"""
ORM 数据模型 — 对齐 mem0 云平台架构
Memory、Category、MemoryChangeLog 等表
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
            "created_at": self.created_at.isoformat() if self.created_at else "",
            "updated_at": self.updated_at.isoformat() if self.updated_at else "",
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
    """记忆内容变更日志表 — 记录记忆文本和分类的修改历史。
    替代原有 SQLite memory_change_logs 表，纳入 SQLAlchemy 统一管理。"""
    __tablename__ = "memory_change_logs_v2"

    id = Column(String(36), primary_key=True, default=_new_uuid)
    memory_id = Column(String(36), ForeignKey("memories_meta.id", ondelete="CASCADE"), nullable=False, index=True)
    event = Column(String(50), nullable=False, comment="事件类型: create/update/delete/import/restore")
    old_content = Column(Text, nullable=True, comment="变更前内容")
    new_content = Column(Text, nullable=True, comment="变更后内容")
    old_categories = Column(JSON, default=list, comment="变更前分类列表")
    new_categories = Column(JSON, default=list, comment="变更后分类列表")
    created_at = Column(DateTime(timezone=True), default=_utcnow, nullable=False, index=True)

    __table_args__ = (
        Index("idx_changelog_memory", "memory_id"),
        Index("idx_changelog_time", "created_at"),
    )
