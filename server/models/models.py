"""
ORM 数据模型 — 对齐 OpenMemory 官方架构
Memory、Category、MemoryStatusHistory、MemoryAccessLog 等表
"""

import enum
import uuid
import datetime

from sqlalchemy import (
    Column, String, Text, DateTime, Enum, Boolean, Integer,
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


# ============ 枚举类型 ============

class MemoryState(str, enum.Enum):
    """记忆状态枚举 — 删除为物理删除，不再保留 deleted 状态"""
    active = "active"
    paused = "paused"
    archived = "archived"


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
    """记忆元数据表 — 存储记忆的状态、分类、时间戳等结构化信息。
    向量数据（embedding）仍存储在 Qdrant 中，此表通过 id 与 Qdrant 记录关联。
    对齐官方 OpenMemory 的 Memory 模型。"""
    __tablename__ = "memories_meta"

    id = Column(String(36), primary_key=True, comment="与 Qdrant 中的 point ID 一致")
    user_id = Column(String(100), nullable=False, index=True, comment="用户标识")
    agent_id = Column(String(100), nullable=True, index=True, comment="Agent 标识")
    run_id = Column(String(100), nullable=True, comment="运行标识")
    content = Column(Text, nullable=False, comment="记忆文本内容")
    hash = Column(String(64), nullable=True, comment="内容哈希（Mem0 生成）")
    metadata_ = Column("metadata", JSON, default=dict, comment="扩展元数据")
    state = Column(
        Enum(MemoryState, values_callable=lambda x: [e.value for e in x]),
        default=MemoryState.active,
        nullable=False,
        index=True,
        comment="记忆状态",
    )
    created_at = Column(DateTime(timezone=True), default=_utcnow, nullable=False, index=True)
    updated_at = Column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow, nullable=True)
    archived_at = Column(DateTime(timezone=True), nullable=True, index=True, comment="归档时间")
    deleted_at = Column(DateTime(timezone=True), nullable=True, index=True, comment="删除时间")

    # 关系
    categories = relationship("Category", secondary=memory_categories, back_populates="memories", lazy="selectin")
    status_history = relationship("MemoryStatusHistory", back_populates="memory", lazy="dynamic")

    __table_args__ = (
        Index("idx_memory_user_state", "user_id", "state"),
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
            "state": self.state.value if isinstance(self.state, MemoryState) else (self.state or "active"),
            "created_at": self.created_at.isoformat() if self.created_at else "",
            "updated_at": self.updated_at.isoformat() if self.updated_at else "",
            "archived_at": self.archived_at.isoformat() if self.archived_at else None,
            "deleted_at": self.deleted_at.isoformat() if self.deleted_at else None,
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


class MemoryStatusHistory(Base):
    """记忆状态变更历史表 — 记录每次状态变更的详细信息。
    对齐官方 OpenMemory 的 MemoryStatusHistory 模型。"""
    __tablename__ = "memory_status_history"

    id = Column(String(36), primary_key=True, default=_new_uuid)
    memory_id = Column(String(36), ForeignKey("memories_meta.id", ondelete="CASCADE"), nullable=False, index=True)
    old_state = Column(
        Enum(MemoryState, values_callable=lambda x: [e.value for e in x]),
        nullable=False,
        comment="变更前状态",
    )
    new_state = Column(
        Enum(MemoryState, values_callable=lambda x: [e.value for e in x]),
        nullable=False,
        comment="变更后状态",
    )
    changed_by = Column(String(100), nullable=True, comment="操作者标识")
    changed_at = Column(DateTime(timezone=True), default=_utcnow, nullable=False, index=True)
    reason = Column(String(500), nullable=True, comment="变更原因")

    # 关系
    memory = relationship("MemoryMeta", back_populates="status_history")

    __table_args__ = (
        Index("idx_history_memory_state", "memory_id", "new_state"),
        Index("idx_history_time", "changed_at"),
    )


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


class ArchivePolicy(Base):
    """归档策略表 — 定义自动归档规则。
    对齐官方 OpenMemory 的 ArchivePolicy 模型。"""
    __tablename__ = "archive_policies"

    id = Column(String(36), primary_key=True, default=_new_uuid)
    criteria_type = Column(String(50), nullable=False, index=True, comment="策略类型: user/category/global")
    criteria_value = Column(String(100), nullable=True, index=True, comment="策略值（如 user_id 或 category_name）")
    days_to_archive = Column(Integer, nullable=False, comment="多少天后自动归档")
    is_active = Column(Boolean, default=True, index=True)
    created_at = Column(DateTime(timezone=True), default=_utcnow, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow)

    __table_args__ = (
        Index("idx_policy_criteria", "criteria_type", "criteria_value"),
    )
