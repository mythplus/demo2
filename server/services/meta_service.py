"""
记忆元数据 CRUD 服务 — 基于 SQLAlchemy 的关系库操作
对齐 OpenMemory 官方架构，所有结构化查询（过滤、分页、统计、状态管理）
都通过关系库完成，Qdrant 只负责向量存储与语义搜索。
"""

import logging
from typing import List, Optional, Dict, Any
from datetime import datetime, timezone

from sqlalchemy import func, and_, or_, case, text
from sqlalchemy.orm import Session, joinedload

from server.models.database import get_session_factory
from server.models.models import (
    MemoryMeta, Category, MemoryStatusHistory, MemoryChangeLog,
    MemoryState, memory_categories,
)
from server.config import VALID_CATEGORIES

logger = logging.getLogger(__name__)


# ============ 会话管理 ============

def _get_db() -> Session:
    """获取数据库会话"""
    SessionLocal = get_session_factory()
    return SessionLocal()


# ============ 分类管理 ============

def get_or_create_categories(db: Session, category_names: List[str]) -> List[Category]:
    """获取或创建分类对象列表"""
    if not category_names:
        return []
    valid_names = [n for n in category_names if n in VALID_CATEGORIES]
    if not valid_names:
        return []

    existing = db.query(Category).filter(Category.name.in_(valid_names)).all()
    existing_map = {c.name: c for c in existing}

    result = []
    for name in valid_names:
        if name in existing_map:
            result.append(existing_map[name])
        else:
            cat = Category(name=name, description=f"自动创建的分类: {name}")
            db.add(cat)
            db.flush()
            result.append(cat)
    return result


# ============ 记忆元数据 CRUD ============

def create_memory_meta(
    memory_id: str,
    user_id: str,
    content: str,
    hash_value: str = "",
    agent_id: str = "",
    run_id: str = "",
    state: str = "active",
    categories: List[str] = None,
    metadata: dict = None,
    created_at: datetime = None,
) -> dict:
    """创建记忆元数据记录（在 Qdrant 写入成功后调用）"""
    db = _get_db()
    try:
        # 获取或创建分类
        cat_objects = get_or_create_categories(db, categories or [])

        memory = MemoryMeta(
            id=memory_id,
            user_id=user_id,
            content=content,
            hash=hash_value,
            agent_id=agent_id or "",
            run_id=run_id or "",
            state=MemoryState(state) if state in [e.value for e in MemoryState] else MemoryState.active,
            metadata_=metadata or {},
            categories=cat_objects,
            created_at=created_at or datetime.now(timezone.utc),
        )
        db.add(memory)

        # 记录状态变更历史
        history = MemoryStatusHistory(
            memory_id=memory_id,
            old_state=MemoryState.active,
            new_state=memory.state,
            changed_by=user_id,
            reason="创建记忆",
        )
        db.add(history)

        # 记录变更日志
        changelog = MemoryChangeLog(
            memory_id=memory_id,
            event="create",
            new_content=content,
            new_categories=categories or [],
        )
        db.add(changelog)

        db.commit()
        return memory.to_dict()
    except Exception as e:
        db.rollback()
        logger.error(f"创建记忆元数据失败: {e}")
        raise
    finally:
        db.close()


def update_memory_meta(
    memory_id: str,
    content: str = None,
    state: str = None,
    categories: List[str] = None,
    metadata: dict = None,
    changed_by: str = None,
    reason: str = None,
) -> Optional[dict]:
    """更新记忆元数据"""
    db = _get_db()
    try:
        memory = db.query(MemoryMeta).options(joinedload(MemoryMeta.categories)).filter(
            MemoryMeta.id == memory_id
        ).first()
        if not memory:
            return None

        old_content = memory.content
        old_categories = [c.name for c in memory.categories]
        old_state = memory.state

        # 更新内容
        if content is not None:
            memory.content = content

        # 更新状态
        if state is not None:
            new_state = MemoryState(state) if state in [e.value for e in MemoryState] else None
            if new_state and new_state != old_state:
                memory.state = new_state
                memory.updated_at = datetime.now(timezone.utc)

                # 设置特殊时间戳
                if new_state == MemoryState.archived:
                    memory.archived_at = datetime.now(timezone.utc)
                elif new_state == MemoryState.deleted:
                    memory.deleted_at = datetime.now(timezone.utc)

                # 记录状态变更历史
                history = MemoryStatusHistory(
                    memory_id=memory_id,
                    old_state=old_state,
                    new_state=new_state,
                    changed_by=changed_by or memory.user_id,
                    reason=reason or f"状态变更: {old_state.value} -> {new_state.value}",
                )
                db.add(history)

        # 更新分类
        if categories is not None:
            cat_objects = get_or_create_categories(db, categories)
            memory.categories = cat_objects

        # 更新扩展元数据
        if metadata is not None:
            memory.metadata_ = metadata

        memory.updated_at = datetime.now(timezone.utc)

        # 记录变更日志
        new_categories = [c.name for c in memory.categories]
        changelog = MemoryChangeLog(
            memory_id=memory_id,
            event="update",
            old_content=old_content,
            new_content=memory.content,
            old_categories=old_categories,
            new_categories=new_categories,
        )
        db.add(changelog)

        db.commit()
        db.refresh(memory)
        return memory.to_dict()
    except Exception as e:
        db.rollback()
        logger.error(f"更新记忆元数据失败: {e}")
        raise
    finally:
        db.close()


def soft_delete_memory(memory_id: str, changed_by: str = None) -> bool:
    """软删除记忆（标记为 deleted 状态）"""
    result = update_memory_meta(
        memory_id=memory_id,
        state="deleted",
        changed_by=changed_by,
        reason="用户删除",
    )
    return result is not None


def batch_soft_delete(memory_ids: List[str], changed_by: str = None) -> Dict[str, Any]:
    """批量软删除记忆"""
    db = _get_db()
    try:
        results = []
        success_count = 0
        failed_count = 0

        for mid in memory_ids:
            try:
                memory = db.query(MemoryMeta).filter(MemoryMeta.id == mid).first()
                if not memory:
                    results.append({"id": mid, "success": False, "error": "记忆不存在"})
                    failed_count += 1
                    continue

                if memory.state == MemoryState.deleted:
                    results.append({"id": mid, "success": False, "error": "记忆已删除"})
                    failed_count += 1
                    continue

                old_state = memory.state
                memory.state = MemoryState.deleted
                memory.deleted_at = datetime.now(timezone.utc)
                memory.updated_at = datetime.now(timezone.utc)

                # 状态变更历史
                db.add(MemoryStatusHistory(
                    memory_id=mid,
                    old_state=old_state,
                    new_state=MemoryState.deleted,
                    changed_by=changed_by or memory.user_id,
                    reason="批量删除",
                ))

                # 变更日志
                db.add(MemoryChangeLog(
                    memory_id=mid,
                    event="delete",
                    old_content=memory.content,
                    new_content=memory.content,
                    old_categories=[c.name for c in memory.categories],
                    new_categories=[c.name for c in memory.categories],
                ))

                results.append({"id": mid, "success": True})
                success_count += 1
            except Exception as e:
                results.append({"id": mid, "success": False, "error": str(e)})
                failed_count += 1

        db.commit()
        return {
            "total": len(memory_ids),
            "success": success_count,
            "failed": failed_count,
            "results": results,
        }
    except Exception as e:
        db.rollback()
        logger.error(f"批量软删除失败: {e}")
        raise
    finally:
        db.close()


def get_memory_meta(memory_id: str) -> Optional[dict]:
    """获取单条记忆元数据"""
    db = _get_db()
    try:
        memory = db.query(MemoryMeta).options(joinedload(MemoryMeta.categories)).filter(
            MemoryMeta.id == memory_id
        ).first()
        return memory.to_dict() if memory else None
    finally:
        db.close()


# ============ 查询与分页 ============

def _build_query_filters(
    db: Session,
    user_id: str = None,
    state: str = None,
    exclude_state: str = None,
    categories: List[str] = None,
    date_from: str = None,
    date_to: str = None,
    search: str = None,
):
    """构建 SQLAlchemy 查询过滤条件"""
    filters = []

    if user_id:
        filters.append(MemoryMeta.user_id == user_id)

    if state:
        try:
            filters.append(MemoryMeta.state == MemoryState(state))
        except ValueError:
            pass

    if exclude_state:
        try:
            filters.append(MemoryMeta.state != MemoryState(exclude_state))
        except ValueError:
            pass

    if categories:
        valid_cats = [c for c in categories if c in VALID_CATEGORIES]
        if valid_cats:
            filters.append(
                MemoryMeta.categories.any(Category.name.in_(valid_cats))
            )

    if date_from:
        try:
            from_dt = _parse_date(date_from, end_of_day=False)
            if from_dt:
                filters.append(MemoryMeta.created_at >= from_dt)
        except (ValueError, TypeError):
            pass

    if date_to:
        try:
            to_dt = _parse_date(date_to, end_of_day=True)
            if to_dt:
                filters.append(MemoryMeta.created_at <= to_dt)
        except (ValueError, TypeError):
            pass

    if search:
        keyword = f"%{search.strip()}%"
        filters.append(
            or_(
                MemoryMeta.content.ilike(keyword),
                MemoryMeta.user_id.ilike(keyword),
                MemoryMeta.id.ilike(keyword),
            )
        )

    return filters


def _parse_date(value: str, end_of_day: bool = False) -> Optional[datetime]:
    """解析日期字符串为 datetime"""
    value = (value or "").strip()
    if not value:
        return None

    if len(value) == 10 and value[4] == "-" and value[7] == "-":
        suffix = "T23:59:59+00:00" if end_of_day else "T00:00:00+00:00"
        return datetime.fromisoformat(value + suffix)

    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def query_memories_page(
    user_id: str = None,
    state: str = None,
    exclude_state: str = None,
    categories: List[str] = None,
    date_from: str = None,
    date_to: str = None,
    search: str = None,
    page: int = 1,
    page_size: int = 20,
    sort_by: str = "created_at",
    sort_order: str = "desc",
) -> dict:
    """从关系库查询分页记忆列表"""
    db = _get_db()
    try:
        safe_page = max(1, int(page or 1))
        safe_page_size = max(1, min(int(page_size or 20), 200))

        query = db.query(MemoryMeta).options(joinedload(MemoryMeta.categories))
        filters = _build_query_filters(
            db, user_id=user_id, state=state, exclude_state=exclude_state,
            categories=categories, date_from=date_from, date_to=date_to, search=search,
        )
        for f in filters:
            query = query.filter(f)

        # 总数
        count_query = db.query(func.count(MemoryMeta.id))
        for f in filters:
            count_query = count_query.filter(f)
        total = count_query.scalar() or 0

        # 排序
        sort_col = getattr(MemoryMeta, sort_by, MemoryMeta.created_at)
        if sort_order == "asc":
            query = query.order_by(sort_col.asc())
        else:
            query = query.order_by(sort_col.desc())

        # 分页
        offset = (safe_page - 1) * safe_page_size
        memories = query.offset(offset).limit(safe_page_size).all()

        # 去重（joinedload 可能导致重复）
        seen = set()
        unique_memories = []
        for m in memories:
            if m.id not in seen:
                seen.add(m.id)
                unique_memories.append(m)

        total_pages = max(1, (total + safe_page_size - 1) // safe_page_size)
        return {
            "items": [m.to_dict() for m in unique_memories],
            "total": total,
            "page": safe_page,
            "page_size": safe_page_size,
            "total_pages": total_pages,
        }
    finally:
        db.close()


def query_all_memories(
    user_id: str = None,
    state: str = None,
    exclude_state: str = None,
    categories: List[str] = None,
    date_from: str = None,
    date_to: str = None,
    search: str = None,
    sort_by: str = "created_at",
    sort_order: str = "desc",
) -> List[dict]:
    """从关系库查询全部记忆（用于导出等场景）"""
    db = _get_db()
    try:
        query = db.query(MemoryMeta).options(joinedload(MemoryMeta.categories))
        filters = _build_query_filters(
            db, user_id=user_id, state=state, exclude_state=exclude_state,
            categories=categories, date_from=date_from, date_to=date_to, search=search,
        )
        for f in filters:
            query = query.filter(f)

        sort_col = getattr(MemoryMeta, sort_by, MemoryMeta.created_at)
        if sort_order == "asc":
            query = query.order_by(sort_col.asc())
        else:
            query = query.order_by(sort_col.desc())

        memories = query.all()

        seen = set()
        result = []
        for m in memories:
            if m.id not in seen:
                seen.add(m.id)
                result.append(m.to_dict())
        return result
    finally:
        db.close()


# ============ 用户汇总 ============

def get_users_summary_from_db() -> List[dict]:
    """从关系库聚合用户摘要"""
    db = _get_db()
    try:
        results = db.query(
            MemoryMeta.user_id,
            func.count(MemoryMeta.id).label("memory_count"),
            func.max(
                case(
                    (MemoryMeta.updated_at.isnot(None), MemoryMeta.updated_at),
                    else_=MemoryMeta.created_at,
                )
            ).label("last_active"),
        ).filter(
            MemoryMeta.state != MemoryState.deleted,
            MemoryMeta.user_id.isnot(None),
            MemoryMeta.user_id != "",
        ).group_by(
            MemoryMeta.user_id,
        ).order_by(
            func.count(MemoryMeta.id).desc(),
        ).all()

        return [
            {
                "user_id": row.user_id,
                "memory_count": row.memory_count,
                "last_active": row.last_active.isoformat() if row.last_active else "",
            }
            for row in results
        ]
    finally:
        db.close()


# ============ 统计聚合 ============

def compute_stats_from_db() -> dict:
    """从关系库聚合统计信息"""
    db = _get_db()
    try:
        # 状态分布
        state_rows = db.query(
            MemoryMeta.state,
            func.count(MemoryMeta.id),
        ).group_by(MemoryMeta.state).all()
        state_distribution = {s.value: 0 for s in MemoryState}
        total_memories = 0
        for state_val, count in state_rows:
            key = state_val.value if isinstance(state_val, MemoryState) else str(state_val)
            state_distribution[key] = count
            if key != "deleted":
                total_memories += count

        # 用户数
        total_users = db.query(func.count(func.distinct(MemoryMeta.user_id))).filter(
            MemoryMeta.state != MemoryState.deleted,
            MemoryMeta.user_id.isnot(None),
            MemoryMeta.user_id != "",
        ).scalar() or 0

        # 分类分布
        cat_rows = db.query(
            Category.name,
            func.count(MemoryMeta.id),
        ).join(
            memory_categories, Category.id == memory_categories.c.category_id
        ).join(
            MemoryMeta, MemoryMeta.id == memory_categories.c.memory_id
        ).filter(
            MemoryMeta.state != MemoryState.deleted,
        ).group_by(Category.name).all()
        category_distribution = {cat: 0 for cat in VALID_CATEGORIES}
        for cat_name, count in cat_rows:
            if cat_name in VALID_CATEGORIES:
                category_distribution[cat_name] = count

        # 未分类数量
        categorized_ids = db.query(memory_categories.c.memory_id).distinct().subquery()
        uncategorized_count = db.query(func.count(MemoryMeta.id)).filter(
            MemoryMeta.state != MemoryState.deleted,
            ~MemoryMeta.id.in_(db.query(categorized_ids)),
        ).scalar() or 0

        # 每日趋势
        daily_rows = db.query(
            func.date(MemoryMeta.created_at).label("day"),
            func.count(MemoryMeta.id),
        ).filter(
            MemoryMeta.state != MemoryState.deleted,
        ).group_by("day").order_by("day").all()
        daily_counter = {str(row.day): row[1] for row in daily_rows if row.day}

        return {
            "total_memories": total_memories,
            "total_users": total_users,
            "category_distribution": category_distribution,
            "uncategorized_count": uncategorized_count,
            "state_distribution": state_distribution,
            "daily_counter": daily_counter,
        }
    finally:
        db.close()


# ============ 首页摘要 ============

def get_summary_from_db(limit_recent: int = 5, limit_top_users: int = 10) -> dict:
    """从关系库获取首页摘要数据"""
    db = _get_db()
    try:
        safe_recent = max(1, min(int(limit_recent or 5), 20))
        safe_top_users = max(1, min(int(limit_top_users or 10), 50))

        # 最近记忆
        recent = db.query(MemoryMeta).options(joinedload(MemoryMeta.categories)).filter(
            MemoryMeta.state != MemoryState.deleted,
        ).order_by(MemoryMeta.created_at.desc()).limit(safe_recent).all()

        seen = set()
        recent_memories = []
        for m in recent:
            if m.id not in seen:
                seen.add(m.id)
                recent_memories.append(m.to_dict())

        # 活跃用户
        top_users_rows = db.query(
            MemoryMeta.user_id,
            func.count(MemoryMeta.id).label("memory_count"),
        ).filter(
            MemoryMeta.state != MemoryState.deleted,
            MemoryMeta.user_id.isnot(None),
            MemoryMeta.user_id != "",
        ).group_by(
            MemoryMeta.user_id,
        ).order_by(
            func.count(MemoryMeta.id).desc(),
        ).limit(safe_top_users).all()

        top_users = [
            {"user_id": row.user_id, "memory_count": row.memory_count}
            for row in top_users_rows
        ]

        return {
            "recent_memories": recent_memories,
            "top_users": top_users,
        }
    finally:
        db.close()


# ============ 变更历史 ============

def get_memory_change_logs(memory_id: str) -> List[dict]:
    """获取记忆的变更历史"""
    db = _get_db()
    try:
        logs = db.query(MemoryChangeLog).filter(
            MemoryChangeLog.memory_id == memory_id,
        ).order_by(MemoryChangeLog.created_at.asc()).all()

        return [
            {
                "id": log.id,
                "memory_id": log.memory_id,
                "event": log.event,
                "old_memory": log.old_content,
                "new_memory": log.new_content,
                "categories": log.new_categories or [],
                "old_categories": log.old_categories or [],
                "created_at": log.created_at.isoformat() if log.created_at else "",
            }
            for log in logs
        ]
    finally:
        db.close()


def get_status_history(memory_id: str) -> List[dict]:
    """获取记忆的状态变更历史"""
    db = _get_db()
    try:
        history = db.query(MemoryStatusHistory).filter(
            MemoryStatusHistory.memory_id == memory_id,
        ).order_by(MemoryStatusHistory.changed_at.asc()).all()

        return [
            {
                "id": h.id,
                "memory_id": h.memory_id,
                "old_state": h.old_state.value if isinstance(h.old_state, MemoryState) else h.old_state,
                "new_state": h.new_state.value if isinstance(h.new_state, MemoryState) else h.new_state,
                "changed_by": h.changed_by or "",
                "changed_at": h.changed_at.isoformat() if h.changed_at else "",
                "reason": h.reason or "",
            }
            for h in history
        ]
    finally:
        db.close()


# ============ 记忆是否存在于关系库 ============

def memory_exists_in_db(memory_id: str) -> bool:
    """检查记忆是否存在于关系库"""
    db = _get_db()
    try:
        return db.query(MemoryMeta.id).filter(MemoryMeta.id == memory_id).first() is not None
    finally:
        db.close()


def count_memories(
    user_id: str = None,
    state: str = None,
    exclude_state: str = None,
) -> int:
    """统计记忆数量"""
    db = _get_db()
    try:
        query = db.query(func.count(MemoryMeta.id))
        if user_id:
            query = query.filter(MemoryMeta.user_id == user_id)
        if state:
            try:
                query = query.filter(MemoryMeta.state == MemoryState(state))
            except ValueError:
                pass
        if exclude_state:
            try:
                query = query.filter(MemoryMeta.state != MemoryState(exclude_state))
            except ValueError:
                pass
        return query.scalar() or 0
    finally:
        db.close()
