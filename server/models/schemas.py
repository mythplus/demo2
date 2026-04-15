"""
Pydantic 请求/响应模型定义
"""

from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, field_validator


class MemoryMessage(BaseModel):
    role: str = Field(..., max_length=20)  # "user" | "assistant" | "system"
    content: str = Field(..., max_length=10000)  # 单条消息最大 10000 字符


class AddMemoryRequest(BaseModel):
    messages: List[MemoryMessage] = Field(..., max_length=50)  # 单次最多 50 条消息
    user_id: Optional[str] = Field(None, max_length=100)
    agent_id: Optional[str] = Field(None, max_length=100)
    run_id: Optional[str] = Field(None, max_length=100)
    metadata: Optional[Dict[str, Any]] = None
    categories: Optional[List[str]] = None
    infer: Optional[bool] = True  # True: AI 自动提取关键记忆（可能拆分为多条）; False: 原文整条存储
    auto_categorize: Optional[bool] = True  # True: 未手动选择标签时由 AI 自动分类


class SearchMemoryRequest(BaseModel):
    query: str = Field(..., max_length=500)  # 搜索查询最大 500 字符
    user_id: Optional[str] = Field(None, max_length=100)
    agent_id: Optional[str] = Field(None, max_length=100)
    run_id: Optional[str] = Field(None, max_length=100)
    limit: Optional[int] = Field(10, ge=1, le=100)  # 返回数量限制 1-100


class UpdateMemoryRequest(BaseModel):
    text: Optional[str] = Field(None, max_length=10000)  # 更新内容最大 10000 字符
    metadata: Optional[Dict[str, Any]] = None
    categories: Optional[List[str]] = Field(None, max_length=20)  # 最多 20 个分类
    auto_categorize: Optional[bool] = False  # True: 对当前内容重新 AI 自动分类


class BatchImportItem(BaseModel):
    """批量导入中的单条记忆"""
    content: str = Field(..., max_length=10000)  # 单条内容最大 10000 字符
    user_id: Optional[str] = Field(None, max_length=100)
    metadata: Optional[Dict[str, Any]] = None
    categories: Optional[List[str]] = Field(None, max_length=20)


class BatchImportRequest(BaseModel):
    """批量导入请求"""
    items: List[BatchImportItem] = Field(..., max_length=100)  # 单次最多导入 100 条
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
    memory_ids: List[str] = Field(..., max_length=100, description="要删除的记忆 ID 列表，最多 100 条")


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
