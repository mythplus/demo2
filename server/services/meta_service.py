"""记忆元数据 CRUD 服务 -- 基于 SQLAlchemy 的关系库操作
对齐 mem0 云平台架构，所有结构化查询（过滤、分页、统计）
都通过关系库完成，Qdrant 只负责向量存储与语义搜索。
"""
import logging
from typing import List, Optional, Dict, Any
from datetime import datetime, timezone

from sqlalchemy import func, and_, or_, case, text
from sqlalchemy.orm import Session, subqueryload

from server.models.database import get_session_factory
from server.models.models import (
    MemoryMeta, Category, MemoryChangeLog,
    memory_categories, _ensure_utc_iso,
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
            metadata_=metadata or {},
            categories=cat_objects,
            created_at=created_at or datetime.now(timezone.utc),
        )
        db.add(memory)
        db.flush()  # 先写入 memory，确保外键约束满足

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
    categories: List[str] = None,
    metadata: dict = None,
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

        # 更新内容
        if content is not None:
            memory.content = content

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
    categories: List[str] = None,
    date_from: str = None,
    date_to: str = None,
    search: str = None,
):
    """构建 SQLAlchemy 查询过滤条件"""
    filters = []

    if user_id:
        filters.append(MemoryMeta.user_id == user_id)

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
            db, user_id=user_id,
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
            db, user_id=user_id,
            categories=categories, date_from=date_from, date_to=date_to, search=search,
        )
        for f in filters:
            id_query = id_query.filter(f)
        return [row[0] for row in id_query.all()]
    finally:
        db.close()


def query_all_memories(
    user_id: str = None,
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
            db, user_id=user_id,
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
                "last_active": _ensure_utc_iso(row.last_active),
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
        # 总记忆数
        total_memories = db.query(func.count(MemoryMeta.id)).scalar() or 0

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
        recent_ids = [row[0] for row in db.query(MemoryMeta.id).order_by(
            MemoryMeta.created_at.desc()
        ).limit(safe_recent).all()]

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
                "created_at": _ensure_utc_iso(log.created_at),
            }
            for log in logs
        ]
    finally:
        db.close()


# ============ 记忆是否存在于关系库 ============

def delete_all_memory_meta() -> int:
    """清空关系库中的所有记忆元数据（危险操作，配合 Qdrant 全量清空使用）"""
    db = _get_db()
    try:
        # 先删除关联表数据
        db.execute(memory_categories.delete())
        # 删除变更日志
        deleted_logs = db.query(MemoryChangeLog).delete()
        # 删除所有记忆元数据
        deleted_count = db.query(MemoryMeta).delete()
        db.commit()
        logger.info(f"已清空关系库所有记忆元数据（删除 {deleted_count} 条记忆，{deleted_logs} 条变更日志）")
        return deleted_count
    except Exception as e:
        db.rollback()
        logger.error(f"清空关系库所有记忆元数据失败: {e}")
        raise
    finally:
        db.close()


def memory_exists_in_db(memory_id: str) -> bool:
    """检查记忆是否存在于关系库"""
    db = _get_db()
    try:
        return db.query(MemoryMeta.id).filter(MemoryMeta.id == memory_id).first() is not None
    finally:
        db.close()


def count_memories(
    user_id: str = None,
) -> int:
    """统计记忆数量"""
    db = _get_db()
    try:
        query = db.query(func.count(MemoryMeta.id))
        if user_id:
            query = query.filter(MemoryMeta.user_id == user_id)
        return query.scalar() or 0
    finally:
        db.close()
