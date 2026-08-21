"""
Mem0 Dashboard 后端 - 统计缓存管理

将缓存逻辑独立到单独模块，避免 memories → stats → memory_engine 的潜在循环导入。
"""
import time

# ============ 统计缓存 ============
_stats_cache: dict = {"data": None, "expire": 0.0}
_STATS_CACHE_TTL = 30


def invalidate_stats_cache():
    """使统计缓存失效"""
    _stats_cache["data"] = None
    _stats_cache["expire"] = 0.0


def get_cached_stats() -> dict | None:
    """获取缓存的统计数据（如果未过期）"""
    now_ts = time.time()
    if _stats_cache["data"] is not None and now_ts < _stats_cache["expire"]:
        return _stats_cache["data"]
    return None


def set_cached_stats(data: dict):
    """设置缓存的统计数据"""
    _stats_cache["data"] = data
    _stats_cache["expire"] = time.time() + _STATS_CACHE_TTL
