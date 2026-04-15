"""
数据迁移脚本 — 将 Qdrant 中现有记忆的 state/categories 等元数据迁移到关系库
运行方式: python -m server.scripts.migrate_to_relational_db
"""

import sys
import os
import logging
from datetime import datetime, timezone

# 确保项目根目录在 sys.path 中
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from server.config import setup_logging
setup_logging()

logger = logging.getLogger(__name__)


def migrate():
    """从 Qdrant 读取所有记忆，迁移到关系库"""
    from server.models.database import init_db, get_session_factory
    from server.models.models import MemoryMeta, Category, memory_categories
    from server.services.memory_service import iter_memories_raw, get_memory
    from server.config import VALID_CATEGORIES

    # 初始化数据库表
    init_db()
    logger.info("数据库表已初始化")

    # 初始化 Mem0（确保 Qdrant 可用）
    get_memory()
    logger.info("Mem0 实例已初始化")

    SessionLocal = get_session_factory()
    db = SessionLocal()

    try:
        # 预创建所有合法分类
        existing_cats = {c.name: c for c in db.query(Category).all()}
        for cat_name in VALID_CATEGORIES:
            if cat_name not in existing_cats:
                cat = Category(name=cat_name, description=f"预创建分类: {cat_name}")
                db.add(cat)
                existing_cats[cat_name] = cat
        db.commit()
        # 刷新分类映射
        existing_cats = {c.name: c for c in db.query(Category).all()}
        logger.info(f"分类表已初始化，共 {len(existing_cats)} 个分类")

        # 统计
        total = 0
        migrated = 0
        skipped = 0
        errors = 0

        # 遍历 Qdrant 中所有记忆（不做任何过滤）
        logger.info("开始从 Qdrant 遍历记忆...")
        for memory in iter_memories_raw(order_by="created_at", order_direction="asc"):
            total += 1
            mid = memory.get("id", "")
            if not mid:
                errors += 1
                continue

            # 检查是否已迁移
            existing = db.query(MemoryMeta.id).filter(MemoryMeta.id == mid).first()
            if existing:
                skipped += 1
                if total % 50 == 0:
                    logger.info(f"进度: {total} 条已扫描, {migrated} 条已迁移, {skipped} 条已跳过")
                continue

            try:
                # 解析时间
                created_at = None
                if memory.get("created_at"):
                    try:
                        created_at = datetime.fromisoformat(
                            str(memory["created_at"]).replace("Z", "+00:00")
                        )
                        if created_at.tzinfo is None:
                            created_at = created_at.replace(tzinfo=timezone.utc)
                    except (ValueError, TypeError):
                        created_at = datetime.now(timezone.utc)

                updated_at = None
                if memory.get("updated_at"):
                    try:
                        updated_at = datetime.fromisoformat(
                            str(memory["updated_at"]).replace("Z", "+00:00")
                        )
                        if updated_at.tzinfo is None:
                            updated_at = updated_at.replace(tzinfo=timezone.utc)
                    except (ValueError, TypeError):
                        pass

                # 创建记忆元数据记录
                meta = MemoryMeta(
                    id=mid,
                    user_id=memory.get("user_id", ""),
                    agent_id=memory.get("agent_id", ""),
                    run_id=memory.get("run_id", ""),
                    content=memory.get("memory", ""),
                    hash=memory.get("hash", ""),
                    metadata_=memory.get("metadata", {}),
                    created_at=created_at or datetime.now(timezone.utc),
                    updated_at=updated_at,
                )

                # 关联分类
                categories = memory.get("categories", [])
                for cat_name in categories:
                    if cat_name in existing_cats:
                        meta.categories.append(existing_cats[cat_name])

                db.add(meta)

                migrated += 1

                # 每 50 条提交一次
                if migrated % 50 == 0:
                    db.commit()
                    logger.info(f"进度: {total} 条已扫描, {migrated} 条已迁移, {skipped} 条已跳过")

            except Exception as e:
                errors += 1
                logger.warning(f"迁移记忆 {mid} 失败: {e}")
                db.rollback()

        # 最终提交
        db.commit()
        logger.info("=" * 50)
        logger.info(f"迁移完成！")
        logger.info(f"  总扫描: {total} 条")
        logger.info(f"  已迁移: {migrated} 条")
        logger.info(f"  已跳过（已存在）: {skipped} 条")
        logger.info(f"  失败: {errors} 条")
        logger.info("=" * 50)

    except Exception as e:
        db.rollback()
        logger.error(f"迁移过程出错: {e}", exc_info=True)
        raise
    finally:
        db.close()


if __name__ == "__main__":
    migrate()
