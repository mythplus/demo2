"""
Playground 对话测试路由 — 记忆增强的 AI 对话
整合 search → LLM → add 三步流程，让用户直观体验"AI 记住了我"的效果
"""

import json
import logging
from typing import Optional, List

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from server.config import MEM0_CONFIG
from server.services import memory_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1/playground", tags=["调试台"])


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


# ============ 辅助函数 ============

def _get_ollama_config():
    """获取 Ollama 配置"""
    llm_config = MEM0_CONFIG.get("llm", {}).get("config", {})
    base_url = llm_config.get("ollama_base_url", "http://localhost:11434")
    model = llm_config.get("model", "qwen2.5:7b")
    temperature = llm_config.get("temperature", 0.7)
    return base_url, model, temperature


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


# ============ 路由 ============

@router.post("/chat", response_model=PlaygroundChatResponse)
async def playground_chat(request: PlaygroundChatRequest):
    """
    Playground 对话接口（非流式）
    流程：检索相关记忆 → 构建增强 Prompt → 调用 LLM → 存储新记忆
    """
    try:
        m = memory_service.get_memory()
        user_id = request.user_id or "default_user"

        # 第1步：检索相关记忆
        retrieved_memories = []
        memories_str = ""
        try:
            search_result = m.search(
                query=request.message,
                user_id=user_id,
                limit=request.memory_limit,
            )
            raw_results = search_result.get("results", []) if isinstance(search_result, dict) else search_result
            # 过滤已删除的记忆
            for item in raw_results:
                metadata = item.get("metadata", {}) or {}
                state = metadata.get("state", "active")
                if state != "deleted":
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
            logger.warning(f"检索记忆失败: {e}")

        # 第2步：构建增强 Prompt 并调用 LLM
        system_prompt = _build_system_prompt(memories_str)
        base_url, model, temperature = _get_ollama_config()

        # 构建消息列表
        messages = [{"role": "system", "content": system_prompt}]
        # 添加对话历史（最多保留最近 20 轮）
        history = (request.history or [])[-40:]  # 最多 40 条消息（约 20 轮对话）
        for msg in history:
            messages.append({"role": msg.role, "content": msg.content})
        messages.append({"role": "user", "content": request.message})

        # 调用 Ollama Chat API
        response = await memory_service.http_client.post(
            f"{base_url}/api/chat",
            json={
                "model": model,
                "messages": messages,
                "stream": False,
                "options": {"temperature": temperature},
            },
            timeout=120,
        )
        response.raise_for_status()
        ai_reply = response.json().get("message", {}).get("content", "")

        # 第3步：将本轮对话存入记忆（mem0 自动提取关键信息）
        new_memories = []
        try:
            add_result = m.add(
                messages=[
                    {"role": "user", "content": request.message},
                    {"role": "assistant", "content": ai_reply},
                ],
                user_id=user_id,
            )
            raw_new = add_result.get("results", []) if isinstance(add_result, dict) else add_result
            for item in raw_new:
                event = item.get("event", "NONE")
                if event in ("ADD", "UPDATE"):
                    new_memories.append({
                        "id": item.get("id", ""),
                        "memory": item.get("memory", ""),
                        "event": event,
                    })
            # 使统计缓存失效
            if new_memories:
                memory_service.invalidate_stats_cache()
        except Exception as e:
            logger.warning(f"存储记忆失败: {e}")

        return PlaygroundChatResponse(
            reply=ai_reply,
            retrieved_memories=retrieved_memories,
            new_memories=new_memories,
        )

    except Exception as e:
        logger.error(f"Playground 对话失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"对话失败: {str(e)}")


@router.post("/chat/stream")
async def playground_chat_stream(request: PlaygroundChatRequest):
    """
    Playground 流式对话接口（SSE）
    流程：检索相关记忆 → 构建增强 Prompt → 流式调用 LLM → 存储新记忆
    返回 Server-Sent Events 格式的流式响应
    """
    m = memory_service.get_memory()
    user_id = request.user_id or "default_user"

    # 第1步：检索相关记忆
    retrieved_memories = []
    memories_str = ""
    try:
        search_result = m.search(
            query=request.message,
            user_id=user_id,
            limit=request.memory_limit,
        )
        raw_results = search_result.get("results", []) if isinstance(search_result, dict) else search_result
        for item in raw_results:
            metadata = item.get("metadata", {}) or {}
            state = metadata.get("state", "active")
            if state != "deleted":
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
        logger.warning(f"检索记忆失败: {e}")

    # 第2步：构建消息列表
    system_prompt = _build_system_prompt(memories_str)
    base_url, model, temperature = _get_ollama_config()

    messages = [{"role": "system", "content": system_prompt}]
    history = (request.history or [])[-40:]
    for msg in history:
        messages.append({"role": msg.role, "content": msg.content})
    messages.append({"role": "user", "content": request.message})

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
                    "messages": messages,
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
                        # 检查是否结束
                        if chunk.get("done", False):
                            break
                    except json.JSONDecodeError:
                        continue

            # 第3步：流式结束后，存储记忆
            new_memories = []
            try:
                add_result = m.add(
                    messages=[
                        {"role": "user", "content": request.message},
                        {"role": "assistant", "content": full_reply},
                    ],
                    user_id=user_id,
                )
                raw_new = add_result.get("results", []) if isinstance(add_result, dict) else add_result
                for item in raw_new:
                    event = item.get("event", "NONE")
                    if event in ("ADD", "UPDATE"):
                        new_memories.append({
                            "id": item.get("id", ""),
                            "memory": item.get("memory", ""),
                            "event": event,
                        })
                if new_memories:
                    memory_service.invalidate_stats_cache()
            except Exception as e:
                logger.warning(f"存储记忆失败: {e}")

            # 发送完成事件（包含新增记忆）
            yield f"data: {json.dumps({'type': 'done', 'new_memories': new_memories}, ensure_ascii=False)}\n\n"

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
