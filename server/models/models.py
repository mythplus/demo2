"""
ORM 数据模型 — 对齐 mem0 云平台架构
MemoryMeta、Category 等表

注意：历史上这里还有 MemoryChangeLog（表 memory_change_logs_v2），
为消除与 log_service.memory_change_logs 的双轨存储，现已标记为废弃（B2 P0-1），
保留类定义仅用于向后兼容历史数据库，不再有任何写入/读取路径。
"""

import uuid
import datetime

from sqlalchemy import (
    Column, String, Text, DateTime, Boolean, Integer,
    ForeignKey, Index, Table, JSON,
)
from sqlalchemy.orm import relationship

from server.models.database import Base


def _utcnow():
    """获取当前 UTC 时间"""
    return datetime.datetime.now(datetime.timezone.utc)


def _ensure_utc_iso(dt) -> str:
    """将 datetime 序列化为带 UTC 时区的 ISO 格式字符串。
    兼容以下情况：
      1. PostgreSQL 驱动在某些配置下返回的 naive datetime（缺少 tzinfo）；
      2. 早期从 SQLite 迁移过来的历史数据，时区信息已丢失；
      3. 直接传入字符串或 None 的边界场景。
    确保输出始终带 +00:00 后缀，前端 new Date() 才能正确识别为 UTC。"""
    if dt is None:
        return ""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=datetime.timezone.utc)
    return dt.isoformat()


def _new_uuid():
    """生成新的 UUID 字符串"""
    return str(uuid.uuid4())


# ============ 多对多关联表 ============

memory_categories = Table(
    "memory_categories",
    Base.metadata,
    Column("memory_id", String(36), ForeignKey("memories_meta.id", ondelete="CASCADE"), primary_key=True),
    Column("category_id", String(36), ForeignKey("categories.id", ondelete="CASCADE"), primary_key=True),
    Index("idx_memory_category", "memory_id", "category_id"),
)


# ============ 数据模型 ============

class MemoryMeta(Base):
    """记忆元数据表 — 存储记忆的分类、时间戳等结构化信息。
    向量数据（embedding）仍存储在 Qdrant 中，此表通过 id 与 Qdrant 记录关联。
    对齐 mem0 云平台架构，不包含状态管理。"""
    __tablename__ = "memories_meta"

    id = Column(String(36), primary_key=True, comment="与 Qdrant 中的 point ID 一致")
    user_id = Column(String(100), nullable=False, index=True, comment="用户标识")
    agent_id = Column(String(100), nullable=True, index=True, comment="Agent 标识")
    run_id = Column(String(100), nullable=True, comment="运行标识")
    content = Column(Text, nullable=False, comment="记忆文本内容")
    hash = Column(String(64), nullable=True, comment="内容哈希（Mem0 生成）")
    metadata_ = Column("metadata", JSON, default=dict, comment="扩展元数据")
    created_at = Column(DateTime(timezone=True), default=_utcnow, nullable=False, index=True)
    updated_at = Column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow, nullable=True)

    # 关系
    categories = relationship("Category", secondary=memory_categories, back_populates="memories", lazy="selectin")

    __table_args__ = (
        Index("idx_memory_created", "created_at"),
    )

    def to_dict(self) -> dict:
        """转换为前端兼容的字典格式"""
        return {
            "id": self.id,
            "memory": self.content,
            "user_id": self.user_id or "",
            "agent_id": self.agent_id or "",
            "run_id": self.run_id or "",
            "hash": self.hash or "",
            "metadata": self.metadata_ or {},
            "categories": [c.name for c in self.categories] if self.categories else [],
            "created_at": _ensure_utc_iso(self.created_at),
            "updated_at": _ensure_utc_iso(self.updated_at),
        }


class Category(Base):
    """分类标签表 — 独立管理分类，通过多对多关联表与记忆关联。
    对齐官方 OpenMemory 的 Category 模型。"""
    __tablename__ = "categories"

    id = Column(String(36), primary_key=True, default=_new_uuid)
    name = Column(String(50), unique=True, nullable=False, index=True, comment="分类名称（英文标识）")
    description = Column(String(200), nullable=True, comment="分类描述")
    created_at = Column(DateTime(timezone=True), default=_utcnow, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow)

    # 关系
    memories = relationship("MemoryMeta", secondary=memory_categories, back_populates="categories")


class MemoryChangeLog(Base):
    """[已废弃 — B2 P0-1] 记忆内容变更日志表。

    历史原因：此类曾是与 log_service.memory_change_logs（原生 SQL 建表）并存的第二条写入路径，
    两者表名不同（memory_change_logs_v2 vs memory_change_logs），字段结构也不一致，
    但记录的是同一业务事件，导致数据双写、前端关联查询缺失。

    现有设计：所有记忆变更日志（ADD / UPDATE / DELETE / HARD_DELETE 等）统一由
    server.services.log_service 管理，写入表 memory_change_logs。

    保留本类定义仅为了：
      1. 保证历史数据库里已经存在的 memory_change_logs_v2 表不会突然缺失模型声明；
      2. 便于后续编写 alembic 迁移脚本 drop 此表。
    任何新代码 标 不允许 写入/查询此 ORM 类。
    """
    __tablename__ = "memory_change_logs_v2"

    id = Column(String(36), primary_key=True, default=_new_uuid)
    memory_id = Column(String(36), ForeignKey("memories_meta.id", ondelete="CASCADE"), nullable=False, index=True)
    event = Column(String(50), nullable=False, comment="事件类型: create/update/delete/import")
    old_content = Column(Text, nullable=True, comment="变更前内容")
    new_content = Column(Text, nullable=True, comment="变更后内容")
    old_categories = Column(JSON, default=list, comment="变更前分类列表")
    new_categories = Column(JSON, default=list, comment="变更后分类列表")
    created_at = Column(DateTime(timezone=True), default=_utcnow, nullable=False, index=True)

    __table_args__ = (
        Index("idx_changelog_memory", "memory_id"),
        Index("idx_changelog_time", "created_at"),
    )
