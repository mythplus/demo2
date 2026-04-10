"""
记忆 CRUD 路由 — 添加/获取/更新/删除/批量导入/批量删除/修改历史
"""

import asyncio
import logging
from typing import Optional, Dict, Any, List

from fastapi import APIRouter, HTTPException, Query

from server.config import MEM0_CONFIG, VALID_CATEGORIES, VALID_STATES, _safe_error_detail
from server.models.schemas import (
    AddMemoryRequest, UpdateMemoryRequest,
    BatchImportItem, BatchImportRequest, BatchImportResponse, BatchImportResultItem,
    BatchDeleteRequest, BatchDeleteResponse,
)
from server.services.memory_service import (
    get_memory, disable_graph, get_all_memories_raw, format_record, format_mem0_result,
    apply_filters, auto_categorize_memory, invalidate_stats_cache,
)
from server.services.log_service import (
    log_access, save_change_log, save_category_snapshot, get_change_logs,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["记忆管理"])


@router.post("/v1/memories/")
async def add_memory(request: AddMemoryRequest):
    """添加记忆（支持 categories 和 state）"""
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

        # 合并 metadata，将 categories 和 state 写入 metadata
        final_metadata = dict(request.metadata or {})
        user_selected_categories = False
        if request.categories:
            # 用户手动选择了分类
            valid_cats = [c for c in request.categories if c in VALID_CATEGORIES]
            if valid_cats:
                final_metadata["categories"] = valid_cats
                user_selected_categories = True
        if request.state and request.state in VALID_STATES:
            final_metadata["state"] = request.state

        # 如果用户未手动选择标签，且开启了 AI 自动分类，则先对原始内容进行 AI 分类
        if not user_selected_categories and request.auto_categorize:
            memory_text = " ".join(msg.content for msg in request.messages)
            ai_categories = await auto_categorize_memory(memory_text)
            if ai_categories:
                final_metadata["categories"] = ai_categories
                logger.info(f"AI 自动分类结果已应用: {ai_categories}")

        if final_metadata:
            kwargs["metadata"] = final_metadata

        result = m.add(messages=messages, infer=request.infer, **kwargs)

        # 确保 categories/state 写入 Qdrant（Mem0 SDK 可能不保留自定义 metadata）
        # 同时，如果是 AI 提取模式（infer=True），可能拆分为多条记忆，需要对每条单独 AI 分类
        try:
            added_ids = []
            if isinstance(result, dict) and "results" in result:
                added_ids = [r for r in result["results"] if r.get("id")]
            elif isinstance(result, list):
                added_ids = [r for r in result if r.get("id")]

            if added_ids:
                collection_name = MEM0_CONFIG["vector_store"]["config"]["collection_name"]
                qdrant_client = m.vector_store.client
                for item in added_ids:
                    mid = item.get("id") if isinstance(item, dict) else item
                    try:
                        points = qdrant_client.retrieve(
                            collection_name=collection_name,
                            ids=[mid],
                            with_payload=True,
                        )
                        if points:
                            current_meta = dict((points[0].payload or {}).get("metadata", {}) or {})

                            # 如果是 AI 提取模式且未手动选标签，对每条拆分后的记忆单独 AI 分类
                            if not user_selected_categories and request.auto_categorize and request.infer:
                                memory_content = item.get("memory", "") if isinstance(item, dict) else ""
                                if memory_content:
                                    per_item_cats = await auto_categorize_memory(memory_content)
                                    if per_item_cats:
                                        current_meta["categories"] = per_item_cats

                            # 补写用户手动选择的分类或预先 AI 分类的结果
                            if "categories" in final_metadata and "categories" not in current_meta:
                                current_meta["categories"] = final_metadata["categories"]
                            if "state" in final_metadata:
                                current_meta["state"] = final_metadata["state"]

                            qdrant_client.set_payload(
                                collection_name=collection_name,
                                payload={"metadata": current_meta},
                                points=[mid],
                            )
                            # 记录初始标签快照
                            init_cats = current_meta.get("categories", [])
                            if init_cats:
                                save_category_snapshot(mid, init_cats)
                            # 记录 ADD 事件到自建历史
                            memory_text = item.get("memory", "") if isinstance(item, dict) else ""
                            save_change_log(mid, "ADD", memory_text, init_cats)
                    except Exception:
                        pass
        except Exception as e2:
            logger.warning(f"补写 metadata 失败: {e2}")

        invalidate_stats_cache()
        return result
    except Exception as e:
        logger.error(f"添加记忆失败: {e}")
        raise HTTPException(status_code=500, detail=_safe_error_detail(e))


@router.post("/v1/memories/batch")
async def batch_import_memories(request: BatchImportRequest):
    """批量导入记忆 — 并行处理多条记忆，显著提升导入速度"""
    if not request.items:
        raise HTTPException(status_code=400, detail="items 不能为空")

    m = get_memory()
    collection_name = MEM0_CONFIG["vector_store"]["config"]["collection_name"]
    qdrant_client = m.vector_store.client

    # 并行度限制（避免同时发起过多 LLM 请求）
    _BATCH_CONCURRENCY = 15
    _semaphore = asyncio.Semaphore(_BATCH_CONCURRENCY)

    async def _process_single_item(idx: int, item: BatchImportItem) -> BatchImportResultItem:
        """处理单条记忆的导入（在信号量控制下并行执行）"""
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

                # AI 自动分类（异步，不阻塞事件循环）
                if not user_selected_categories and request.auto_categorize:
                    ai_categories = await auto_categorize_memory(item.content)
                    if ai_categories:
                        final_metadata["categories"] = ai_categories

                kwargs: Dict[str, Any] = {"user_id": uid}
                if final_metadata:
                    kwargs["metadata"] = final_metadata

                messages = [{"role": "user", "content": item.content}]
                # m.add 是同步的 Mem0 SDK 调用，放到线程池执行避免阻塞事件循环
                # 使用 disable_graph 临时禁用图谱，避免 Neo4j 关系名不合法导致导入失败
                def _add_without_graph():
                    with disable_graph(m):
                        return m.add(messages=messages, infer=request.infer, **kwargs)
                result = await asyncio.to_thread(_add_without_graph)

                # 补写 metadata 到 Qdrant
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

                return BatchImportResultItem(
                    index=idx, success=True, id=first_id, memory=first_memory
                )
            except Exception as e:
                logger.warning(f"批量导入第 {idx+1} 条失败: {e}")
                return BatchImportResultItem(
                    index=idx, success=False, error=str(e)
                )

    # 并行执行所有导入任务
    tasks = [_process_single_item(idx, item) for idx, item in enumerate(request.items)]
    results = await asyncio.gather(*tasks)

    # 使统计缓存失效
    invalidate_stats_cache()

    success_count = sum(1 for r in results if r.success)
    failed_count = len(results) - success_count

    invalidate_stats_cache()
    return BatchImportResponse(
        total=len(request.items),
        success=success_count,
        failed=failed_count,
        results=list(results),
    )


@router.get("/v1/memories/")
async def get_memories(
    user_id: Optional[str] = Query(None),
    categories: Optional[str] = Query(None, description="逗号分隔的分类列表"),
    state: Optional[str] = Query(None, description="记忆状态: active/paused/deleted"),
    date_from: Optional[str] = Query(None, description="起始日期 ISO 格式"),
    date_to: Optional[str] = Query(None, description="截止日期 ISO 格式"),
    search: Optional[str] = Query(None, description="文本搜索关键词"),
):
    """获取所有记忆（支持多维筛选）"""
    try:
        # 统一使用 Qdrant 直接查询，确保 metadata (categories/state) 始终一致
        all_memories = get_all_memories_raw()

        # 如果指定了 user_id，先做用户筛选
        if user_id:
            all_memories = [m for m in all_memories if m.get("user_id") == user_id]

        # 应用多维筛选
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


@router.get("/v1/memories/{memory_id}/")
async def get_memory_by_id(memory_id: str):
    """获取单条记忆"""
    try:
        m = get_memory()
        # 直接从 Qdrant 读取，确保 metadata (state/categories) 一致
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
            formatted["id"] = memory_id  # 确保 ID 一致
        except HTTPException:
            raise
        except Exception:
            # fallback 到 Mem0 SDK
            result = m.get(memory_id)
            if not result:
                raise HTTPException(status_code=404, detail="记忆不存在")
            formatted = format_mem0_result(result) if isinstance(result, dict) else result

        # 记录访问日志
        preview = formatted.get("memory", "") if isinstance(formatted, dict) else ""
        log_access(memory_id, "view", preview)
        return formatted
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取记忆失败: {e}")
        raise HTTPException(status_code=500, detail=_safe_error_detail(e))


@router.put("/v1/memories/{memory_id}/")
async def update_memory(memory_id: str, request: UpdateMemoryRequest):
    """更新记忆（支持 text、metadata、categories、state 更新）"""
    try:
        m = get_memory()
        collection_name = MEM0_CONFIG["vector_store"]["config"]["collection_name"]
        qdrant_client = m.vector_store.client

        # 先读取旧数据（更新前快照）
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

        # 第一步：如果有文本更新，先通过 Mem0 SDK 更新（这会重写 Qdrant payload）
        if request.text:
            result = m.update(memory_id=memory_id, data=request.text)
        else:
            result = {"message": "metadata updated"}

        # 第二步：在文本更新完成后，再读取最新 payload 并修改 metadata
        need_metadata_update = (
            request.categories is not None
            or request.state is not None
            or request.metadata is not None
            or request.auto_categorize
        )
        new_cats = old_categories  # 默认不变
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

                    # AI 自动重新分类
                    if request.auto_categorize:
                        memory_text = request.text or current_payload.get("data", "")
                        if memory_text:
                            ai_categories = await auto_categorize_memory(memory_text)
                            current_metadata["categories"] = ai_categories
                            logger.info(f"AI 重新分类记忆 {memory_id}: {ai_categories}")

                    # 更新 categories（手动选择优先于 AI 分类）
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
                    new_cats = current_metadata.get("categories", [])
                    save_category_snapshot(memory_id, new_cats)
                    logger.info(f"已更新记忆 {memory_id} 的 metadata: state={current_metadata.get('state')}, categories={new_cats}")
            except Exception as meta_err:
                logger.warning(f"更新 metadata 失败: {meta_err}")

        # 记录 UPDATE 事件到自建历史（真实时间 + 旧/新内容 + 当前标签）
        new_memory_text = request.text or old_memory_text
        # 如果内容没有变化（只改了标签/元数据），old_memory 传 None 避免显示相同的旧/新内容
        effective_old_memory = old_memory_text if (request.text and old_memory_text != new_memory_text) else None
        save_change_log(memory_id, "UPDATE", new_memory_text, new_cats, effective_old_memory, old_categories)

        invalidate_stats_cache()
        return result
    except Exception as e:
        logger.error(f"更新记忆失败: {e}")
        raise HTTPException(status_code=500, detail=_safe_error_detail(e))


@router.delete("/v1/memories/{memory_id}/")
async def delete_memory_by_id(memory_id: str):
    """软删除单条记忆（将 state 标记为 deleted，而非物理删除）"""
    try:
        m = get_memory()
        collection_name = MEM0_CONFIG["vector_store"]["config"]["collection_name"]
        qdrant_client = m.vector_store.client

        # 先获取当前记忆信息
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

            # 检查是否已经是 deleted 状态，防止重复删除
            if metadata.get("state") == "deleted":
                raise HTTPException(status_code=400, detail="该记忆已处于删除状态，无法重复删除")

            # 将 state 标记为 deleted
            metadata["state"] = "deleted"
            qdrant_client.set_payload(
                collection_name=collection_name,
                payload={"metadata": metadata},
                points=[memory_id],
            )

            # 记录 DELETE 事件到修改历史
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


@router.delete("/v1/memories/")
async def delete_all_memories(
    user_id: Optional[str] = Query(None),
    confirm: bool = Query(False, description="清空全部记忆时必须传 confirm=true 以防误操作"),
):
    """删除用户的所有记忆（清空全部需要 confirm=true 确认）"""
    try:
        m = get_memory()
        if user_id:
            # 分页滚动软删除该用户的所有记忆（mem0 的 delete_all 默认只删 100 条）
            from qdrant_client.models import Filter, FieldCondition, MatchValue
            collection_name = MEM0_CONFIG["vector_store"]["config"]["collection_name"]
            qdrant_client = m.vector_store.client
            total_deleted = 0
            offset = None  # scroll 游标
            while True:
                records, next_offset = qdrant_client.scroll(
                    collection_name=collection_name,
                    scroll_filter=Filter(
                        must=[
                            FieldCondition(key="user_id", match=MatchValue(value=user_id)),
                        ],
                        must_not=[
                            FieldCondition(key="metadata.state", match=MatchValue(value="deleted")),
                        ],
                    ),
                    limit=100,
                    offset=offset,
                    with_payload=True,
                    with_vectors=False,
                )
                if not records:
                    break
                for point in records:
                    mid = str(point.id)
                    payload = point.payload or {}
                    metadata = dict(payload.get("metadata", {}) or {})
                    old_memory_text = payload.get("data", "")
                    old_categories = metadata.get("categories", [])
                    # 软删除：标记 state 为 deleted
                    metadata["state"] = "deleted"
                    qdrant_client.set_payload(
                        collection_name=collection_name,
                        payload={"metadata": metadata},
                        points=[mid],
                    )
                    save_change_log(mid, "DELETE", old_memory_text, old_categories)
                    total_deleted += 1
                # 如果没有下一页游标，说明已经遍历完毕
                if next_offset is None:
                    break
                offset = next_offset
            invalidate_stats_cache()
            return {"message": f"用户 {user_id} 的所有记忆已删除（共 {total_deleted} 条）"}
        else:
            # 无 user_id 时必须显式确认，防止误删全部数据
            if not confirm:
                raise HTTPException(
                    status_code=400,
                    detail="清空全部记忆是危险操作，请传入 confirm=true 参数以确认执行"
                )
            # 复用 Mem0 内部的 Qdrant 客户端清空集合（分页滚动删除，确保全部清空）
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


# ============ 批量删除接口 ============

@router.post("/v1/memories/batch-delete")
async def batch_delete_memories(request: BatchDeleteRequest):
    """批量软删除记忆 — 一次请求删除多条，避免 N 次 HTTP 请求"""
    if not request.memory_ids:
        raise HTTPException(status_code=400, detail="memory_ids 不能为空")

    m = get_memory()
    collection_name = MEM0_CONFIG["vector_store"]["config"]["collection_name"]
    qdrant_client = m.vector_store.client

    results: List[Dict[str, Any]] = []
    success_count = 0
    failed_count = 0

    # 批量获取所有记忆的当前状态
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

    # 收集需要更新的 point IDs 和对应的 payload
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
        # 记录删除历史
        old_memory_text = payload.get("data", "")
        old_categories = metadata.get("categories", [])
        save_change_log(mid, "DELETE", old_memory_text, old_categories)
        results.append({"id": mid, "success": True})
        success_count += 1

    # 批量更新 state 为 deleted
    if to_delete_ids:
        try:
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
            # 部分失败不影响已成功的
            pass

    invalidate_stats_cache()
    return BatchDeleteResponse(
        total=len(request.memory_ids),
        success=success_count,
        failed=failed_count,
        results=results,
    )


# ============ 历史记录接口 ============

@router.get("/v1/memories/history/{memory_id}/")
async def get_memory_history(memory_id: str):
    """获取记忆的修改历史（优先使用自建历史，带真实操作时间和标签快照）"""
    try:
        # 优先查自建历史
        change_logs = get_change_logs(memory_id)
        if change_logs:
            return change_logs

        # 没有自建记录时，回退到 Mem0 原生 history（兼容旧数据）
        m = get_memory()
        result = m.history(memory_id=memory_id)
        history_list = result if isinstance(result, list) else []

        # 获取当前 categories 作为兜底
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
