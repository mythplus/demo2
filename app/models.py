"""
Mem0 Dashboard 后端 - Pydantic 请求/响应模型
"""
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


class MemoryMessage(BaseModel):
    role: str = Field(..., max_length=20)
    content: str = Field(..., max_length=10000)


class AddMemoryRequest(BaseModel):
    messages: List[MemoryMessage] = Field(..., max_length=50)
    user_id: Optional[str] = Field(None, max_length=100)
    agent_id: Optional[str] = Field(None, max_length=100)
    run_id: Optional[str] = Field(None, max_length=100)
    metadata: Optional[Dict[str, Any]] = None
    categories: Optional[List[str]] = None
    state: Optional[str] = "active"
    infer: Optional[bool] = True
    auto_categorize: Optional[bool] = True


class SearchMemoryRequest(BaseModel):
    query: str = Field(..., max_length=500)
    user_id: Optional[str] = Field(None, max_length=100)
    agent_id: Optional[str] = Field(None, max_length=100)
    run_id: Optional[str] = Field(None, max_length=100)
    limit: Optional[int] = Field(10, ge=1, le=100)


class UpdateMemoryRequest(BaseModel):
    text: Optional[str] = Field(None, max_length=10000)
    metadata: Optional[Dict[str, Any]] = None
    categories: Optional[List[str]] = Field(None, max_length=20)
    state: Optional[str] = Field(None, max_length=20)
    auto_categorize: Optional[bool] = False


class BatchImportItem(BaseModel):
    content: str = Field(..., max_length=10000)
    user_id: Optional[str] = Field(None, max_length=100)
    metadata: Optional[Dict[str, Any]] = None
    categories: Optional[List[str]] = Field(None, max_length=20)
    state: Optional[str] = Field("active", max_length=20)


class BatchImportRequest(BaseModel):
    items: List[BatchImportItem] = Field(..., max_length=100)
    default_user_id: Optional[str] = Field(None, max_length=100)
    infer: Optional[bool] = False
    auto_categorize: Optional[bool] = True


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
    memory_ids: List[str] = Field(..., max_length=100)


class BatchDeleteResponse(BaseModel):
    total: int
    success: int
    failed: int
    results: List[Dict[str, Any]]


class GraphSearchRequest(BaseModel):
    query: str = Field(..., max_length=500)
    user_id: Optional[str] = Field(None, max_length=100)
    limit: Optional[int] = Field(20, ge=1, le=200)
