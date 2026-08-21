"""
Mem0 Dashboard 后端 - 记忆管理路由
"""
import json
import asyncio
import logging
from typing import Optional, List, Dict, Any

from fastapi import APIRouter, HTTPException, Query
import httpx

from app.config import MEM0_CONFIG, VALID_CATEGORIES, VALID_STATES, _safe_error_detail
from app.models import (
    AddMemoryRequest, SearchMemoryRequest, UpdateMemoryRequest,
    BatchImportRequest, BatchImportItem, BatchImportResultItem, BatchImportResponse,
    BatchDeleteRequest, BatchDeleteResponse,
)
from app.memory_engine import (
    get_memory, get_all_memories_raw, get_real_states,
    format_mem0_result, format_record, apply_filters,
)
from app.categorizer import auto_categorize_memory
from app.database import (
    log_access, save_category_snapshot, save_change_log, get_change_logs,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1/memories", tags=["memories"])

# ============ 统计缓存失效 ============
from app.cache import invalidate_stats_cache


async def _write_metadata_to_qdrant(memory_ids: list, metadata_updates: dict):
    """将 metadata 写入 Qdrant"""
    m = get_memory()
    collection_name = MEM0_CONFIG["vector_store"]["config"]["collection_name"]
    qdrant_client = m.vector_store.client
    for mid in memory_ids:
        try:
            points = qdrant_client.retrieve(
                collection_name=collection_name,
                ids=[mid],
                with_payload=True,
            )
            if points:
                current_meta = dict((points[0].payload or {}).get("metadata", {}) or {})
                current_meta.update(metadata_updates)
                qdrant_client.set_payload(
                    collection_name=collection_name,
                    payload={"metadata": current_meta},
                    points=[mid],
                )
        except Exception:
            pass


# ============ 记忆 CRUD ============

@router.post("/")
async def add_memory(request: AddMemoryRequest):
    """添加记忆"""
    try:
        m = get_memory()
        messages = [{"role": msg.role, "content": msg.content} for msg in request.messages]

        if not request.user_id or not request.user_id.strip():
            raise HTTPException(status_code=400, detail="user_id 为必填项")

        kwargs = {"user_id": request.user_id.strip()}
        if request.agent_id:
            kwargs["agent_id"] = request.agent_id
        if request.run_id:
            kwargs["run_id"] = request.run_id

        final_metadata = dict(request.metadata or {})
        user_selected_categories = False
        if request.categories:
            valid_cats = [c for c in request.categories if c in VALID_CATEGORIES]
            if valid_cats:
                final_metadata["categories"] = valid_cats
                user_selected_categories = True
        if request.state and request.state in VALID_STATES:
            final_metadata["state"] = request.state

        if not user_selected_categories and request.auto_categorize:
            memory_text = " ".join(msg.content for msg in request.messages)
            ai_categories = await auto_categorize_memory(memory_text)
            if ai_categories:
                final_metadata["categories"] = ai_categories
                logger.info(f"AI 自动分类结果已应用: {ai_categories}")

        if final_metadata:
            kwargs["metadata"] = final_metadata

        result = m.add(messages=messages, infer=request.infer, **kwargs)

        try:
            added_ids = []
            if isinstance(result, dict) and "results" in result:
                added_ids = [r for r in result["results"] if r.get("id")]
            elif isinstance(result, list):
                added_ids = [r for r in result if r.get("id")]

            if added_ids:
                collection_name = MEM0_CONFIG["vector_store"]["config"]["collection_name"]
                qdrant_client = m.vector_store.client
                # 批量 retrieve 所有新增点（1 次网络往返替代 N 次）
                all_mids = [item.get("id") if isinstance(item, dict) else item for item in added_ids]
                points = qdrant_client.retrieve(
                    collection_name=collection_name,
                    ids=all_mids,
                    with_payload=True,
                )
                points_map = {str(p.id): p for p in points}

                for item in added_ids:
                    mid = item.get("id") if isinstance(item, dict) else item
                    point = points_map.get(mid)
                    if not point:
                        continue
                    try:
                        current_meta = dict((point.payload or {}).get("metadata", {}) or {})

                        if not user_selected_categories and request.auto_categorize and request.infer:
                            memory_content = item.get("memory", "") if isinstance(item, dict) else ""
                            if memory_content:
                                per_item_cats = await auto_categorize_memory(memory_content)
                                if per_item_cats:
                                    current_meta["categories"] = per_item_cats

                        if "categories" in final_metadata and "categories" not in current_meta:
                            current_meta["categories"] = final_metadata["categories"]
                        if "state" in final_metadata:
                            current_meta["state"] = final_metadata["state"]

                        qdrant_client.set_payload(
                            collection_name=collection_name,
                            payload={"metadata": current_meta},
                            points=[mid],
                        )
                        init_cats = current_meta.get("categories", [])
                        if init_cats:
                            save_category_snapshot(mid, init_cats)
                        memory_text = item.get("memory", "") if isinstance(item, dict) else ""
                        save_change_log(mid, "ADD", memory_text, init_cats)
                    except Exception:
                        pass
        except Exception as e2:
            logger.warning(f"补写 metadata 失败: {e2}")

        invalidate_stats_cache()
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"添加记忆失败: {e}")
        raise HTTPException(status_code=500, detail=_safe_error_detail(e))


@router.post("/batch")
async def batch_import_memories(request: BatchImportRequest):
    """批量导入记忆"""
    if not request.items:
        raise HTTPException(status_code=400, detail="items 不能为空")

    m = get_memory()
    collection_name = MEM0_CONFIG["vector_store"]["config"]["collection_name"]
    qdrant_client = m.vector_store.client

    _BATCH_CONCURRENCY = 5
    _semaphore = asyncio.Semaphore(_BATCH_CONCURRENCY)

    async def _process_single_item(idx: int, item: BatchImportItem) -> BatchImportResultItem:
        async with _semaphore:
            try:
                uid = (request.default_user_id or "").strip() or (item.user_id or "").strip() or "default"

                final_metadata: Dict[str, Any] = dict(item.metadata or {})
                user_selected_categories = False

                if item.categories:
                    valid_cats = [c for c in item.categories if c in VALID_CATEGORIES]
                    if valid_cats:
                        final_metadata["categories"] = valid_cats
                        user_selected_categories = True

                final_metadata["state"] = "active"

                if not user_selected_categories and request.auto_categorize:
                    ai_categories = await auto_categorize_memory(item.content)
                    if ai_categories:
                        final_metadata["categories"] = ai_categories

                kwargs: Dict[str, Any] = {"user_id": uid}
                if final_metadata:
                    kwargs["metadata"] = final_metadata

                messages = [{"role": "user", "content": item.content}]
                result = await asyncio.to_thread(
                    m.add, messages=messages, infer=request.infer, **kwargs
                )

                try:
                    added_ids = []
                    if isinstance(result, dict) and "results" in result:
                        added_ids = [r for r in result["results"] if r.get("id")]
                    elif isinstance(result, list):
                        added_ids = [r for r in result if r.get("id")]

                    if added_ids:
                        for added_item in added_ids:
                            mid = added_item.get("id") if isinstance(added_item, dict) else added_item
                            try:
                                points = qdrant_client.retrieve(
                                    collection_name=collection_name,
                                    ids=[mid],
                                    with_payload=True,
                                )
                                if points:
                                    current_meta = dict((points[0].payload or {}).get("metadata", {}) or {})
                                    if "categories" in final_metadata and "categories" not in current_meta:
                                        current_meta["categories"] = final_metadata["categories"]
                                    if "state" in final_metadata:
                                        current_meta["state"] = final_metadata["state"]
                                    qdrant_client.set_payload(
                                        collection_name=collection_name,
                                        payload={"metadata": current_meta},
                                        points=[mid],
                                    )
                                    init_cats = current_meta.get("categories", [])
                                    if init_cats:
                                        save_category_snapshot(mid, init_cats)
                                    memory_text = added_item.get("memory", "") if isinstance(added_item, dict) else ""
                                    save_change_log(mid, "ADD", memory_text, init_cats)
                            except Exception:
                                pass
                except Exception:
                    pass

                first_id = None
                first_memory = None
                if isinstance(result, dict) and "results" in result and result["results"]:
                    first_id = result["results"][0].get("id")
                    first_memory = result["results"][0].get("memory")

                return BatchImportResultItem(index=idx, success=True, id=first_id, memory=first_memory)
            except Exception as e:
                logger.warning(f"批量导入第 {idx+1} 条失败: {e}")
                return BatchImportResultItem(index=idx, success=False, error=str(e))

    tasks = [_process_single_item(idx, item) for idx, item in enumerate(request.items)]
    results = await asyncio.gather(*tasks)

    invalidate_stats_cache()

    success_count = sum(1 for r in results if r.success)
    failed_count = len(results) - success_count

    return BatchImportResponse(
        total=len(request.items),
        success=success_count,
        failed=failed_count,
        results=list(results),
    )


@router.get("/")
async def get_memories(
    user_id: Optional[str] = Query(None),
    categories: Optional[str] = Query(None, description="逗号分隔的分类列表"),
    state: Optional[str] = Query(None),
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
):
    """获取所有记忆（支持多维筛选）"""
    try:
        all_memories = get_all_memories_raw()

        if user_id:
            all_memories = [m for m in all_memories if m.get("user_id") == user_id]

        cat_list = [c.strip() for c in categories.split(",") if c.strip()] if categories else None
        memories = apply_filters(
            all_memories,
            categories=cat_list,
            state=state,
            date_from=date_from,
            date_to=date_to,
            search=search,
        )

        return memories
    except Exception as e:
        logger.error(f"获取记忆失败: {e}")
        raise HTTPException(status_code=500, detail=_safe_error_detail(e))


@router.get("/{memory_id}/")
async def get_memory_by_id(memory_id: str):
    """获取单条记忆"""
    try:
        m = get_memory()
        try:
            collection_name = MEM0_CONFIG["vector_store"]["config"]["collection_name"]
            qdrant_client = m.vector_store.client
            points = qdrant_client.retrieve(
                collection_name=collection_name,
                ids=[memory_id],
                with_payload=True,
            )
            if not points:
                raise HTTPException(status_code=404, detail="记忆不存在")
            formatted = format_record(points[0])
            formatted["id"] = memory_id
        except HTTPException:
            raise
        except Exception:
            result = m.get(memory_id)
            if not result:
                raise HTTPException(status_code=404, detail="记忆不存在")
            formatted = format_mem0_result(result) if isinstance(result, dict) else result

        preview = formatted.get("memory", "") if isinstance(formatted, dict) else ""
        log_access(memory_id, "view", preview)
        return formatted
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取记忆失败: {e}")
        raise HTTPException(status_code=500, detail=_safe_error_detail(e))


@router.put("/{memory_id}/")
async def update_memory(memory_id: str, request: UpdateMemoryRequest):
    """更新记忆"""
    try:
        m = get_memory()
        collection_name = MEM0_CONFIG["vector_store"]["config"]["collection_name"]
        qdrant_client = m.vector_store.client

        old_memory_text = ""
        old_categories: list = []
        try:
            old_points = qdrant_client.retrieve(
                collection_name=collection_name,
                ids=[memory_id],
                with_payload=True,
            )
            if old_points:
                old_payload = old_points[0].payload or {}
                old_memory_text = old_payload.get("data", old_payload.get("memory", ""))
                old_meta = old_payload.get("metadata", {}) or {}
                old_categories = old_meta.get("categories", [])
        except Exception:
            pass

        if request.text:
            result = m.update(memory_id=memory_id, data=request.text)
        else:
            result = {"message": "metadata updated"}

        need_metadata_update = (
            request.categories is not None
            or request.state is not None
            or request.metadata is not None
            or request.auto_categorize
        )
        new_cats = old_categories
        if need_metadata_update:
            try:
                points = qdrant_client.retrieve(
                    collection_name=collection_name,
                    ids=[memory_id],
                    with_payload=True,
                )
                if points:
                    current_payload = points[0].payload or {}
                    current_metadata = dict(current_payload.get("metadata", {}) or {})

                    if request.auto_categorize:
                        memory_text = request.text or current_payload.get("data", "")
                        if memory_text:
                            ai_categories = await auto_categorize_memory(memory_text)
                            current_metadata["categories"] = ai_categories
                            logger.info(f"AI 重新分类记忆 {memory_id}: {ai_categories}")

                    if request.categories is not None:
                        valid_cats = [c for c in request.categories if c in VALID_CATEGORIES]
                        current_metadata["categories"] = valid_cats

                    if request.state is not None and request.state in VALID_STATES:
                        current_metadata["state"] = request.state

                    if request.metadata is not None:
                        for k, v in request.metadata.items():
                            if k not in ("categories", "state"):
                                current_metadata[k] = v

                    qdrant_client.set_payload(
                        collection_name=collection_name,
                        payload={"metadata": current_metadata},
                        points=[memory_id],
                    )
                    new_cats = current_metadata.get("categories", [])
                    save_category_snapshot(memory_id, new_cats)
                    logger.info(f"已更新记忆 {memory_id} 的 metadata")
            except Exception as meta_err:
                logger.warning(f"更新 metadata 失败: {meta_err}")

        new_memory_text = request.text or old_memory_text
        effective_old_memory = old_memory_text if (request.text and old_memory_text != new_memory_text) else None
        save_change_log(memory_id, "UPDATE", new_memory_text, new_cats, effective_old_memory, old_categories)

        invalidate_stats_cache()
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"更新记忆失败: {e}")
        raise HTTPException(status_code=500, detail=_safe_error_detail(e))


@router.delete("/{memory_id}/")
async def delete_memory_by_id(memory_id: str):
    """软删除单条记忆"""
    try:
        m = get_memory()
        collection_name = MEM0_CONFIG["vector_store"]["config"]["collection_name"]
        qdrant_client = m.vector_store.client

        try:
            points = qdrant_client.retrieve(
                collection_name=collection_name,
                ids=[memory_id],
                with_payload=True,
            )
            if not points:
                raise HTTPException(status_code=404, detail="记忆不存在")

            payload = points[0].payload or {}
            metadata = payload.get("metadata", {})
            old_memory_text = payload.get("data", "")
            old_categories = metadata.get("categories", [])

            if metadata.get("state") == "deleted":
                raise HTTPException(status_code=400, detail="该记忆已处于删除状态，无法重复删除")

            metadata["state"] = "deleted"
            qdrant_client.set_payload(
                collection_name=collection_name,
                payload={"metadata": metadata},
                points=[memory_id],
            )

            save_change_log(memory_id, "DELETE", old_memory_text, old_categories)

            logger.info(f"已软删除记忆 {memory_id}")
            invalidate_stats_cache()
            return {"message": "记忆已删除"}
        except HTTPException:
            raise
        except Exception as inner_err:
            logger.warning(f"软删除失败，回退到物理删除: {inner_err}")
            m.delete(memory_id=memory_id)
            invalidate_stats_cache()
            return {"message": "记忆已删除"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"删除记忆失败: {e}")
        raise HTTPException(status_code=500, detail=_safe_error_detail(e))


@router.delete("/")
async def delete_all_memories(
    user_id: Optional[str] = Query(None),
    confirm: bool = Query(False),
):
    """删除用户的所有记忆"""
    try:
        m = get_memory()
        if user_id:
            m.delete_all(user_id=user_id)
            return {"message": f"用户 {user_id} 的所有记忆已删除"}
        else:
            if not confirm:
                raise HTTPException(
                    status_code=400,
                    detail="清空全部记忆是危险操作，请传入 confirm=true 参数以确认执行"
                )
            try:
                from qdrant_client.models import PointIdsList
                collection_name = MEM0_CONFIG["vector_store"]["config"]["collection_name"]
                qdrant_client = m.vector_store.client
                total_deleted = 0
                while True:
                    records, _ = qdrant_client.scroll(
                        collection_name=collection_name,
                        limit=100,
                        with_payload=False,
                        with_vectors=False,
                    )
                    if not records:
                        break
                    ids = [record.id for record in records]
                    qdrant_client.delete(
                        collection_name=collection_name,
                        points_selector=PointIdsList(points=ids),
                    )
                    total_deleted += len(ids)
                return {"message": f"所有记忆已删除（共 {total_deleted} 条）"}
            except Exception as qdrant_err:
                logger.error(f"Qdrant 直接删除失败: {qdrant_err}")
                raise HTTPException(status_code=500, detail=_safe_error_detail(qdrant_err))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"删除记忆失败: {e}")
        raise HTTPException(status_code=500, detail=_safe_error_detail(e))


@router.post("/batch-delete")
async def batch_delete_memories(request: BatchDeleteRequest):
    """批量软删除记忆"""
    if not request.memory_ids:
        raise HTTPException(status_code=400, detail="memory_ids 不能为空")

    m = get_memory()
    collection_name = MEM0_CONFIG["vector_store"]["config"]["collection_name"]
    qdrant_client = m.vector_store.client

    results: List[Dict[str, Any]] = []
    success_count = 0
    failed_count = 0

    try:
        points = qdrant_client.retrieve(
            collection_name=collection_name,
            ids=request.memory_ids,
            with_payload=True,
        )
        points_map = {str(p.id): p for p in points}
    except Exception as e:
        logger.error(f"批量查询记忆失败: {e}")
        raise HTTPException(status_code=500, detail=_safe_error_detail(e))

    to_delete_ids = []
    for mid in request.memory_ids:
        point = points_map.get(mid)
        if not point:
            results.append({"id": mid, "success": False, "error": "记忆不存在"})
            failed_count += 1
            continue

        payload = point.payload or {}
        metadata = payload.get("metadata", {}) or {}

        if metadata.get("state") == "deleted":
            results.append({"id": mid, "success": False, "error": "已处于删除状态"})
            failed_count += 1
            continue

        to_delete_ids.append(mid)
        old_memory_text = payload.get("data", "")
        old_categories = metadata.get("categories", [])
        save_change_log(mid, "DELETE", old_memory_text, old_categories)
        results.append({"id": mid, "success": True})
        success_count += 1

    if to_delete_ids:
        try:
            from qdrant_client.models import PointIdsList
            # 批量软删除：一次性更新所有需要删除的记忆 state
            for mid in to_delete_ids:
                point = points_map[mid]
                metadata = dict((point.payload or {}).get("metadata", {}) or {})
                metadata["state"] = "deleted"
                qdrant_client.set_payload(
                    collection_name=collection_name,
                    payload={"metadata": metadata},
                    points=[mid],
                )
        except Exception as e:
            logger.error(f"批量软删除失败: {e}")

    invalidate_stats_cache()
    return BatchDeleteResponse(
        total=len(request.memory_ids),
        success=success_count,
        failed=failed_count,
        results=results,
    )


@router.post("/search/")
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

        formatted = []
        if isinstance(result, dict) and "results" in result:
            formatted = [format_mem0_result(item) for item in result["results"]]
            for i, item in enumerate(result["results"]):
                if "score" in item:
                    formatted[i]["score"] = item["score"]
        elif isinstance(result, list):
            formatted = [format_mem0_result(item) for item in result]
            for i, item in enumerate(result):
                if "score" in item:
                    formatted[i]["score"] = item["score"]
        else:
            return {"results": result}

        memory_ids = [item["id"] for item in formatted if item.get("id")]
        real_states = get_real_states(memory_ids)

        for item in formatted:
            mid = item.get("id", "")
            if mid in real_states:
                item["state"] = real_states[mid]
        formatted = [item for item in formatted if item.get("state", "active") != "deleted"]

        return {"results": formatted}
    except Exception as e:
        logger.error(f"搜索记忆失败: {e}")
        raise HTTPException(status_code=500, detail=_safe_error_detail(e))


@router.get("/history/{memory_id}/")
async def get_memory_history(memory_id: str):
    """获取记忆的修改历史"""
    try:
        change_logs = get_change_logs(memory_id)
        if change_logs:
            return change_logs

        m = get_memory()
        result = m.history(memory_id=memory_id)
        history_list = result if isinstance(result, list) else []

        current_categories: list = []
        try:
            collection_name = MEM0_CONFIG["vector_store"]["config"]["collection_name"]
            qdrant_client = m.vector_store.client
            points = qdrant_client.retrieve(
                collection_name=collection_name,
                ids=[memory_id],
                with_payload=True,
            )
            if points:
                current_metadata = (points[0].payload or {}).get("metadata", {}) or {}
                current_categories = current_metadata.get("categories", [])
        except Exception:
            pass

        for item in history_list:
            if isinstance(item, dict):
                item["categories"] = current_categories

        return history_list
    except Exception as e:
        logger.error(f"获取记忆历史失败: {e}")
        raise HTTPException(status_code=500, detail=_safe_error_detail(e))


@router.get("/{memory_id}/related/")
async def get_related_memories(memory_id: str, limit: int = Query(5, ge=1, le=20)):
    """获取语义相关的记忆"""
    try:
        m = get_memory()
        current = m.get(memory_id)
        if not current:
            raise HTTPException(status_code=404, detail="记忆不存在")

        memory_text = current.get("memory", "") if isinstance(current, dict) else ""
        if not memory_text:
            return {"results": []}

        search_result = m.search(query=memory_text, limit=limit + 1)

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

        memory_ids = [item["id"] for item in results if item.get("id")]
        real_states = get_real_states(memory_ids)
        for item in results:
            mid = item.get("id", "")
            if mid in real_states:
                item["state"] = real_states[mid]
        results = [item for item in results if item.get("state", "active") != "deleted"]

        results = results[:limit]
        return {"results": results}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取关联记忆失败: {e}")
        raise HTTPException(status_code=500, detail=_safe_error_detail(e))
