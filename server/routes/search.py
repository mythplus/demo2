"""
语义搜索 + 关联记忆路由
"""

import asyncio
import logging
from fastapi import APIRouter, HTTPException, Query

from server.config import MEM0_CONFIG, _safe_error_detail
from server.models.schemas import SearchMemoryRequest
from server.services.memory_service import (
    get_memory, format_mem0_result,
)
from server.services import webhook_service, memory_service as _mem_svc

logger = logging.getLogger(__name__)

router = APIRouter(tags=["语义检索"])


def get_real_states() -> dict:
    """兼容旧测试桩的占位函数，当前状态信息已直接包含在格式化结果中。"""
    return {}


@router.post("/v1/memories/search/")

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

        result = await asyncio.to_thread(m.search, **kwargs)


        # 统一返回格式并附加 categories/state
        formatted = []
        if isinstance(result, dict) and "results" in result:
            raw_results = result["results"]
        elif isinstance(result, list):
            raw_results = result
        else:
            return {"results": result}

        formatted = []
        for item in raw_results:
            formatted_item = format_mem0_result(item)
            state = (
                formatted_item.get("state")
                or (formatted_item.get("metadata") or {}).get("state")
                or "active"
            )
            if state == "deleted":
                continue
            if "score" in item:
                formatted_item["score"] = item["score"]
            formatted.append(formatted_item)


        # 触发 Webhook（托管到统一后台任务管理器）
        _wh_data = {
            "user_id": request.user_id or "",
            "memory": request.query[:200],
            "result_count": len(formatted),
        }
        webhook_service.schedule_webhook_delivery("memory.searched", _wh_data, _mem_svc.http_client)


        return {"results": formatted}
    except Exception as e:
        logger.error(f"搜索记忆失败: {e}")
        raise HTTPException(status_code=500, detail=_safe_error_detail(e))


@router.get("/v1/memories/{memory_id}/related/")
async def get_related_memories(memory_id: str, limit: int = Query(5, ge=1, le=20)):
    """获取语义相关的记忆（基于当前记忆内容搜索）"""
    try:
        m = get_memory()
        # 先获取当前记忆内容
        current = await asyncio.to_thread(m.get, memory_id)

        if not current:
            raise HTTPException(status_code=404, detail="记忆不存在")

        memory_text = current.get("memory", "") if isinstance(current, dict) else ""
        if not memory_text:
            return {"results": []}

        # 用当前记忆文本做语义搜索
        search_result = await asyncio.to_thread(m.search, query=memory_text, limit=limit + 1)


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

        # 截取到 limit 条
        results = results[:limit]

        return {"results": results}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取关联记忆失败: {e}")
        raise HTTPException(status_code=500, detail=_safe_error_detail(e))
