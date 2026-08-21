"""
Mem0 Dashboard 后端 - 用户管理路由
"""
import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from app.config import MEM0_CONFIG, _safe_error_detail
from app.memory_engine import get_all_memories_raw, apply_filters

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1/users", tags=["users"])


@router.get("/")
async def get_users(
    search: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    """获取用户列表（从记忆数据中聚合）"""
    try:
        all_memories = get_all_memories_raw()

        user_map: dict = {}
        for m in all_memories:
            uid = m.get("user_id", "")
            if not uid:
                continue
            if uid not in user_map:
                user_map[uid] = {
                    "user_id": uid,
                    "memory_count": 0,
                    "active_count": 0,
                    "paused_count": 0,
                    "deleted_count": 0,
                    "last_active": "",
                }
            user_map[uid]["memory_count"] += 1
            state = m.get("state", "active")
            if state == "active":
                user_map[uid]["active_count"] += 1
            elif state == "paused":
                user_map[uid]["paused_count"] += 1
            elif state == "deleted":
                user_map[uid]["deleted_count"] += 1

            created = m.get("created_at", "")
            if created and created > user_map[uid]["last_active"]:
                user_map[uid]["last_active"] = created

        users = list(user_map.values())

        if search:
            keyword = search.lower()
            users = [u for u in users if keyword in u["user_id"].lower()]

        users.sort(key=lambda u: u["memory_count"], reverse=True)

        total = len(users)
        users = users[offset:offset + limit]

        return {"users": users, "total": total, "limit": limit, "offset": offset}
    except Exception as e:
        logger.error(f"获取用户列表失败: {e}")
        raise HTTPException(status_code=500, detail=_safe_error_detail(e))


@router.get("/{user_id}/")
async def get_user_detail(user_id: str):
    """获取用户详情"""
    try:
        all_memories = get_all_memories_raw()
        user_memories = [m for m in all_memories if m.get("user_id") == user_id]

        if not user_memories:
            raise HTTPException(status_code=404, detail="用户不存在")

        active_count = sum(1 for m in user_memories if m.get("state", "active") == "active")
        paused_count = sum(1 for m in user_memories if m.get("state") == "paused")
        deleted_count = sum(1 for m in user_memories if m.get("state") == "deleted")

        category_counter: dict = {}
        for m in user_memories:
            for cat in (m.get("categories") or []):
                category_counter[cat] = category_counter.get(cat, 0) + 1

        last_active = ""
        for m in user_memories:
            created = m.get("created_at", "")
            if created and created > last_active:
                last_active = created

        return {
            "user_id": user_id,
            "total_memories": len(user_memories),
            "active_count": active_count,
            "paused_count": paused_count,
            "deleted_count": deleted_count,
            "category_distribution": category_counter,
            "last_active": last_active,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取用户详情失败: {e}")
        raise HTTPException(status_code=500, detail=_safe_error_detail(e))


@router.get("/{user_id}/memories/")
async def get_user_memories(
    user_id: str,
    categories: Optional[str] = Query(None),
    state: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    """获取用户的所有记忆"""
    try:
        all_memories = get_all_memories_raw()
        user_memories = [m for m in all_memories if m.get("user_id") == user_id]

        cat_list = [c.strip() for c in categories.split(",") if c.strip()] if categories else None
        filtered = apply_filters(user_memories, categories=cat_list, state=state, search=search)

        total = len(filtered)
        paged = filtered[offset:offset + limit]

        return {"memories": paged, "total": total, "limit": limit, "offset": offset}
    except Exception as e:
        logger.error(f"获取用户记忆失败: {e}")
        raise HTTPException(status_code=500, detail=_safe_error_detail(e))
