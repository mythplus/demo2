"""
Mem0 Dashboard 后端 - 统计缓存管理

将缓存逻辑独立到单独模块，避免 memories → stats → memory_engine 的潜在循环导入。
支持租户级缓存（per-tenant cache key）。
"""
import time

# ============ 统计缓存（按租户隔离） ============
_stats_cache: dict = {}  # key: cache_key → {"data": ..., "expire": float}
_STATS_CACHE_TTL = 30


def invalidate_stats_cache():
    """使所有统计缓存失效"""
    _stats_cache.clear()


def get_cached_stats(cache_key: str = "default") -> dict | None:
    """获取缓存的统计数据（如果未过期）"""
    now_ts = time.time()
    entry = _stats_cache.get(cache_key)
    if entry and entry["data"] is not None and now_ts < entry["expire"]:
        return entry["data"]
    return None


def set_cached_stats(data: dict, cache_key: str = "default"):
    """设置缓存的统计数据"""
    _stats_cache[cache_key] = {
        "data": data,
        "expire": time.time() + _STATS_CACHE_TTL,
    }
