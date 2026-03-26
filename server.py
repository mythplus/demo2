"""
Mem0 Dashboard 后端 API 服务
使用 FastAPI 实现，Qdrant 采用本地文件模式（无需额外部署向量数据库）
"""

import os
import logging
from typing import Optional, List, Dict, Any
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ============ Qdrant 本地文件存储路径 ============
# 使用项目目录下的 qdrant_data 文件夹，基于当前文件位置动态计算
QDRANT_DATA_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "qdrant_data")

# ============ Mem0 配置（方案二：本地文件模式） ============
MEM0_CONFIG = {
    "vector_store": {
        "provider": "qdrant",
        "config": {
            "collection_name": "mem0",
            "embedding_model_dims": 768,
            "path": QDRANT_DATA_PATH,
            "on_disk": True,  # 持久化存储，重启不丢数据
        },
    },
    # LLM 配置（默认使用 OpenAI，需设置 OPENAI_API_KEY 环境变量）
    "llm": {
        "provider": "ollama",
        "config": {
            "model": "qwen2.5:7b",
            "ollama_base_url": "http://9.134.231.238:11434",
            "temperature": 0.1,
        },
    },
    "embedder": {
        "provider": "ollama",
        "config": {
            "model": "nomic-embed-text",
            "ollama_base_url": "http://9.134.231.238:11434",
        },
    },
    "version": "v1.1",
}

# ============ 全局 Memory 实例 ============
memory_instance = None


def get_memory():
    """获取 Mem0 Memory 实例（延迟初始化）"""
    global memory_instance
    if memory_instance is None:
        from mem0 import Memory
        logger.info(f"正在初始化 Mem0，Qdrant 数据目录: {QDRANT_DATA_PATH}")
        memory_instance = Memory.from_config(MEM0_CONFIG)
        logger.info("Mem0 初始化完成")
    return memory_instance


# ============ 请求/响应模型 ============

class MemoryMessage(BaseModel):
    role: str  # "user" | "assistant" | "system"
    content: str


class AddMemoryRequest(BaseModel):
    messages: List[MemoryMessage]
    user_id: Optional[str] = None
    agent_id: Optional[str] = None
    run_id: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class SearchMemoryRequest(BaseModel):
    query: str
    user_id: Optional[str] = None
    agent_id: Optional[str] = None
    run_id: Optional[str] = None
    limit: Optional[int] = 10


class UpdateMemoryRequest(BaseModel):
    text: str


# ============ 应用生命周期 ============

@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用启动时初始化 Mem0"""
    logger.info("=" * 50)
    logger.info("Mem0 Dashboard 后端服务启动中...")
    logger.info(f"Qdrant 存储模式: 本地文件模式 (on_disk)")
    logger.info(f"Qdrant 数据目录: {QDRANT_DATA_PATH}")
    logger.info("=" * 50)
    # 预初始化 Memory 实例
    get_memory()
    yield
    logger.info("Mem0 Dashboard 后端服务已关闭")


# ============ FastAPI 应用 ============

app = FastAPI(
    title="Mem0 Dashboard API",
    description="Mem0 记忆管理后端服务（Qdrant 本地文件模式）",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS 配置（允许前端跨域访问）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============ 健康检查 ============

@app.get("/")
async def health_check():
    """健康检查端点"""
    return {"status": "ok", "message": "Mem0 Dashboard API 运行中"}


# ============ 记忆 CRUD 接口 ============

@app.post("/v1/memories/")
async def add_memory(request: AddMemoryRequest):
    """添加记忆"""
    try:
        m = get_memory()
        messages = [{"role": msg.role, "content": msg.content} for msg in request.messages]

        kwargs = {}
        if request.user_id:
            kwargs["user_id"] = request.user_id
        if request.agent_id:
            kwargs["agent_id"] = request.agent_id
        if request.run_id:
            kwargs["run_id"] = request.run_id
        if request.metadata:
            kwargs["metadata"] = request.metadata

        result = m.add(messages=messages, **kwargs)
        return result
    except Exception as e:
        logger.error(f"添加记忆失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/v1/memories/")
async def get_memories(user_id: Optional[str] = Query(None)):
    """获取所有记忆（可按 user_id 筛选）"""
    try:
        m = get_memory()
        if user_id:
            result = m.get_all(user_id=user_id)
        else:
            result = m.get_all()

        # mem0 返回的可能是 dict 或 list，统一处理
        if isinstance(result, dict) and "results" in result:
            return result["results"]
        if isinstance(result, list):
            return result
        return result
    except Exception as e:
        logger.error(f"获取记忆失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/v1/memories/{memory_id}/")
async def get_memory_by_id(memory_id: str):
    """获取单条记忆"""
    try:
        m = get_memory()
        result = m.get(memory_id)
        if not result:
            raise HTTPException(status_code=404, detail="记忆不存在")
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取记忆失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.put("/v1/memories/{memory_id}/")
async def update_memory(memory_id: str, request: UpdateMemoryRequest):
    """更新记忆"""
    try:
        m = get_memory()
        result = m.update(memory_id=memory_id, data=request.text)
        return result
    except Exception as e:
        logger.error(f"更新记忆失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/v1/memories/{memory_id}/")
async def delete_memory_by_id(memory_id: str):
    """删除单条记忆"""
    try:
        m = get_memory()
        m.delete(memory_id=memory_id)
        return {"message": "记忆已删除"}
    except Exception as e:
        logger.error(f"删除记忆失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/v1/memories/")
async def delete_all_memories(user_id: Optional[str] = Query(None)):
    """删除用户的所有记忆"""
    try:
        m = get_memory()
        if user_id:
            m.delete_all(user_id=user_id)
            return {"message": f"用户 {user_id} 的所有记忆已删除"}
        else:
            m.delete_all()
            return {"message": "所有记忆已删除"}
    except Exception as e:
        logger.error(f"删除记忆失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============ 搜索接口 ============

@app.post("/v1/memories/search/")
async def search_memories(request: SearchMemoryRequest):
    """语义搜索记忆"""
    try:
        m = get_memory()
        kwargs = {"query": request.query}
        if request.user_id:
            kwargs["user_id"] = request.user_id
        if request.agent_id:
            kwargs["agent_id"] = request.agent_id
        if request.run_id:
            kwargs["run_id"] = request.run_id
        if request.limit:
            kwargs["limit"] = request.limit

        result = m.search(**kwargs)

        # 统一返回格式
        if isinstance(result, dict) and "results" in result:
            return result
        if isinstance(result, list):
            return {"results": result}
        return {"results": result}
    except Exception as e:
        logger.error(f"搜索记忆失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============ 历史记录接口 ============

@app.get("/v1/memories/history/{memory_id}/")
async def get_memory_history(memory_id: str):
    """获取记忆的修改历史"""
    try:
        m = get_memory()
        result = m.history(memory_id=memory_id)
        if isinstance(result, list):
            return result
        return result
    except Exception as e:
        logger.error(f"获取记忆历史失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============ 启动入口 ============

if __name__ == "__main__":
    # 默认监听 8080 端口，与前端 .env.local 中配置一致
    port = int(os.environ.get("MEM0_PORT", 8080))
    logger.info(f"启动 Mem0 API 服务，端口: {port}")
    uvicorn.run(
        "server:app",
        host="0.0.0.0",
        port=port,
        reload=True,
        reload_includes=["*.py"],  # 只监控 .py 文件变化
        reload_excludes=["qdrant_data/**", "*.log"],  # 排除 Qdrant 数据目录和日志文件
        log_level="info",
    )
