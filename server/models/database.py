"""
数据库引擎与会话管理 — SQLAlchemy + PostgreSQL
对齐 OpenMemory 官方架构，将记忆元数据（state、categories、状态变更历史等）
从 Qdrant metadata 迁移到关系型数据库，Qdrant 只负责向量存储与语义搜索。
"""

import logging
from contextlib import contextmanager
from sqlalchemy import create_engine, inspect
from sqlalchemy.engine.url import make_url
from sqlalchemy.orm import sessionmaker, declarative_base, Session

from server.config import DATABASE_URL, IS_PRODUCTION

logger = logging.getLogger(__name__)


def _safe_db_url_for_log(url: str) -> str:
    """对 DATABASE_URL 做脱敏后再打日志。
    用 SQLAlchemy 官方 URL 解析，比手工 split('@') 鲁棒，
    避免密码里含特殊字符或 URL 拼接异常时把真实密码写进日志。"""
    try:
        return make_url(url).render_as_string(hide_password=True)
    except Exception:
        return url.rsplit("@", 1)[-1] if "@" in url else "<unparsable-url>"

# SQLAlchemy 声明基类
Base = declarative_base()

# 数据库引擎（延迟初始化）
_engine = None
_SessionLocal = None


def get_engine():
    """获取数据库引擎（单例）"""
    global _engine
    if _engine is None:
        _engine = create_engine(
            DATABASE_URL,
            echo=False,
            pool_pre_ping=True,
            pool_size=10,
            max_overflow=20,
        )
        logger.info(f"数据库引擎已创建: {_safe_db_url_for_log(DATABASE_URL)}")
    return _engine


def get_session_factory():
    """获取会话工厂（单例）"""
    global _SessionLocal
    if _SessionLocal is None:
        _SessionLocal = sessionmaker(
            bind=get_engine(),
            autocommit=False,
            autoflush=False,
            expire_on_commit=False,
        )
    return _SessionLocal


def get_db() -> Session:
    """获取数据库会话（需调用方手动 close，推荐使用 get_db_session() 上下文管理器）"""
    SessionLocal = get_session_factory()
    return SessionLocal()


@contextmanager
def get_db_session():
    """获取数据库会话的上下文管理器，自动管理 commit/rollback/close。
    用法：
        with get_db_session() as db:
            db.query(...)
    """
    db = get_db()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def init_db():
    """初始化数据库。

    P0-2 整改后行为：
    - 开发/测试环境：仍走 `create_all()` 快速起服务，不做迁移。
    - 生产环境（MEM0_ENV=production）：**禁止** 自动 create_all / 自动迁移，
      只做"schema 健康检查"（验证 `memories_meta` 是否存在），
      迁移由部署流水线显式执行 `alembic upgrade head`。

    这样保证：
    1. 新增列等结构变更永远走 alembic，不会出现"ORM 改了但线上没建字段"的静默 bug；
    2. 不同服务实例启动时也不会并发 create_all 抢锁；
    3. 开发体验保持一致，快速迭代不受影响。
    """
    # 导入模型以确保它们被注册到 Base.metadata
    from server.models import models as _models  # noqa: F401
    engine = get_engine()

    if IS_PRODUCTION:
        # 生产：只检查关键表是否已就位，缺失则提示由流水线跑迁移
        inspector = inspect(engine)
        required_tables = {"memories_meta", "categories", "memory_categories"}
        existing = set(inspector.get_table_names())
        missing = required_tables - existing
        if missing:
            raise RuntimeError(
                "生产环境检测到数据库缺少必要表: "
                + ", ".join(sorted(missing))
                + "。请先执行 `alembic upgrade head` 再启动服务。"
            )
        logger.info("生产环境：数据库 schema 健康检查通过，迁移由流水线管理（alembic upgrade head）")
    else:
        # 开发/测试：裸建表，保持快速迭代体验
        Base.metadata.create_all(bind=engine)
        logger.info(
            "开发模式：记忆元数据库表已通过 create_all 初始化。"
            "注意：新增/修改列时 create_all 不会改既有表，请同步跑 `alembic revision --autogenerate` + `alembic upgrade head`。"
        )


def close_db():
    """关闭数据库引擎"""
    global _engine, _SessionLocal
    if _engine is not None:
        _engine.dispose()
        _engine = None
        _SessionLocal = None
        logger.info("数据库引擎已关闭")

