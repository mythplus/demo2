"""
统计接口路由
"""

import time
import logging
from datetime import datetime, timedelta
from collections import Counter

from fastapi import APIRouter, HTTPException

from server.config import MEM0_CONFIG, VALID_CATEGORIES, VALID_STATES, _safe_error_detail
from server.services.memory_service import (
    get_all_memories_raw, get_stats_cache, set_stats_cache,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["统计"])

_STATS_CACHE_TTL = 30  # 统计数据缓存 30 秒


@router.get("/v1/stats/")
async def get_stats():
    """获取统计数据（分类分布、状态分布、每日趋势）— 带 TTL 缓存，O(N) 一次遍历"""
    try:
        # 检查缓存是否有效
        cache = get_stats_cache()
        now_ts = time.time()
        if cache["data"] is not None and now_ts < cache["expire"]:
            return cache["data"]

        all_memories = get_all_memories_raw()

        # ===== O(N) 一次遍历，同时计算所有统计指标 =====
        total_memories = 0
        user_set: set = set()
        category_counter: Counter = Counter()
        uncategorized_count = 0
        state_counter: Counter = Counter()
        daily_counter: Counter = Counter()  # date_str -> count（仅活跃记忆）

        for m in all_memories:
            state = m.get("state", "active")
            state_counter[state] += 1

            # 以下统计仅针对活跃记忆（排除已删除）
            if state == "deleted":
                continue

            total_memories += 1
            uid = m.get("user_id")
            if uid:
                user_set.add(uid)

            # 分类统计
            cats = m.get("categories") or []
            if not cats:
                uncategorized_count += 1
            else:
                for cat in cats:
                    if cat in VALID_CATEGORIES:
                        category_counter[cat] += 1

            # 每日趋势统计（只解析一次日期）
            created = m.get("created_at")
            if created:
                try:
                    created_dt = datetime.fromisoformat(str(created).replace("Z", "+00:00"))
                    daily_counter[created_dt.strftime("%Y-%m-%d")] += 1
                except (ValueError, TypeError):
                    pass

        # 构建分类分布（确保所有分类都有值）
        category_distribution = {cat: category_counter.get(cat, 0) for cat in VALID_CATEGORIES}

        # 构建状态分布
        state_distribution = {s: state_counter.get(s, 0) for s in VALID_STATES}

        # 构建每日趋势（补全 30 天内没有数据的日期）
        daily_trend = []
        today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        for i in range(29, -1, -1):
            day_str = (today - timedelta(days=i)).strftime("%Y-%m-%d")
            daily_trend.append({"date": day_str, "count": daily_counter.get(day_str, 0)})

        result = {
            "total_memories": total_memories,
            "total_users": len(user_set),
            "category_distribution": category_distribution,
            "uncategorized_count": uncategorized_count,
            "state_distribution": state_distribution,
            "daily_trend": daily_trend,
        }

        # 写入缓存
        set_stats_cache(result)

        return result
    except Exception as e:
        logger.error(f"获取统计数据失败: {e}")
        raise HTTPException(status_code=500, detail=_safe_error_detail(e))
