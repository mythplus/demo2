"""
Mem0 Dashboard 后端 API 服务
使用 FastAPI 实现，Qdrant 采用本地文件模式（无需额外部署向量数据库）
"""

import os
import logging
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
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

# ============ 分类和状态常量 ============
VALID_CATEGORIES = {"personal", "work", "health", "finance", "travel", "education", "preferences", "relationships"}
VALID_STATES = {"active", "paused", "archived", "deleted"}

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


def extract_memory_fields(payload: dict) -> dict:
    """从 Qdrant payload 中提取记忆字段，包括 categories 和 state"""
    metadata = payload.get("metadata", {}) or {}
    return {
        "id": str(payload.get("id", "")),
        "memory": payload.get("data", payload.get("memory", "")),
        "user_id": payload.get("user_id", ""),
        "agent_id": payload.get("agent_id", ""),
        "run_id": payload.get("run_id", ""),
        "hash": payload.get("hash", ""),
        "metadata": {k: v for k, v in metadata.items() if k not in ("categories", "state")},
        "categories": metadata.get("categories", []),
        "state": metadata.get("state", "active"),
        "created_at": payload.get("created_at", ""),
        "updated_at": payload.get("updated_at", ""),
    }


def format_record(record) -> dict:
    """将 Qdrant record 转换为前端格式"""
    payload = record.payload or {}
    result = extract_memory_fields(payload)
    result["id"] = str(record.id)
    return result


def format_mem0_result(item: dict) -> dict:
    """将 Mem0 返回的记忆对象格式化，提取 categories 和 state"""
    metadata = item.get("metadata", {}) or {}
    return {
        "id": item.get("id", ""),
        "memory": item.get("memory", ""),
        "user_id": item.get("user_id", ""),
        "agent_id": item.get("agent_id", ""),
        "run_id": item.get("run_id", ""),
        "hash": item.get("hash", ""),
        "metadata": {k: v for k, v in metadata.items() if k not in ("categories", "state")},
        "categories": metadata.get("categories", []),
        "state": metadata.get("state", "active"),
        "created_at": item.get("created_at", ""),
        "updated_at": item.get("updated_at", ""),
    }


def apply_filters(memories: list, categories: list = None, state: str = None,
                   date_from: str = None, date_to: str = None, search: str = None) -> list:
    """对记忆列表应用多维筛选"""
    filtered = memories

    # 按状态筛选
    if state:
        filtered = [m for m in filtered if m.get("state", "active") == state]

    # 按分类筛选（包含任一分类即匹配）
    if categories:
        cat_set = set(categories)
        filtered = [m for m in filtered if set(m.get("categories", [])) & cat_set]

    # 按时间范围筛选
    if date_from:
        try:
            from_dt = datetime.fromisoformat(date_from.replace("Z", "+00:00"))
            filtered = [m for m in filtered if m.get("created_at") and
                        datetime.fromisoformat(str(m["created_at"]).replace("Z", "+00:00")) >= from_dt]
        except (ValueError, TypeError):
            pass

    if date_to:
        try:
            to_dt = datetime.fromisoformat(date_to.replace("Z", "+00:00"))
            filtered = [m for m in filtered if m.get("created_at") and
                        datetime.fromisoformat(str(m["created_at"]).replace("Z", "+00:00")) <= to_dt]
        except (ValueError, TypeError):
            pass

    # 文本搜索
    if search:
        keyword = search.lower()
        filtered = [m for m in filtered if
                    keyword in (m.get("memory", "") or "").lower() or
                    keyword in (m.get("user_id", "") or "").lower() or
                    keyword in (m.get("id", "") or "").lower()]

    return filtered


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
    categories: Optional[List[str]] = None
    state: Optional[str] = "active"


class SearchMemoryRequest(BaseModel):
    query: str
    user_id: Optional[str] = None
    agent_id: Optional[str] = None
    run_id: Optional[str] = None
    limit: Optional[int] = 10


class UpdateMemoryRequest(BaseModel):
    text: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    categories: Optional[List[str]] = None
    state: Optional[str] = None


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
    version="1.1.0",
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


# ============ 辅助函数：获取所有记忆 ============

def _get_all_memories_raw() -> list:
    """获取所有记忆（原始 Qdrant 查询），返回格式化后的列表"""
    m = get_memory()
    try:
        collection_name = MEM0_CONFIG["vector_store"]["config"]["collection_name"]
        qdrant_client = m.vector_store.client
        records, _ = qdrant_client.scroll(
            collection_name=collection_name,
            limit=200,
            with_payload=True,
            with_vectors=False,
        )
        return [format_record(record) for record in records]
    except Exception as e:
        logger.warning(f"Qdrant 直接查询失败: {e}")
        return []


# ============ 记忆 CRUD 接口 ============

@app.post("/v1/memories/")
async def add_memory(request: AddMemoryRequest):
    """添加记忆（支持 categories 和 state）"""
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

        # 合并 metadata，将 categories 和 state 写入 metadata
        final_metadata = dict(request.metadata or {})
        if request.categories:
            # 校验分类
            valid_cats = [c for c in request.categories if c in VALID_CATEGORIES]
            if valid_cats:
                final_metadata["categories"] = valid_cats
        if request.state and request.state in VALID_STATES:
            final_metadata["state"] = request.state

        if final_metadata:
            kwargs["metadata"] = final_metadata

        result = m.add(messages=messages, **kwargs)
        return result
    except Exception as e:
        logger.error(f"添加记忆失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/v1/memories/")
async def get_memories(
    user_id: Optional[str] = Query(None),
    categories: Optional[str] = Query(None, description="逗号分隔的分类列表"),
    state: Optional[str] = Query(None, description="记忆状态: active/paused/archived/deleted"),
    date_from: Optional[str] = Query(None, description="起始日期 ISO 格式"),
    date_to: Optional[str] = Query(None, description="截止日期 ISO 格式"),
    search: Optional[str] = Query(None, description="文本搜索关键词"),
):
    """获取所有记忆（支持多维筛选）"""
    try:
        m = get_memory()
        if user_id:
            # 按用户筛选
            result = m.get_all(user_id=user_id)
            # mem0 返回的可能是 dict 或 list
            if isinstance(result, dict) and "results" in result:
                memories = [format_mem0_result(item) for item in result["results"]]
            elif isinstance(result, list):
                memories = [format_mem0_result(item) for item in result]
            else:
                memories = []
        else:
            memories = _get_all_memories_raw()

        # 应用多维筛选
        cat_list = [c.strip() for c in categories.split(",") if c.strip()] if categories else None
        memories = apply_filters(
            memories,
            categories=cat_list,
            state=state,
            date_from=date_from,
            date_to=date_to,
            search=search,
        )

        return memories
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
        return format_mem0_result(result) if isinstance(result, dict) else result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取记忆失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.put("/v1/memories/{memory_id}/")
async def update_memory(memory_id: str, request: UpdateMemoryRequest):
    """更新记忆（支持 text、metadata、categories、state 更新）"""
    try:
        m = get_memory()

        # 如果有文本更新
        if request.text:
            result = m.update(memory_id=memory_id, data=request.text)
        else:
            result = {"message": "metadata updated"}

        # 如果有 categories 或 state 更新，需要更新 Qdrant payload 中的 metadata
        if request.categories is not None or request.state is not None or request.metadata is not None:
            try:
                collection_name = MEM0_CONFIG["vector_store"]["config"]["collection_name"]
                qdrant_client = m.vector_store.client

                # 先获取当前 payload
                points = qdrant_client.retrieve(
                    collection_name=collection_name,
                    ids=[memory_id],
                    with_payload=True,
                )
                if points:
                    current_payload = points[0].payload or {}
                    current_metadata = dict(current_payload.get("metadata", {}) or {})

                    # 更新 categories
                    if request.categories is not None:
                        valid_cats = [c for c in request.categories if c in VALID_CATEGORIES]
                        current_metadata["categories"] = valid_cats

                    # 更新 state
                    if request.state is not None and request.state in VALID_STATES:
                        current_metadata["state"] = request.state

                    # 合并其他 metadata
                    if request.metadata is not None:
                        for k, v in request.metadata.items():
                            if k not in ("categories", "state"):
                                current_metadata[k] = v

                    # 写回 Qdrant
                    qdrant_client.set_payload(
                        collection_name=collection_name,
                        payload={"metadata": current_metadata},
                        points=[memory_id],
                    )
            except Exception as meta_err:
                logger.warning(f"更新 metadata 失败: {meta_err}")

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
            # 无 user_id 时，复用 Mem0 内部的 Qdrant 客户端清空集合
            try:
                from qdrant_client.models import PointIdsList
                collection_name = MEM0_CONFIG["vector_store"]["config"]["collection_name"]
                qdrant_client = m.vector_store.client
                records, _ = qdrant_client.scroll(
                    collection_name=collection_name,
                    limit=1000,
                    with_payload=False,
                    with_vectors=False,
                )
                if records:
                    ids = [record.id for record in records]
                    qdrant_client.delete(
                        collection_name=collection_name,
                        points_selector=PointIdsList(points=ids),
                    )
                return {"message": "所有记忆已删除"}
            except Exception as qdrant_err:
                logger.error(f"Qdrant 直接删除失败: {qdrant_err}")
                raise HTTPException(status_code=500, detail=str(qdrant_err))
    except HTTPException:
        raise
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

        # 统一返回格式并附加 categories/state
        if isinstance(result, dict) and "results" in result:
            formatted = [format_mem0_result(item) for item in result["results"]]
            # 保留 score 字段
            for i, item in enumerate(result["results"]):
                if "score" in item:
                    formatted[i]["score"] = item["score"]
            return {"results": formatted}
        if isinstance(result, list):
            formatted = [format_mem0_result(item) for item in result]
            for i, item in enumerate(result):
                if "score" in item:
                    formatted[i]["score"] = item["score"]
            return {"results": formatted}
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


# ============ 统计接口 ============

@app.get("/v1/stats/")
async def get_stats():
    """获取统计数据（分类分布、状态分布、每日趋势）"""
    try:
        memories = _get_all_memories_raw()

        # 基础统计
        total_memories = len(memories)
        user_set = set()
        for m in memories:
            uid = m.get("user_id")
            if uid:
                user_set.add(uid)
        total_users = len(user_set)

        # 分类分布
        category_distribution = {cat: 0 for cat in VALID_CATEGORIES}
        for m in memories:
            for cat in (m.get("categories") or []):
                if cat in category_distribution:
                    category_distribution[cat] += 1

        # 状态分布
        state_distribution = {s: 0 for s in VALID_STATES}
        for m in memories:
            s = m.get("state", "active")
            if s in state_distribution:
                state_distribution[s] += 1

        # 近 30 天每日趋势
        daily_trend = []
        today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        for i in range(29, -1, -1):
            day = today - timedelta(days=i)
            day_str = day.strftime("%Y-%m-%d")
            count = 0
            for m in memories:
                created = m.get("created_at")
                if created:
                    try:
                        created_dt = datetime.fromisoformat(str(created).replace("Z", "+00:00"))
                        if created_dt.strftime("%Y-%m-%d") == day_str:
                            count += 1
                    except (ValueError, TypeError):
                        pass
            daily_trend.append({"date": day_str, "count": count})

        return {
            "total_memories": total_memories,
            "total_users": total_users,
            "category_distribution": category_distribution,
            "state_distribution": state_distribution,
            "daily_trend": daily_trend,
        }
    except Exception as e:
        logger.error(f"获取统计数据失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============ 关联记忆接口 ============

@app.get("/v1/memories/{memory_id}/related/")
async def get_related_memories(memory_id: str, limit: int = Query(5, ge=1, le=20)):
    """获取语义相关的记忆（基于当前记忆内容搜索）"""
    try:
        m = get_memory()
        # 先获取当前记忆内容
        current = m.get(memory_id)
        if not current:
            raise HTTPException(status_code=404, detail="记忆不存在")

        memory_text = current.get("memory", "") if isinstance(current, dict) else ""
        if not memory_text:
            return {"results": []}

        # 用当前记忆文本做语义搜索
        search_result = m.search(query=memory_text, limit=limit + 1)

        # 格式化并排除自身
        results = []
        raw_items = []
        if isinstance(search_result, dict) and "results" in search_result:
            raw_items = search_result["results"]
        elif isinstance(search_result, list):
            raw_items = search_result

        for item in raw_items:
            item_id = item.get("id", "")
            if item_id == memory_id:
                continue
            formatted = format_mem0_result(item)
            if "score" in item:
                formatted["score"] = item["score"]
            results.append(formatted)
            if len(results) >= limit:
                break

        return {"results": results}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取关联记忆失败: {e}")
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
