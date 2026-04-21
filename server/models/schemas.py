"""
Pydantic 请求/响应模型定义
"""

from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, field_validator


# ============ 常量：字段长度限制（集中定义，便于调整和测试复用） ============
# 记忆正文长度上限：一条记忆通常是一两句话到一段话，2000 字已覆盖绝大多数场景；
# 若确实需要存更长内容，应拆分为多条或存原文摘要
MAX_MEMORY_CONTENT_LEN = 2000
# Playground 对话消息长度上限：用户可能粘贴长代码/日志，放宽到 20000
MAX_CHAT_MESSAGE_LEN = 20000
# 单次 AddMemory 的消息总条数上限
MAX_ADD_MESSAGES = 50
# 单次批量导入的条目数上限（CSV 场景友好）
MAX_BATCH_IMPORT_ITEMS = 500
# 单次批量删除的 ID 数上限
MAX_BATCH_DELETE_IDS = 500
# 单条记忆关联的分类标签上限
MAX_CATEGORIES_PER_MEMORY = 20


class MemoryMessage(BaseModel):
    role: str = Field(..., max_length=20)  # "user" | "assistant" | "system"
    # 聊天消息允许较长内容（粘贴日志/代码等）
    content: str = Field(..., max_length=MAX_CHAT_MESSAGE_LEN)

    @field_validator("role")
    @classmethod
    def _check_role(cls, v: str) -> str:
        allowed = {"user", "assistant", "system", "tool"}
        if v not in allowed:
            raise ValueError(f"role 必须是 {allowed} 之一，收到: {v}")
        return v

class AddMemoryRequest(BaseModel):
    messages: List[MemoryMessage] = Field(..., max_length=MAX_ADD_MESSAGES, min_length=1)
    user_id: Optional[str] = Field(None, max_length=100)
    agent_id: Optional[str] = Field(None, max_length=100)
    run_id: Optional[str] = Field(None, max_length=100)
    metadata: Optional[Dict[str, Any]] = None
    categories: Optional[List[str]] = Field(None, max_length=MAX_CATEGORIES_PER_MEMORY)
    infer: Optional[bool] = True  # True: AI 自动提取关键记忆（可能拆分为多条）; False: 原文整条存储
    auto_categorize: Optional[bool] = True  # True: 未手动选择标签时由 AI 自动分类

    @field_validator("messages")
    @classmethod
    def _check_total_content_size(cls, v: List[MemoryMessage]) -> List[MemoryMessage]:
        # 全部消息拼接后的总字符上限，避免单请求撑爆 LLM 上下文
        MAX_TOTAL = 100_000
        total = sum(len(m.content or "") for m in v)
        if total > MAX_TOTAL:
            raise ValueError(f"messages 总字符数 {total} 超过上限 {MAX_TOTAL}")
        return v


class SearchMemoryRequest(BaseModel):
    query: str = Field(..., max_length=500)  # 搜索查询最大 500 字符
    user_id: Optional[str] = Field(None, max_length=100)
    agent_id: Optional[str] = Field(None, max_length=100)
    run_id: Optional[str] = Field(None, max_length=100)
    limit: Optional[int] = Field(10, ge=1, le=100)  # 返回数量限制 1-100


class UpdateMemoryRequest(BaseModel):
    text: Optional[str] = Field(None, max_length=MAX_MEMORY_CONTENT_LEN)
    metadata: Optional[Dict[str, Any]] = None
    categories: Optional[List[str]] = Field(None, max_length=MAX_CATEGORIES_PER_MEMORY)
    auto_categorize: Optional[bool] = False  # True: 对当前内容重新 AI 自动分类

class BatchImportItem(BaseModel):
    """批量导入中的单条记忆"""
    content: str = Field(..., max_length=MAX_MEMORY_CONTENT_LEN, min_length=1)
    user_id: Optional[str] = Field(None, max_length=100)
    metadata: Optional[Dict[str, Any]] = None
    categories: Optional[List[str]] = Field(None, max_length=MAX_CATEGORIES_PER_MEMORY)

class BatchImportRequest(BaseModel):
    """批量导入请求"""
    items: List[BatchImportItem] = Field(..., max_length=MAX_BATCH_IMPORT_ITEMS, min_length=1)
    default_user_id: Optional[str] = Field(None, max_length=100)
    infer: Optional[bool] = False  # 默认原文存储
    auto_categorize: Optional[bool] = True  # 默认 AI 自动分类


class BatchImportResultItem(BaseModel):
    index: int
    success: bool
    id: Optional[str] = None
    memory: Optional[str] = None
    error: Optional[str] = None


class BatchImportResponse(BaseModel):
    total: int
    success: int
    failed: int
    results: List[BatchImportResultItem]


class BatchDeleteRequest(BaseModel):
    """批量删除请求"""
    memory_ids: List[str] = Field(
        ...,
        max_length=MAX_BATCH_DELETE_IDS,
        min_length=1,
        description=f"要删除的记忆 ID 列表，最多 {MAX_BATCH_DELETE_IDS} 条",
    )


class BatchDeleteResponse(BaseModel):
    """批量删除响应"""
    total: int
    success: int
    failed: int
    results: List[Dict[str, Any]]


class GraphSearchRequest(BaseModel):
    query: str = Field(..., max_length=500)  # 图谱搜索查询最大 500 字符
    user_id: Optional[str] = Field(None, max_length=100)
    limit: Optional[int] = Field(20, ge=1, le=200)  # 返回数量限制 1-200
