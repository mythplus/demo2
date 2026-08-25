"""
速率限制器

基于 Redis 滑动窗口实现，Redis 不可达时自动降级为进程内滑动窗口。
支持按租户维度限制每分钟/每小时请求数。
"""
import time
import logging
import threading
from collections import deque
from typing import Optional

from app.config import MEM0_CONFIG

logger = logging.getLogger(__name__)

# ============ Redis 连接（延迟初始化） ============
_redis_client = None
_redis_checked = False


def _get_redis():
    """获取 Redis 连接（不可达时返回 None，只检查一次）"""
    global _redis_client, _redis_checked
    if _redis_checked:
        return _redis_client
    _redis_checked = True

    redis_cfg = MEM0_CONFIG.get("redis", {})
    if not redis_cfg:
        logger.info("未配置 Redis，速率限制将使用进程内降级模式")
        return None

    try:
        import redis
        _redis_client = redis.Redis(
            host=redis_cfg.get("host", "localhost"),
            port=redis_cfg.get("port", 6379),
            db=redis_cfg.get("db", 0),
            password=redis_cfg.get("password", "") or None,
            socket_timeout=redis_cfg.get("socket_timeout", 5),
            decode_responses=True,
        )
        _redis_client.ping()
        logger.info(f"Redis 连接成功: {redis_cfg.get('host')}:{redis_cfg.get('port')}")
        return _redis_client
    except Exception as e:
        logger.warning(f"Redis 连接失败，降级为进程内限流: {e}")
        _redis_client = None
        return None


def _reset_redis():
    """重置 Redis 连接状态（用于测试或重连）"""
    global _redis_client, _redis_checked
    _redis_client = None
    _redis_checked = False


# ============ 进程内滑动窗口（降级方案） ============
_local_windows: dict = {}  # key → deque[timestamps]
_local_lock = threading.Lock()


def _local_sliding_window(key: str, window_seconds: int, max_requests: int) -> tuple:
    """
    进程内滑动窗口检查
    返回 (allowed: bool, current_count: int)
    """
    now = time.time()
    cutoff = now - window_seconds

    with _local_lock:
        dq = _local_windows.get(key)
        if dq is None:
            dq = deque()
            _local_windows[key] = dq

        # 清理过期时间戳
        while dq and dq[0] < cutoff:
            dq.popleft()

        current_count = len(dq)
        if current_count >= max_requests:
            return (False, current_count)

        dq.append(now)
        return (True, current_count + 1)


# ============ 公共接口 ============

def check_rate_limit(tenant_id: str, max_per_minute: int = None,
                     max_per_hour: int = None) -> tuple:
    """
    检查租户速率限制

    返回 (allowed: bool, reason: str)
    """
    rl_cfg = MEM0_CONFIG.get("rate_limit", {})
    if not rl_cfg.get("enabled", False):
        return (True, "速率限制未启用")

    max_per_minute = max_per_minute or rl_cfg.get("per_minute", 120)
    max_per_hour = max_per_hour or rl_cfg.get("per_hour", 3600)

    # 尝试 Redis
    redis_client = _get_redis()
    if redis_client:
        try:
            return _redis_sliding_window(
                redis_client, tenant_id, max_per_minute, max_per_hour
            )
        except Exception as e:
            logger.warning(f"Redis 限流失败，降级进程内: {e}")

    # 降级：进程内
    minute_key = f"rl:{tenant_id}:min"
    hour_key = f"rl:{tenant_id}:hour"

    allowed_min, count_min = _local_sliding_window(minute_key, 60, max_per_minute)
    if not allowed_min:
        return (False, f"已达每分钟限制 ({max_per_minute}/min)")

    allowed_hour, count_hour = _local_sliding_window(hour_key, 3600, max_per_hour)
    if not allowed_hour:
        return (False, f"已达每小时限制 ({max_per_hour}/hour)")

    return (True, "OK")


def _redis_sliding_window(redis_client, tenant_id: str,
                          max_per_minute: int, max_per_hour: int) -> tuple:
    """Redis 滑动窗口实现"""
    now = time.time()
    pipe = redis_client.pipeline()

    minute_key = f"rl:{tenant_id}:min"
    hour_key = f"rl:{tenant_id}:hour"

    # 清理 + 计数（分钟窗口）
    pipe.zremrangebyscore(minute_key, 0, now - 60)
    pipe.zcard(minute_key)

    # 清理 + 计数（小时窗口）
    pipe.zremrangebyscore(hour_key, 0, now - 3600)
    pipe.zcard(hour_key)

    results = pipe.execute()
    minute_count = results[1]
    hour_count = results[3]

    if minute_count >= max_per_minute:
        return (False, f"已达每分钟限制 ({max_per_minute}/min)")
    if hour_count >= max_per_hour:
        return (False, f"已达每小时限制 ({max_per_hour}/hour)")

    # 记录本次请求
    member = f"{now}"
    pipe = redis_client.pipeline()
    pipe.zadd(minute_key, {member: now})
    pipe.zadd(hour_key, {member: now})
    pipe.expire(minute_key, 120)
    pipe.expire(hour_key, 7200)
    pipe.execute()

    return (True, "OK")


# ============ 配额检查 ============

def check_quota(tenant_id: str, tenant: dict = None) -> tuple:
    """
    检查租户配额（每日 API 调用上限 + 记忆总量上限）

    返回 (allowed: bool, reason: str, usage: dict)
    """
    quota_cfg = MEM0_CONFIG.get("quota", {})
    if not quota_cfg.get("enabled", True):
        return (True, "配额检查未启用", {})

    if not tenant:
        from app.tenant_db import get_tenant
        tenant = get_tenant(tenant_id)
    if not tenant:
        return (True, "租户不存在，跳过", {})

    # default 租户/enterprise 套餐不限制
    if tenant.get("plan") == "enterprise" or tenant.get("name") == "default":
        return (True, "企业版无限制", {})

    from app.tenant_db import get_quota_usage
    usage = get_quota_usage(tenant_id)

    # 检查每日 API 调用上限
    max_api = tenant.get("max_api_calls_per_day", quota_cfg.get("default_max_api_calls_per_day", 5000))
    if usage["today_api_call_count"] >= max_api:
        return (False, f"已达每日 API 调用上限 ({max_api}/day)", usage)

    # 检查记忆总量上限（查询 Qdrant 实际数量）
    max_mem = tenant.get("max_memories", quota_cfg.get("default_max_memories", 10000))
    try:
        from app.memory_engine import get_all_memories_raw
        all_mems = get_all_memories_raw(tenant_id=tenant_id)
        total_mems = len(all_mems)
        if total_mems >= max_mem:
            return (False, f"已达记忆总量上限 ({max_mem})", usage)
    except Exception:
        # Qdrant 查询失败时不阻断（优雅降级）
        pass

    return (True, "OK", usage)
