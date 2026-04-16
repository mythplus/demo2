"""
数据库引擎与会话管理 — SQLAlchemy + SQLite（可平滑切换 PostgreSQL）
对齐 OpenMemory 官方架构，将记忆元数据（state、categories、状态变更历史等）
从 Qdrant metadata 迁移到关系型数据库，Qdrant 只负责向量存储与语义搜索。
"""

import logging
from contextlib import contextmanager
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, declarative_base, Session

from server.config import MEMORY_DB_PATH

logger = logging.getLogger(__name__)

# SQLAlchemy 声明基类
Base = declarative_base()

# 数据库引擎（延迟初始化）
_engine = None
_SessionLocal = None


def _sqlite_pragma_on_connect(dbapi_conn, connection_record):
    """SQLite 连接时设置性能优化 PRAGMA"""
    cursor = dbapi_conn.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA synchronous=NORMAL")
    cursor.execute("PRAGMA busy_timeout=10000")
    cursor.execute("PRAGMA cache_size=-4000")
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


def get_engine():
    """获取数据库引擎（单例）"""
    global _engine
    if _engine is None:
        db_url = f"sqlite:///{MEMORY_DB_PATH}"
        _engine = create_engine(
            db_url,
            echo=False,
            pool_pre_ping=True,
            connect_args={"check_same_thread": False},
        )
        # SQLite 性能优化
        event.listen(_engine, "connect", _sqlite_pragma_on_connect)
        logger.info(f"数据库引擎已创建: {db_url}")
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
    """初始化数据库：创建所有表（如果不存在）"""
    # 导入模型以确保它们被注册到 Base.metadata
    from server.models import models as _models  # noqa: F401
    engine = get_engine()
    Base.metadata.create_all(bind=engine)
    logger.info("记忆元数据库表已初始化")


def close_db():
    """关闭数据库引擎"""
    global _engine, _SessionLocal
    if _engine is not None:
        _engine.dispose()
        _engine = None
        _SessionLocal = None
        logger.info("数据库引擎已关闭")
