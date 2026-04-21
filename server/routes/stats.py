"""
统计接口路由
"""

import time
import logging
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, HTTPException

from server.config import _safe_error_detail
from server.services.memory_service import (
    compute_memory_stats, get_stats_cache, set_stats_cache,
)


logger = logging.getLogger(__name__)

router = APIRouter(tags=["统计"])

# B3 P2-6: 删除死代码 _STATS_CACHE_TTL（真正的 TTL 在 memory_service._STATS_CACHE_TTL 中定义）


@router.get("/v1/stats/")
async def get_stats():
    """获取统计数据（分类分布、状态分布、每日趋势）— 带 TTL 缓存，流式聚合避免全量拉取列表"""
    try:
        # 检查缓存是否有效
        cache = get_stats_cache()
        now_ts = time.time()
        if cache["data"] is not None and now_ts < cache["expire"]:
            return cache["data"]

        aggregated = compute_memory_stats()
        daily_counter = aggregated.pop("daily_counter", {})

        # 构建每日趋势（补全 30 天内没有数据的日期）
        daily_trend = []
        today = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
        for i in range(29, -1, -1):
            day_str = (today - timedelta(days=i)).strftime("%Y-%m-%d")
            daily_trend.append({"date": day_str, "count": daily_counter.get(day_str, 0)})

        result = {
            **aggregated,
            "daily_trend": daily_trend,
        }

        # 写入缓存
        set_stats_cache(result)

        return result
    except Exception as e:
        logger.error(f"获取统计数据失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=_safe_error_detail(e))
