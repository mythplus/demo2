"""
Playground 对话测试路由 — 基于 LangGraph StateGraph 的记忆增强 AI 对话
将对话流程拆分为三个节点：检索记忆 → LLM 生成 → 存储记忆
"""

import asyncio
import json
import logging
from typing import Optional, List, TypedDict, Annotated

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from langgraph.graph import StateGraph, START, END

from server.config import MEM0_CONFIG
from server.services import memory_service
from server.services.memory_service import auto_categorize_memory

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1/playground", tags=["Playground"])


# ============ 请求/响应模型 ============

class ChatMessage(BaseModel):
    role: str = Field(..., description="消息角色: user / assistant / system")
    content: str = Field(..., max_length=10000, description="消息内容")


class PlaygroundChatRequest(BaseModel):
    message: str = Field(..., max_length=5000, description="用户当前输入的消息")
    user_id: Optional[str] = Field("default_user", max_length=100, description="用户 ID")
    history: Optional[List[ChatMessage]] = Field(default_factory=list, description="当前会话的对话历史")
    memory_limit: Optional[int] = Field(5, ge=1, le=20, description="检索记忆的数量上限")
    stream: Optional[bool] = Field(True, description="是否使用流式输出")


class PlaygroundChatResponse(BaseModel):
    reply: str = Field(..., description="AI 回复内容")
    retrieved_memories: list = Field(default_factory=list, description="本轮检索到的相关记忆")
    new_memories: list = Field(default_factory=list, description="本轮新增/更新的记忆")


# ============ LangGraph 状态定义 ============

class PlaygroundState(TypedDict):
    """LangGraph 状态图的状态，在节点间流转"""
    # 输入
    message: str
    user_id: str
    history: list
    memory_limit: int
    # 中间产物
    retrieved_memories: list
    memories_str: str
    llm_messages: list
    # 输出
    reply: str
    new_memories: list


# ============ 辅助函数 ============

def _get_ollama_config():
    """获取 Ollama 配置"""
    llm_config = MEM0_CONFIG.get("llm", {}).get("config", {})
    base_url = llm_config.get("ollama_base_url", "http://localhost:11434")
    model = llm_config.get("model", "qwen2.5:7b")
    temperature = llm_config.get("temperature", 0.7)
    return base_url, model, temperature


def _write_categories_to_qdrant(m, memory_id: str, categories: list):
    """将自动分类结果写入 Qdrant metadata"""
    try:
        vector_store = getattr(m, "vector_store", None)
        client = getattr(vector_store, "client", None) if vector_store else None
        collection_name = MEM0_CONFIG.get("vector_store", {}).get("config", {}).get("collection_name", "")
        if not client or not collection_name:
            logger.warning(f"写入 Qdrant 分类跳过 [{memory_id}]：vector_store/client 不可用")
            return

        points = client.retrieve(
            collection_name=collection_name,
            ids=[memory_id],
            with_payload=True,
        )
        if not points:
            logger.warning(f"写入 Qdrant 分类跳过 [{memory_id}]：未找到对应 point")
            return

        current_meta = dict((points[0].payload or {}).get("metadata", {}) or {})
        current_meta["categories"] = categories
        client.set_payload(
            collection_name=collection_name,
            payload={"metadata": current_meta},
            points=[memory_id],
        )
        logger.info(f"Playground 自动分类写入成功 [{memory_id}]: {categories}")
    except Exception as e:
        logger.warning(f"写入 Qdrant 分类失败 [{memory_id}]: {e}")


def _build_system_prompt(memories_str: str) -> str:
    """构建带记忆的系统提示词"""
    if memories_str:
        return (
            "你是一个有记忆能力的 AI 助手。你能记住用户之前告诉你的信息，并在对话中自然地运用这些记忆。\n\n"
            "以下是你对该用户的已有记忆：\n"
            f"{memories_str}\n\n"
            "请基于这些记忆和用户的新消息进行回复。如果记忆中的信息与当前对话相关，请自然地引用它们。"
            "回复时请使用用户的语言（如果用户用中文提问，请用中文回复）。"
        )
    else:
        return (
            "你是一个有记忆能力的 AI 助手。目前你对该用户还没有任何记忆。\n"
            "请友好地回复用户的消息。回复时请使用用户的语言（如果用户用中文提问，请用中文回复）。"
        )


# ============ LangGraph 节点函数 ============

async def retrieve_memories_node(state: PlaygroundState) -> dict:
    """节点1：从 Mem0 检索相关记忆"""
    m = memory_service.get_memory()
    retrieved_memories = []
    memories_str = ""

    try:
        search_result = await asyncio.to_thread(
            m.search,
            query=state["message"],
            user_id=state["user_id"],
            limit=state["memory_limit"],
        )
        raw_results = search_result.get("results", []) if isinstance(search_result, dict) else search_result
        for item in raw_results:
            retrieved_memories.append({
                "id": item.get("id", ""),
                "memory": item.get("memory", ""),
                "score": item.get("score", 0),
                "user_id": item.get("user_id", ""),
            })
        if retrieved_memories:
            memories_str = "\n".join(
                f"- {mem['memory']}" for mem in retrieved_memories
            )
    except Exception as e:
        logger.warning(f"[LangGraph] 检索记忆失败: {e}")

    # 构建 LLM 消息列表
    system_prompt = _build_system_prompt(memories_str)
    base_url, model, temperature = _get_ollama_config()

    messages = [{"role": "system", "content": system_prompt}]
    history = (state.get("history") or [])[-40:]
    for msg in history:
        if isinstance(msg, dict):
            messages.append({"role": msg["role"], "content": msg["content"]})
        else:
            messages.append({"role": msg.role, "content": msg.content})
    messages.append({"role": "user", "content": state["message"]})

    return {
        "retrieved_memories": retrieved_memories,
        "memories_str": memories_str,
        "llm_messages": messages,
    }


async def generate_reply_node(state: PlaygroundState) -> dict:
    """节点2：调用 LLM 生成回复"""
    base_url, model, temperature = _get_ollama_config()

    try:
        response = await memory_service.http_client.post(
            f"{base_url}/api/chat",
            json={
                "model": model,
                "messages": state["llm_messages"],
                "stream": False,
                "options": {"temperature": temperature},
            },
            timeout=120,
        )
        response.raise_for_status()
        ai_reply = response.json().get("message", {}).get("content", "")
    except Exception as e:
        logger.error(f"[LangGraph] LLM 调用失败: {e}")
        ai_reply = f"抱歉，AI 回复失败: {str(e)}"

    return {"reply": ai_reply}


async def store_memories_node(state: PlaygroundState) -> dict:
    """节点3：将本轮对话存入 Mem0 记忆"""
    from server.services import meta_service

    m = memory_service.get_memory()
    new_memories = []

    try:
        add_result = await asyncio.to_thread(
            lambda: m.add(
                messages=[
                    {"role": "user", "content": state["message"]},
                    {"role": "assistant", "content": state["reply"]},
                ],
                user_id=state["user_id"],
                metadata={},
            )
        )

        raw_new = add_result.get("results", []) if isinstance(add_result, dict) else add_result
        for item in raw_new:
            event = item.get("event", "NONE")
            if event in ("ADD", "UPDATE"):
                mem_id = item.get("id", "")
                mem_text = item.get("memory", "")
                new_memories.append({
                    "id": mem_id,
                    "memory": mem_text,
                    "event": event,
                })
                cats = []
                # 自动分类并写入 Qdrant
                if mem_text and mem_id:
                    try:
                        cats = await auto_categorize_memory(mem_text)
                        if cats:
                            _write_categories_to_qdrant(m, mem_id, cats)
                    except Exception as e:
                        logger.warning(f"[LangGraph] 自动分类失败 [{mem_id}]: {e}")

                # 双写关系库（对齐其他写入路径）
                if mem_id:
                    try:
                        await asyncio.to_thread(
                            meta_service.create_memory_meta,
                            memory_id=mem_id,
                            user_id=state["user_id"],
                            content=mem_text,
                            hash_value=item.get("hash", "") if isinstance(item, dict) else "",
                            categories=cats,
                            metadata={"categories": cats} if cats else {},
                        )
                    except Exception as db_err:
                        logger.warning(f"[LangGraph] 关系库双写失败（不影响主流程）: {db_err}")

        if new_memories:
            memory_service.invalidate_stats_cache()
    except Exception as e:
        logger.warning(f"[LangGraph] 存储记忆失败: {e}")

    return {"new_memories": new_memories}


# ============ 构建 LangGraph 状态图 ============

def build_playground_graph() -> StateGraph:
    """构建 Playground 对话的 LangGraph 状态图

    流程：
        START → retrieve_memories → generate_reply → store_memories → END
    """
    graph = StateGraph(PlaygroundState)

    # 添加节点
    graph.add_node("retrieve_memories", retrieve_memories_node)
    graph.add_node("generate_reply", generate_reply_node)
    graph.add_node("store_memories", store_memories_node)

    # 定义边（线性流程）
    graph.add_edge(START, "retrieve_memories")
    graph.add_edge("retrieve_memories", "generate_reply")
    graph.add_edge("generate_reply", "store_memories")
    graph.add_edge("store_memories", END)

    return graph.compile()


# 编译一次复用
_playground_graph = None


def get_playground_graph():
    """获取编译后的 Playground 状态图（懒加载单例）"""
    global _playground_graph
    if _playground_graph is None:
        _playground_graph = build_playground_graph()
    return _playground_graph


# ============ 路由 ============

@router.post("/chat", response_model=PlaygroundChatResponse)
async def playground_chat(request: PlaygroundChatRequest):
    """
    Playground 对话接口（非流式）— 基于 LangGraph StateGraph
    流程：retrieve_memories → generate_reply → store_memories
    """
    try:
        graph = get_playground_graph()

        # 初始化状态
        initial_state: PlaygroundState = {
            "message": request.message,
            "user_id": request.user_id or "default_user",
            "history": [{"role": msg.role, "content": msg.content} for msg in (request.history or [])],
            "memory_limit": request.memory_limit or 5,
            "retrieved_memories": [],
            "memories_str": "",
            "llm_messages": [],
            "reply": "",
            "new_memories": [],
        }

        # 执行状态图
        final_state = await graph.ainvoke(initial_state)

        return PlaygroundChatResponse(
            reply=final_state["reply"],
            retrieved_memories=final_state["retrieved_memories"],
            new_memories=final_state["new_memories"],
        )

    except Exception as e:
        logger.error(f"Playground 对话失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"对话失败: {str(e)}")


@router.post("/chat/stream")
async def playground_chat_stream(request: PlaygroundChatRequest):
    """
    Playground 流式对话接口（SSE）— 混合 LangGraph + 手动流式
    流程：LangGraph retrieve_memories → 手动流式 LLM → 后台 store_memories
    说明：流式场景下 LLM 步骤需要逐 token 推送，无法完全封装在 LangGraph 节点中，
         因此采用混合模式：检索记忆走 LangGraph 节点，流式 LLM 和记忆存储手动处理。
    """
    m = memory_service.get_memory()
    user_id = request.user_id or "default_user"

    # 第1步：通过 LangGraph 节点检索记忆 + 构建消息
    retrieve_state: PlaygroundState = {
        "message": request.message,
        "user_id": user_id,
        "history": [{"role": msg.role, "content": msg.content} for msg in (request.history or [])],
        "memory_limit": request.memory_limit or 5,
        "retrieved_memories": [],
        "memories_str": "",
        "llm_messages": [],
        "reply": "",
        "new_memories": [],
    }
    retrieve_result = await retrieve_memories_node(retrieve_state)
    retrieved_memories = retrieve_result["retrieved_memories"]
    llm_messages = retrieve_result["llm_messages"]

    # 第2步：流式调用 LLM
    base_url, model, temperature = _get_ollama_config()

    async def event_stream():
        full_reply = ""

        try:
            # 先发送检索到的记忆
            yield f"data: {json.dumps({'type': 'memories', 'retrieved_memories': retrieved_memories}, ensure_ascii=False)}\n\n"

            # 流式调用 Ollama Chat API
            async with memory_service.http_client.stream(
                "POST",
                f"{base_url}/api/chat",
                json={
                    "model": model,
                    "messages": llm_messages,
                    "stream": True,
                    "options": {"temperature": temperature},
                },
                timeout=120,
            ) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if not line.strip():
                        continue
                    try:
                        chunk = json.loads(line)
                        content = chunk.get("message", {}).get("content", "")
                        if content:
                            full_reply += content
                            yield f"data: {json.dumps({'type': 'content', 'content': content}, ensure_ascii=False)}\n\n"
                        if chunk.get("done", False):
                            break
                    except json.JSONDecodeError:
                        continue

            # 先发送 done 事件让前端立即解锁
            yield f"data: {json.dumps({'type': 'done', 'new_memories': []}, ensure_ascii=False)}\n\n"

            # 第3步：后台异步存储记忆（复用 LangGraph 节点逻辑）
            async def _save_memories_background():
                store_state: PlaygroundState = {
                    "message": request.message,
                    "user_id": user_id,
                    "history": [],
                    "memory_limit": 5,
                    "retrieved_memories": [],
                    "memories_str": "",
                    "llm_messages": [],
                    "reply": full_reply,
                    "new_memories": [],
                }
                await store_memories_node(store_state)

            asyncio.create_task(_save_memories_background())

        except Exception as e:
            logger.error(f"流式对话失败: {e}", exc_info=True)
            yield f"data: {json.dumps({'type': 'error', 'error': str(e)}, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
