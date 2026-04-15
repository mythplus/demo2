"""
记忆元数据 CRUD 服务 — 基于 SQLAlchemy 的关系库操作
对齐 OpenMemory 官方架构，所有结构化查询（过滤、分页、统计、状态管理）
都通过关系库完成，Qdrant 只负责向量存储与语义搜索。
"""

import logging
from typing import List, Optional, Dict, Any
from datetime import datetime, timezone

from sqlalchemy import func, and_, or_, case, text
from sqlalchemy.orm import Session, subqueryload

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
        memory = db.query(MemoryMeta).options(subqueryload(MemoryMeta.categories)).filter(
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


def hard_delete_memory_meta(memory_id: str) -> bool:
    """物理删除单条记忆的关系库元数据（级联删除关联的分类、状态历史、变更日志）"""
    db = _get_db()
    try:
        memory = db.query(MemoryMeta).filter(MemoryMeta.id == memory_id).first()
        if not memory:
            return False
        db.delete(memory)
        db.commit()
        return True
    except Exception as e:
        db.rollback()
        logger.error(f"物理删除记忆元数据失败: {e}")
        raise
    finally:
        db.close()


def batch_hard_delete_memory_meta(memory_ids: List[str]) -> Dict[str, Any]:
    """批量物理删除记忆的关系库元数据"""
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

                db.delete(memory)
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
        logger.error(f"批量物理删除失败: {e}")
        raise
    finally:
        db.close()


def get_memory_meta(memory_id: str) -> Optional[dict]:
    """获取单条记忆元数据"""
    db = _get_db()
    try:
        memory = db.query(MemoryMeta).options(subqueryload(MemoryMeta.categories)).filter(
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
    exclude_states: List[str] = None,
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

    # 支持多个排除状态（优先使用 exclude_states 列表）
    if exclude_states:
        valid_excludes = []
        for es in exclude_states:
            try:
                valid_excludes.append(MemoryState(es))
            except ValueError:
                pass
        if valid_excludes:
            filters.append(MemoryMeta.state.notin_(valid_excludes))
    elif exclude_state:
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
    exclude_states: List[str] = None,
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

        # 第一步：只查主表 ID 进行分页（避免 JOIN 膨胀导致 LIMIT 不准）
        id_query = db.query(MemoryMeta.id)
        filters = _build_query_filters(
            db, user_id=user_id, state=state, exclude_state=exclude_state,
            exclude_states=exclude_states,
            categories=categories, date_from=date_from, date_to=date_to, search=search,
        )
        for f in filters:
            id_query = id_query.filter(f)

        # 总数
        count_query = db.query(func.count(MemoryMeta.id))
        for f in filters:
            count_query = count_query.filter(f)
        total = count_query.scalar() or 0

        # 排序
        sort_col = getattr(MemoryMeta, sort_by, MemoryMeta.created_at)
        if sort_order == "asc":
            id_query = id_query.order_by(sort_col.asc())
        else:
            id_query = id_query.order_by(sort_col.desc())

        # 分页（在主表 ID 上 LIMIT，不受 JOIN 影响）
        offset = (safe_page - 1) * safe_page_size
        page_ids = [row[0] for row in id_query.offset(offset).limit(safe_page_size).all()]

        # 第二步：用 ID 列表加载完整对象 + 关联分类
        if page_ids:
            query = db.query(MemoryMeta).options(subqueryload(MemoryMeta.categories)).filter(
                MemoryMeta.id.in_(page_ids)
            )
            if sort_order == "asc":
                query = query.order_by(sort_col.asc())
            else:
                query = query.order_by(sort_col.desc())
            memories = query.all()
        else:
            memories = []

        total_pages = max(1, (total + safe_page_size - 1) // safe_page_size)
        return {
            "items": [m.to_dict() for m in memories],
            "total": total,
            "page": safe_page,
            "page_size": safe_page_size,
            "total_pages": total_pages,
        }
    finally:
        db.close()


def query_all_memory_ids(
    user_id: str = None,
    state: str = None,
    exclude_state: str = None,
    exclude_states: List[str] = None,
    categories: List[str] = None,
    date_from: str = None,
    date_to: str = None,
    search: str = None,
) -> List[str]:
    """从关系库查询当前筛选条件下的所有记忆 ID（用于前端全选功能）"""
    db = _get_db()
    try:
        id_query = db.query(MemoryMeta.id)
        filters = _build_query_filters(
            db, user_id=user_id, state=state, exclude_state=exclude_state,
            exclude_states=exclude_states,
            categories=categories, date_from=date_from, date_to=date_to, search=search,
        )
        for f in filters:
            id_query = id_query.filter(f)
        return [row[0] for row in id_query.all()]
    finally:
        db.close()


def query_all_memories(
    user_id: str = None,
    state: str = None,
    exclude_state: str = None,
    exclude_states: List[str] = None,
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
        query = db.query(MemoryMeta).options(subqueryload(MemoryMeta.categories))
        filters = _build_query_filters(
            db, user_id=user_id, state=state, exclude_state=exclude_state,
            exclude_states=exclude_states,
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
        return [m.to_dict() for m in memories]
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
            if key in state_distribution:
                state_distribution[key] = count
            total_memories += count

        # 用户数
        total_users = db.query(func.count(func.distinct(MemoryMeta.user_id))).filter(
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
        ).group_by(Category.name).all()
        category_distribution = {cat: 0 for cat in VALID_CATEGORIES}
        for cat_name, count in cat_rows:
            if cat_name in VALID_CATEGORIES:
                category_distribution[cat_name] = count

        # 未分类数量
        categorized_ids = db.query(memory_categories.c.memory_id).distinct().subquery()
        uncategorized_count = db.query(func.count(MemoryMeta.id)).filter(
            ~MemoryMeta.id.in_(db.query(categorized_ids)),
        ).scalar() or 0

        # 每日趋势
        daily_rows = db.query(
            func.date(MemoryMeta.created_at).label("day"),
            func.count(MemoryMeta.id),
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

        # 最近记忆（两阶段查询：先查 ID 分页，再加载关联数据）
        recent_ids = [row[0] for row in db.query(MemoryMeta.id).filter(
            MemoryMeta.state != MemoryState.deleted,
        ).order_by(MemoryMeta.created_at.desc()).limit(safe_recent).all()]

        if recent_ids:
            recent = db.query(MemoryMeta).options(subqueryload(MemoryMeta.categories)).filter(
                MemoryMeta.id.in_(recent_ids)
            ).order_by(MemoryMeta.created_at.desc()).all()
            recent_memories = [m.to_dict() for m in recent]
        else:
            recent_memories = []

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


# ============ 统一状态变更入口（关系库为主，同步写 Qdrant） ============

async def update_memory_state(
    memory_id: str,
    new_state: str,
    operator: str = "system",
    reason: str = "",
) -> dict:
    """统一状态变更入口 — 关系库为主存储，同步写 Qdrant metadata。

    逻辑：
    1. 校验状态合法性
    2. 从关系库读取当前状态
    3. 幂等：old_state == new_state 直接返回
    4. 更新关系库（state + 时间戳 + 状态历史）
    5. 同步写 Qdrant metadata
    6. invalidate_stats_cache
    7. 返回结果
    """
    from server.config import VALID_STATES
    from server.services.memory_service import invalidate_stats_cache, _get_qdrant_collection_and_client

    if new_state not in VALID_STATES:
        raise ValueError(f"无效的状态: {new_state}，合法值: {VALID_STATES}")

    now_utc = datetime.now(timezone.utc)
    now_iso = now_utc.isoformat()

    # 1. 关系库操作（主存储）
    db = _get_db()
    try:
        memory = db.query(MemoryMeta).options(subqueryload(MemoryMeta.categories)).filter(
            MemoryMeta.id == memory_id
        ).first()
        if not memory:
            raise ValueError(f"记忆不存在: {memory_id}")

        old_state_enum = memory.state
        old_state = old_state_enum.value if isinstance(old_state_enum, MemoryState) else str(old_state_enum or "active")

        # 幂等
        if old_state == new_state:
            return {
                "memory_id": memory_id,
                "old_state": old_state,
                "new_state": new_state,
                "changed": False,
                "message": f"状态已经是 {new_state}，无需变更",
            }

        # 更新状态
        try:
            new_state_enum = MemoryState(new_state)
        except ValueError:
            raise ValueError(f"无效的状态: {new_state}")

        memory.state = new_state_enum
        memory.updated_at = now_utc

        if new_state == "archived":
            memory.archived_at = now_utc

        # 记录状态变更历史
        history = MemoryStatusHistory(
            memory_id=memory_id,
            old_state=old_state_enum,
            new_state=new_state_enum,
            changed_by=operator,
            reason=reason or f"状态变更: {old_state} -> {new_state}",
        )
        db.add(history)

        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()

    # 2. 同步写 Qdrant metadata（非关键路径，失败只打 warning）
    try:
        collection_name, qdrant_client = _get_qdrant_collection_and_client()
        points = qdrant_client.retrieve(
            collection_name=collection_name,
            ids=[memory_id],
            with_payload=True,
        )
        if points:
            metadata = dict((points[0].payload or {}).get("metadata", {}) or {})
            metadata["state"] = new_state
            metadata["state_updated_at"] = now_iso
            metadata["state_updated_by"] = operator
            if new_state == "archived":
                metadata["archived_at"] = now_iso
            qdrant_client.set_payload(
                collection_name=collection_name,
                payload={"metadata": metadata},
                points=[memory_id],
            )
    except Exception as qdrant_err:
        logger.warning(f"Qdrant metadata 同步失败（关系库已更新）: {qdrant_err}")

    # 3. 缓存失效
    invalidate_stats_cache()

    logger.info(f"记忆 {memory_id} 状态变更: {old_state} -> {new_state} (by {operator}, reason: {reason})")

    return {
        "memory_id": memory_id,
        "old_state": old_state,
        "new_state": new_state,
        "changed": True,
        "state_updated_at": now_iso,
        "message": f"状态已从 {old_state} 变更为 {new_state}",
    }


async def batch_update_memory_state(
    memory_ids: list,
    new_state: str,
    operator: str = "system",
    reason: str = "",
) -> dict:
    """批量状态变更 — 逐条调用 update_memory_state"""
    from server.config import VALID_STATES

    if new_state not in VALID_STATES:
        raise ValueError(f"无效的状态: {new_state}")

    results = []
    success_count = 0
    failed_count = 0

    for mid in memory_ids:
        try:
            result = await update_memory_state(
                memory_id=mid,
                new_state=new_state,
                operator=operator,
                reason=reason,
            )
            results.append({"id": mid, "success": True, **result})
            success_count += 1
        except Exception as e:
            results.append({"id": mid, "success": False, "error": str(e)})
            failed_count += 1

    return {
        "total": len(memory_ids),
        "success": success_count,
        "failed": failed_count,
        "results": results,
    }


# ============ 默认列表状态过滤规则 ============

def resolve_list_state_filters(
    state: str | None = None,
    exclude_state: str | None = None,
    show_archived: bool = False,
) -> tuple:
    """解析列表查询的状态过滤参数。

    返回: (state_filter, exclude_states_list)

    规则（对齐 openmemory）：
    - 如果明确指定了 state，按指定的查
    - 如果没指定 state：默认排除 deleted 和 archived
    - 如果 show_archived=True：只排除 deleted
    - exclude_state 参数仍然生效
    """
    if state:
        # 明确指定了状态，直接用
        return state, []

    # 没指定 state，应用默认排除规则
    exclude_list = []
    if not show_archived:
        exclude_list.append("archived")

    # 额外的 exclude_state
    if exclude_state and exclude_state not in exclude_list:
        exclude_list.append(exclude_state)

    return None, exclude_list
