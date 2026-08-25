"""
Mem0 Dashboard 后端 - 统计路由
"""
import logging
from collections import Counter
from datetime import datetime, timedelta

from fastapi import APIRouter, HTTPException, Request

from app.config import VALID_CATEGORIES, VALID_STATES, _safe_error_detail
from app.memory_engine import get_all_memories_raw
from app.cache import get_cached_stats, set_cached_stats

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1/stats", tags=["stats"])


@router.get("/")
async def get_stats(request: Request):
    """获取统计数据"""
    try:
        tenant_id = getattr(request.state, "tenant_id", None)

        # 检查缓存（租户级缓存 key）
        cache_key = f"stats:{tenant_id}" if tenant_id else "stats:default"
        cached = get_cached_stats(cache_key)
        if cached is not None:
            return cached

        all_memories = get_all_memories_raw(tenant_id=tenant_id)

        total_memories = 0
        user_set: set = set()
        category_counter: Counter = Counter()
        uncategorized_count = 0
        state_counter: Counter = Counter()
        daily_counter: Counter = Counter()

        for m in all_memories:
            state = m.get("state", "active")
            state_counter[state] += 1

            if state == "deleted":
                continue

            total_memories += 1
            uid = m.get("user_id")
            if uid:
                user_set.add(uid)

            cats = m.get("categories") or []
            if not cats:
                uncategorized_count += 1
            else:
                for cat in cats:
                    if cat in VALID_CATEGORIES:
                        category_counter[cat] += 1

            created = m.get("created_at")
            if created:
                try:
                    created_dt = datetime.fromisoformat(str(created).replace("Z", "+00:00"))
                    daily_counter[created_dt.strftime("%Y-%m-%d")] += 1
                except (ValueError, TypeError):
                    pass

        category_distribution = {cat: category_counter.get(cat, 0) for cat in VALID_CATEGORIES}
        state_distribution = {s: state_counter.get(s, 0) for s in VALID_STATES}

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

        set_cached_stats(result, cache_key)
        return result
    except Exception as e:
        logger.error(f"获取统计数据失败: {e}")
        raise HTTPException(status_code=500, detail=_safe_error_detail(e))
