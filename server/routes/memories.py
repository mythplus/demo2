"""
记忆 CRUD 路由 — 添加/获取/更新/删除/批量导入/批量删除/修改历史
"""

import asyncio
import logging
from typing import Optional, Dict, Any, List

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from server.config import MEM0_CONFIG, VALID_CATEGORIES, VALID_STATES, _safe_error_detail
from server.models.schemas import (
    AddMemoryRequest, UpdateMemoryRequest,
    BatchImportItem, BatchImportRequest, BatchImportResponse, BatchImportResultItem,
    BatchDeleteRequest, BatchDeleteResponse,
    BatchStateChangeRequest, RestoreMemoriesRequest,
)
from server.services.memory_service import (
    get_memory, disable_graph, get_all_memories_raw, get_memories_page, get_all_memory_ids,
    get_users_summary, get_memory_summary, format_record, format_mem0_result,
    auto_categorize_memory, invalidate_stats_cache,
)
from server.services.log_service import (
    log_access, save_change_log, save_category_snapshot, save_memory_audit_snapshot, get_change_logs,
)
from server.services import webhook_service, memory_service as _mem_svc
from server.services import meta_service
from server.services.meta_service import (
    update_memory_state, batch_update_memory_state, resolve_list_state_filters,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["记忆管理"])


class PaginatedMemoriesResponse(BaseModel):
    items: List[Dict[str, Any]]
    total: int
    page: int
    page_size: int
    total_pages: int


class UserSummaryItem(BaseModel):
    user_id: str
    memory_count: int
    last_active: Optional[str] = None


class DashboardSummaryResponse(BaseModel):
    recent_memories: List[Dict[str, Any]]
    top_users: List[UserSummaryItem]


@router.post("/v1/memories/")
async def add_memory(request: AddMemoryRequest):
    """添加记忆（支持 categories 和 state）"""
    user_id = (request.user_id or "").strip()
    if not user_id:
        raise HTTPException(status_code=400, detail="user_id 为必填项")

    added_ids_for_rollback: List[str] = []

    try:
        m = get_memory()
        messages = [{"role": msg.role, "content": msg.content} for msg in request.messages]

        kwargs = {"user_id": user_id}
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

        # m.add 是同步的 Mem0 SDK 调用，放到线程池执行避免阻塞事件循环
        result = await asyncio.to_thread(m.add, messages=messages, infer=request.infer, **kwargs)

        added_items = []
        if isinstance(result, dict) and "results" in result:
            added_items = [r for r in result["results"] if r.get("id")]
        elif isinstance(result, list):
            added_items = [r for r in result if r.get("id")]

        added_ids_for_rollback = [str(item.get("id")) for item in added_items if item.get("id")]

        if added_items:
            collection_name = MEM0_CONFIG["vector_store"]["config"]["collection_name"]
            qdrant_client = m.vector_store.client
            for item in added_items:
                mid = str(item.get("id"))
                points = qdrant_client.retrieve(
                    collection_name=collection_name,
                    ids=[mid],
                    with_payload=True,
                )
                if not points:
                    raise RuntimeError(f"新增记忆后未找到对应向量记录: {mid}")

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

                init_cats = current_meta.get("categories", [])
                memory_text = item.get("memory", "") if isinstance(item, dict) else ""
                await asyncio.to_thread(save_memory_audit_snapshot, mid, "ADD", memory_text, init_cats)

                # 双写关系库（对齐 OpenMemory 架构）
                try:
                    await asyncio.to_thread(
                        meta_service.create_memory_meta,
                        memory_id=mid,
                        user_id=user_id,
                        content=memory_text,
                        hash_value=item.get("hash", "") if isinstance(item, dict) else "",
                        agent_id=request.agent_id or "",
                        run_id=request.run_id or "",
                        state=current_meta.get("state", "active"),
                        categories=init_cats,
                        metadata=current_meta,
                    )
                except Exception as db_err:
                    logger.warning(f"关系库双写失败（不影响主流程）: {db_err}")

        invalidate_stats_cache()

        # 触发 Webhook（后台异步，不阻塞响应）
        try:
            _wh_data = {
                "user_id": user_id,
                "memory": " ".join(msg.content for msg in request.messages)[:200],
                "memory_id": ", ".join(added_ids_for_rollback) if added_ids_for_rollback else "",
            }
            asyncio.ensure_future(webhook_service.trigger_webhooks("memory.added", _wh_data, _mem_svc.http_client))
        except Exception:
            pass

        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("添加记忆失败")

        if added_ids_for_rollback:
            try:
                collection_name = MEM0_CONFIG["vector_store"]["config"]["collection_name"]
                qdrant_client = get_memory().vector_store.client
                for mid in added_ids_for_rollback:
                    points = qdrant_client.retrieve(
                        collection_name=collection_name,
                        ids=[mid],
                        with_payload=True,
                    )
                    if not points:
                        continue
                    metadata = dict((points[0].payload or {}).get("metadata", {}) or {})
                    metadata["state"] = "deleted"
                    qdrant_client.set_payload(
                        collection_name=collection_name,
                        payload={"metadata": metadata},
                        points=[mid],
                    )
                invalidate_stats_cache()
                logger.warning(f"添加记忆补写失败，已软回滚 {len(added_ids_for_rollback)} 条记忆")
            except Exception as rollback_err:
                logger.error(f"添加记忆补写失败后的软回滚也失败: {rollback_err}")

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

    async def _soft_rollback_added_ids(memory_ids: List[str]):
        """将已新增但补写失败的记忆软回滚为 deleted。"""
        if not memory_ids:
            return
        for mid in memory_ids:
            points = qdrant_client.retrieve(
                collection_name=collection_name,
                ids=[mid],
                with_payload=True,
            )
            if not points:
                continue
            metadata = dict((points[0].payload or {}).get("metadata", {}) or {})
            metadata["state"] = "deleted"
            qdrant_client.set_payload(
                collection_name=collection_name,
                payload={"metadata": metadata},
                points=[mid],
            )

    async def _process_single_item(idx: int, item: BatchImportItem) -> BatchImportResultItem:
        """处理单条记忆的导入（在信号量控制下并行执行）"""
        async with _semaphore:
            added_ids_for_rollback: List[str] = []
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

                added_items = []
                if isinstance(result, dict) and "results" in result:
                    added_items = [r for r in result["results"] if r.get("id")]
                elif isinstance(result, list):
                    added_items = [r for r in result if r.get("id")]

                added_ids_for_rollback = [str(added_item.get("id")) for added_item in added_items if added_item.get("id")]

                for added_item in added_items:
                    mid = str(added_item.get("id"))
                    points = qdrant_client.retrieve(
                        collection_name=collection_name,
                        ids=[mid],
                        with_payload=True,
                    )
                    if not points:
                        raise RuntimeError(f"批量导入新增记忆后未找到对应向量记录: {mid}")

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

                # 记忆本体和 metadata 已写入成功，审计日志为非关键路径，失败只打 warning
                for added_item in added_items:
                    try:
                        mid = str(added_item.get("id"))
                        init_cats = []
                        _pts = qdrant_client.retrieve(collection_name=collection_name, ids=[mid], with_payload=True)
                        if _pts:
                            init_cats = (_pts[0].payload or {}).get("metadata", {}).get("categories", [])
                        memory_text = added_item.get("memory", "") if isinstance(added_item, dict) else ""
                        await asyncio.to_thread(save_memory_audit_snapshot, mid, "ADD", memory_text, init_cats)

                        # 双写关系库（对齐 OpenMemory 架构）
                        try:
                            await asyncio.to_thread(
                                meta_service.create_memory_meta,
                                memory_id=mid,
                                user_id=uid,
                                content=memory_text,
                                hash_value=added_item.get("hash", "") if isinstance(added_item, dict) else "",
                                state="active",
                                categories=init_cats,
                                metadata=(_pts[0].payload or {}).get("metadata", {}) if _pts else {},
                            )
                        except Exception as db_err:
                            logger.warning(f"批量导入第 {idx+1} 条关系库双写失败（不影响主流程）: {db_err}")
                    except Exception as audit_err:
                        logger.warning(f"批量导入第 {idx+1} 条审计日志写入失败（记忆已成功导入）: {audit_err}")

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
                if added_ids_for_rollback:
                    try:
                        await _soft_rollback_added_ids(added_ids_for_rollback)
                        logger.warning(f"批量导入第 {idx+1} 条补写失败，已软回滚 {len(added_ids_for_rollback)} 条记忆")
                    except Exception as rollback_err:
                        logger.error(f"批量导入第 {idx+1} 条补写失败后的软回滚也失败: {rollback_err}")
                return BatchImportResultItem(
                    index=idx, success=False, error=_safe_error_detail(e)
                )

    # 并行执行所有导入任务
    tasks = [_process_single_item(idx, item) for idx, item in enumerate(request.items)]
    results = await asyncio.gather(*tasks)

    success_count = sum(1 for r in results if r.success)
    failed_count = len(results) - success_count

    # 使统计缓存失效
    if success_count > 0:
        invalidate_stats_cache()

    # Webhook 由前端在所有批次完成后调用 /v1/memories/batch-import-notify 统一触发

    return BatchImportResponse(
        total=len(request.items),
        success=success_count,
        failed=failed_count,
        results=list(results),
    )


# ============ 批量导入 Webhook 汇总通知 ============

class _BatchImportNotifyRequest(BaseModel):
    """批量导入完成后的 Webhook 汇总通知请求"""
    total: int = Field(..., description="全局总条数")
    success: int = Field(..., description="全局成功条数")
    failed: int = Field(..., description="全局失败条数")
    skipped: int = Field(0, description="全局跳过条数（用户取消导入时未处理的）")

@router.post("/v1/memories/batch-import-notify")
async def batch_import_notify(request: _BatchImportNotifyRequest):
    """批量导入完成后发送 Webhook 汇总通知（前端在所有批次完成后调用）"""
    try:
        parts = [f"批量导入 {request.total} 条记忆，成功 {request.success} 条，失败 {request.failed} 条"]
        if request.skipped > 0:
            parts.append(f"跳过 {request.skipped} 条")
        _wh_data = {
            "memory": "，".join(parts),
            "memory_id": "",
        }
        asyncio.ensure_future(webhook_service.trigger_webhooks("memory.batch_imported", _wh_data, _mem_svc.http_client))
    except Exception:
        pass
    return {"message": "通知已发送"}


@router.get("/v1/memories/")
async def get_memories(
    user_id: Optional[str] = Query(None),
    categories: Optional[str] = Query(None, description="逗号分隔的分类列表"),
    state: Optional[str] = Query(None, description="记忆状态: active/paused/archived/deleted"),
    date_from: Optional[str] = Query(None, description="起始日期 ISO 格式"),
    date_to: Optional[str] = Query(None, description="截止日期 ISO 格式"),
    search: Optional[str] = Query(None, description="文本搜索关键词"),
    page: Optional[int] = Query(None, ge=1, description="页码，传入后启用服务端分页"),
    page_size: Optional[int] = Query(None, ge=1, le=200, description="每页条数，默认 20，最大 200"),
    sort_by: Optional[str] = Query("created_at", description="排序字段: created_at/updated_at"),
    sort_order: Optional[str] = Query("desc", description="排序方向: asc/desc"),
    exclude_state: Optional[str] = Query(None, description="排除的记忆状态，如 deleted"),
    show_archived: bool = Query(False, description="是否在默认列表中显示已归档记忆"),
):
    """获取记忆列表（默认排除 archived 和 deleted，对齐 openmemory 行为）"""
    try:
        cat_list = [c.strip() for c in categories.split(",") if c.strip()] if categories else None

        # 应用默认列表过滤规则（对齐 openmemory：默认排除 archived + deleted）
        resolved_state, exclude_states = resolve_list_state_filters(
            state=state, exclude_state=exclude_state, show_archived=show_archived,
        )

        if page is not None or page_size is not None:
            return get_memories_page(
                user_id=user_id,
                categories=cat_list,
                state=resolved_state,
                date_from=date_from,
                date_to=date_to,
                search=search,
                page=page or 1,
                page_size=page_size or 20,
                order_by=sort_by or "created_at",
                order_direction=sort_order or "desc",
                exclude_states=exclude_states if exclude_states else None,
            )

        return get_all_memories_raw(
            user_id=user_id,
            categories=cat_list,
            state=resolved_state,
            date_from=date_from,
            date_to=date_to,
            search=search,
            order_by=sort_by or "created_at",
            order_direction=sort_order or "desc",
            exclude_states=exclude_states if exclude_states else None,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取记忆失败: {e}")
        raise HTTPException(status_code=500, detail=_safe_error_detail(e))


@router.get("/v1/memories/ids/")
async def get_memory_ids(
    user_id: Optional[str] = Query(None),
    categories: Optional[str] = Query(None, description="逗号分隔的分类列表"),
    state: Optional[str] = Query(None, description="记忆状态: active/paused/archived/deleted"),
    date_from: Optional[str] = Query(None, description="起始日期 ISO 格式"),
    date_to: Optional[str] = Query(None, description="截止日期 ISO 格式"),
    search: Optional[str] = Query(None, description="文本搜索关键词"),
    exclude_state: Optional[str] = Query(None, description="排除的记忆状态"),
    show_archived: bool = Query(False, description="是否显示已归档记忆"),
):
    """获取当前筛选条件下的所有记忆 ID（用于前端全选功能）"""
    try:
        cat_list = [c.strip() for c in categories.split(",") if c.strip()] if categories else None
        resolved_state, exclude_states = resolve_list_state_filters(
            state=state, exclude_state=exclude_state, show_archived=show_archived,
        )
        ids = get_all_memory_ids(
            user_id=user_id,
            categories=cat_list,
            state=resolved_state,
            date_from=date_from,
            date_to=date_to,
            search=search,
            exclude_states=exclude_states if exclude_states else None,
        )
        return {"ids": ids, "total": len(ids)}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取记忆 ID 列表失败: {e}")
        raise HTTPException(status_code=500, detail=_safe_error_detail(e))


@router.get("/v1/memories/users/", response_model=List[UserSummaryItem])
async def list_memory_users():
    """获取用户汇总信息（用户列表、筛选器、导出页等复用）。"""
    try:
        return get_users_summary()
    except Exception as e:
        logger.error(f"获取用户汇总失败: {e}")
        raise HTTPException(status_code=500, detail=_safe_error_detail(e))


@router.get("/v1/memories/summary/", response_model=DashboardSummaryResponse)
async def get_dashboard_summary(
    recent_limit: int = Query(5, ge=1, le=20),
    top_users_limit: int = Query(10, ge=1, le=50),
):
    """获取首页摘要（最近记忆 + 活跃用户），避免首页再次拉全量记忆列表。"""
    try:
        return get_memory_summary(limit_recent=recent_limit, limit_top_users=top_users_limit)
    except Exception as e:
        logger.error(f"获取首页摘要失败: {e}")
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
        old_points = qdrant_client.retrieve(
            collection_name=collection_name,
            ids=[memory_id],
            with_payload=True,
        )
        if not old_points:
            raise HTTPException(status_code=404, detail="记忆不存在")

        old_payload = old_points[0].payload or {}
        old_memory_text = old_payload.get("data", old_payload.get("memory", ""))
        old_meta = old_payload.get("metadata", {}) or {}
        old_categories = old_meta.get("categories", [])

        # 第一步：如果有文本更新，先通过 Mem0 SDK 更新（这会重写 Qdrant payload）
        if request.text:
            # m.update 是同步的 Mem0 SDK 调用，放到线程池执行避免阻塞事件循环
            result = await asyncio.to_thread(m.update, memory_id=memory_id, data=request.text)
        else:
            result = {"message": "metadata updated"}

        # 第二步：在文本更新完成后，再读取最新 payload 并修改 metadata
        points = qdrant_client.retrieve(
            collection_name=collection_name,
            ids=[memory_id],
            with_payload=True,
        )
        if not points:
            raise RuntimeError(f"更新后未找到记忆对应向量记录: {memory_id}")

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

        qdrant_client.set_payload(
            collection_name=collection_name,
            payload={"metadata": current_metadata},
            points=[memory_id],
        )

        new_cats = current_metadata.get("categories", [])
        new_memory_text = request.text or current_payload.get("data", old_memory_text)
        # 如果内容没有变化（只改了标签/元数据），old_memory 传 None 避免显示相同的旧/新内容
        effective_old_memory = old_memory_text if (request.text and old_memory_text != new_memory_text) else None
        await asyncio.to_thread(
            save_memory_audit_snapshot,
            memory_id,
            "UPDATE",
            new_memory_text,
            new_cats,
            effective_old_memory,
            old_categories,
        )

        # 双写关系库（对齐 OpenMemory 架构）
        try:
            await asyncio.to_thread(
                meta_service.update_memory_meta,
                memory_id=memory_id,
                content=new_memory_text if request.text else None,
                state=request.state if (request.state and request.state in VALID_STATES) else None,
                categories=new_cats if (request.categories is not None or request.auto_categorize) else None,
                metadata=current_metadata,
                changed_by=old_payload.get("user_id", ""),
                reason="用户更新",
            )
        except Exception as db_err:
            logger.warning(f"关系库双写更新失败（不影响主流程）: {db_err}")

        invalidate_stats_cache()

        logger.info(f"已更新记忆 {memory_id} 的 metadata: state={current_metadata.get('state')}, categories={new_cats}")

        # 触发 Webhook
        try:
            _wh_data = {"memory_id": memory_id, "memory": new_memory_text[:200], "user_id": result.get("user_id", "")}
            asyncio.ensure_future(webhook_service.trigger_webhooks("memory.updated", _wh_data, _mem_svc.http_client))
        except Exception:
            pass

        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"更新记忆失败: {e}")
        raise HTTPException(status_code=500, detail=_safe_error_detail(e))


@router.delete("/v1/memories/{memory_id}/")
async def delete_memory_by_id(memory_id: str):
    """软删除单条记忆（通过统一状态服务将 state 标记为 deleted）"""
    try:
        # 通过统一状态服务执行软删除
        result = await update_memory_state(
            memory_id=memory_id,
            new_state="deleted",
            operator="user",
            reason="api_delete",
        )

        if not result.get("changed", False):
            raise HTTPException(status_code=400, detail="该记忆已处于删除状态，无法重复删除")

        # 记录 DELETE 事件到修改历史
        try:
            collection_name = MEM0_CONFIG["vector_store"]["config"]["collection_name"]
            qdrant_client = get_memory().vector_store.client
            points = qdrant_client.retrieve(collection_name=collection_name, ids=[memory_id], with_payload=True)
            if points:
                payload = points[0].payload or {}
                old_memory_text = payload.get("data", "")
                old_categories = (payload.get("metadata", {}) or {}).get("categories", [])
                save_change_log(memory_id, "DELETE", old_memory_text, old_categories)

                # 触发 Webhook
                try:
                    _wh_data = {"memory_id": memory_id, "memory": old_memory_text[:200] if old_memory_text else "", "user_id": payload.get("user_id", "")}
                    asyncio.ensure_future(webhook_service.trigger_webhooks("memory.deleted", _wh_data, _mem_svc.http_client))
                except Exception:
                    pass
        except Exception as log_err:
            logger.warning(f"删除后记录日志失败（不影响主流程）: {log_err}")

        return {"message": "记忆已删除"}
    except HTTPException:
        raise
    except ValueError as ve:
        raise HTTPException(status_code=404, detail=str(ve))
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


# ============ 硬删除用户接口 ============

@router.delete("/v1/memories/user/{user_id}/hard-delete")
async def hard_delete_user(user_id: str):
    """硬删除用户：物理删除该用户的所有记忆数据和图谱数据（不可恢复）"""
    try:
        from qdrant_client.models import Filter, FieldCondition, MatchValue, PointIdsList
        m = get_memory()
        collection_name = MEM0_CONFIG["vector_store"]["config"]["collection_name"]
        qdrant_client = m.vector_store.client
        total_deleted = 0
        # 1. 分页滚动物理删除该用户在 Qdrant 中的所有记忆（包括已软删除的）
        while True:
            records, _ = qdrant_client.scroll(
                collection_name=collection_name,
                scroll_filter=Filter(
                    must=[
                        FieldCondition(key="user_id", match=MatchValue(value=user_id)),
                    ],
                ),
                limit=100,
                with_payload=False,
                with_vectors=False,
            )
            if not records:
                break
            ids = [str(record.id) for record in records]
            qdrant_client.delete(
                collection_name=collection_name,
                points_selector=PointIdsList(points=ids),
            )
            total_deleted += len(ids)

        # 2. 清理 Neo4j 中该用户的所有图谱实体和关系
        graph_deleted = 0
        try:
            from server.services.graph_service import neo4j_query
            result = neo4j_query(
                "MATCH (n {user_id: $user_id}) DETACH DELETE n RETURN count(n) AS deleted",
                {"user_id": user_id},
            )
            if result:
                graph_deleted = result[0].get("deleted", 0)
            logger.info(f"已清理用户 {user_id} 的图谱数据（删除 {graph_deleted} 个实体及其关系）")
        except Exception as graph_err:
            logger.warning(f"清理用户 {user_id} 的图谱数据失败（不影响记忆删除）: {graph_err}")

        invalidate_stats_cache()
        logger.info(f"已硬删除用户 {user_id} 的所有记忆（共 {total_deleted} 条）")

        # 触发 Webhook（硬删除用户）
        try:
            _wh_data = {
                "user_id": user_id,
"memory": f"用户 {user_id} 已被删除（记忆 {total_deleted} 条，图谱实体 {graph_deleted} 个）",
                "event_detail": "hard_delete_user",
                "deleted_memories_count": total_deleted,
                "deleted_graph_entities_count": graph_deleted,
            }
            asyncio.ensure_future(
                webhook_service.trigger_webhooks("user.hard_deleted", _wh_data, _mem_svc.http_client)
            )
        except Exception:
            pass

        return {
            "message": f"用户 {user_id} 及其所有数据已永久删除（记忆 {total_deleted} 条，图谱实体 {graph_deleted} 个）"
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"硬删除用户失败: {e}")
        raise HTTPException(status_code=500, detail=_safe_error_detail(e))


# ============ 批量删除接口 ============

@router.post("/v1/memories/batch-delete")
async def batch_delete_memories(request: BatchDeleteRequest):
    """批量软删除记忆 — 一次请求删除多条，避免 N 次 HTTP 请求"""
    if not request.memory_ids:
        raise HTTPException(status_code=400, detail="memory_ids 不能为空")

    try:
        m = get_memory()
        collection_name = MEM0_CONFIG["vector_store"]["config"]["collection_name"]
        qdrant_client = m.vector_store.client

        results: List[Optional[Dict[str, Any]]] = [None] * len(request.memory_ids)
        success_count = 0
        failed_count = 0
        pending_delete_items: List[Dict[str, Any]] = []
        deleted_ids: List[str] = []

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

        # 先校验并收集待删除项，不提前记录成功状态
        for idx, mid in enumerate(request.memory_ids):
            point = points_map.get(mid)
            if not point:
                results[idx] = {"id": mid, "success": False, "error": "记忆不存在"}
                failed_count += 1
                continue

            payload = point.payload or {}
            metadata = dict(payload.get("metadata", {}) or {})

            if metadata.get("state") == "deleted":
                results[idx] = {"id": mid, "success": False, "error": "已处于删除状态"}
                failed_count += 1
                continue

            pending_delete_items.append({
                "index": idx,
                "id": mid,
                "metadata": metadata,
                "old_memory_text": payload.get("data", ""),
                "old_categories": metadata.get("categories", []),
            })

        # 真正执行软删除；只有落库成功后才记录成功结果
        for item in pending_delete_items:
            mid = item["id"]
            try:
                metadata = dict(item["metadata"])
                metadata["state"] = "deleted"
                qdrant_client.set_payload(
                    collection_name=collection_name,
                    payload={"metadata": metadata},
                    points=[mid],
                )

                results[item["index"]] = {"id": mid, "success": True}
                success_count += 1
                deleted_ids.append(mid)

                try:
                    save_change_log(mid, "DELETE", item["old_memory_text"], item["old_categories"])
                except Exception as log_err:
                    logger.warning(f"记录批量删除历史失败 memory_id={mid}: {log_err}")
            except Exception as e:
                logger.error(f"批量软删除单条失败 memory_id={mid}: {e}")
                results[item["index"]] = {"id": mid, "success": False, "error": "删除失败"}
                failed_count += 1

        if success_count > 0:
            invalidate_stats_cache()

        final_results = [
            item if item is not None else {"id": request.memory_ids[idx], "success": False, "error": "删除结果未知"}
            for idx, item in enumerate(results)
        ]

        if success_count > 0:
            invalidate_stats_cache()

            # 双写关系库（对齐 OpenMemory 架构）
            try:
                await asyncio.to_thread(
                    meta_service.batch_soft_delete,
                    memory_ids=deleted_ids,
                )
            except Exception as db_err:
                logger.warning(f"关系库批量双写删除失败（不影响主流程）: {db_err}")

        # 触发 Webhook（批量删除汇总通知）
        try:
            # 记忆ID列表截断显示，避免消息过长
            _id_summary = ", ".join(deleted_ids[:5])
            if len(deleted_ids) > 5:
                _id_summary += f" ...等共 {len(deleted_ids)} 条"
            _wh_data = {
                "memory": f"批量删除 {len(request.memory_ids)} 条记忆，成功 {success_count} 条，失败 {failed_count} 条",
                "memory_id": _id_summary,
            }
            asyncio.ensure_future(webhook_service.trigger_webhooks("memory.batch_deleted", _wh_data, _mem_svc.http_client))
        except Exception:
            pass

        return BatchDeleteResponse(
            total=len(request.memory_ids),
            success=success_count,
            failed=failed_count,
            results=final_results,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"批量删除记忆失败: {e}")
        raise HTTPException(status_code=500, detail=_safe_error_detail(e))


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
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取记忆历史失败: {e}")
        raise HTTPException(status_code=500, detail=_safe_error_detail(e))


# ============ 数据迁移 API ============

@router.post("/v1/memories/migrate-to-db/", tags=["系统"])
async def migrate_qdrant_to_db():
    """将 Qdrant 中现有记忆的元数据迁移到关系库（幂等操作，可重复执行）"""
    from server.models.models import MemoryMeta, Category, MemoryStatusHistory, MemoryState, memory_categories as mc_table
    from server.models.database import get_session_factory
    from server.config import VALID_CATEGORIES as _VALID_CATS

    try:
        SessionLocal = get_session_factory()
        db = SessionLocal()

        try:
            # 预创建所有合法分类
            existing_cats = {c.name: c for c in db.query(Category).all()}
            for cat_name in _VALID_CATS:
                if cat_name not in existing_cats:
                    cat = Category(name=cat_name, description=f"预创建分类: {cat_name}")
                    db.add(cat)
                    existing_cats[cat_name] = cat
            db.commit()
            existing_cats = {c.name: c for c in db.query(Category).all()}

            total = 0
            migrated = 0
            skipped = 0
            errors = 0

            from datetime import datetime, timezone
            for memory in get_all_memories_raw(order_by="created_at", order_direction="asc"):
                total += 1
                mid = memory.get("id", "")
                if not mid:
                    errors += 1
                    continue

                existing = db.query(MemoryMeta.id).filter(MemoryMeta.id == mid).first()
                if existing:
                    skipped += 1
                    continue

                try:
                    state_str = memory.get("state", "active")
                    try:
                        state = MemoryState(state_str)
                    except ValueError:
                        state = MemoryState.active

                    created_at = None
                    if memory.get("created_at"):
                        try:
                            created_at = datetime.fromisoformat(str(memory["created_at"]).replace("Z", "+00:00"))
                            if created_at.tzinfo is None:
                                created_at = created_at.replace(tzinfo=timezone.utc)
                        except (ValueError, TypeError):
                            created_at = datetime.now(timezone.utc)

                    updated_at = None
                    if memory.get("updated_at"):
                        try:
                            updated_at = datetime.fromisoformat(str(memory["updated_at"]).replace("Z", "+00:00"))
                            if updated_at.tzinfo is None:
                                updated_at = updated_at.replace(tzinfo=timezone.utc)
                        except (ValueError, TypeError):
                            pass

                    record = MemoryMeta(
                        id=mid,
                        user_id=memory.get("user_id", ""),
                        agent_id=memory.get("agent_id", ""),
                        run_id=memory.get("run_id", ""),
                        content=memory.get("memory", ""),
                        hash=memory.get("hash", ""),
                        metadata_=memory.get("metadata", {}),
                        state=state,
                        created_at=created_at or datetime.now(timezone.utc),
                        updated_at=updated_at,
                        deleted_at=datetime.now(timezone.utc) if state == MemoryState.deleted else None,
                    )

                    categories = memory.get("categories", [])
                    for cat_name in categories:
                        if cat_name in existing_cats:
                            record.categories.append(existing_cats[cat_name])

                    db.add(record)
                    db.add(MemoryStatusHistory(
                        memory_id=mid,
                        old_state=MemoryState.active,
                        new_state=state,
                        changed_by="migration",
                        reason="从 Qdrant 迁移",
                    ))

                    migrated += 1
                    if migrated % 50 == 0:
                        db.commit()
                except Exception as e:
                    errors += 1
                    logger.warning(f"迁移记忆 {mid} 失败: {e}")
                    db.rollback()

            db.commit()
            invalidate_stats_cache()

            return {
                "message": "迁移完成",
                "total_scanned": total,
                "migrated": migrated,
                "skipped": skipped,
                "errors": errors,
            }
        finally:
            db.close()
    except Exception as e:
        logger.error(f"迁移失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=_safe_error_detail(e))


# ============ 状态动作接口（对齐 openmemory） ============

@router.post("/v1/memories/actions/archive")
async def archive_memories(request: BatchStateChangeRequest):
    """归档记忆（单条或批量）— 归档后默认列表不再显示，但可通过筛选查到"""
    try:
        result = await batch_update_memory_state(
            memory_ids=request.memory_ids,
            new_state="archived",
            operator=request.operator or "user",
            reason=request.reason or "manual_archive",
        )

        # 触发 Webhook
        try:
            _wh_data = {
                "memory": f"归档 {result['success']} 条记忆",
                "memory_id": ", ".join(request.memory_ids[:5]),
            }
            asyncio.ensure_future(webhook_service.trigger_webhooks("memory.archived", _wh_data, _mem_svc.http_client))
        except Exception:
            pass

        return result
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        logger.error(f"归档记忆失败: {e}")
        raise HTTPException(status_code=500, detail=_safe_error_detail(e))


@router.post("/v1/memories/actions/pause")
async def pause_memories(request: BatchStateChangeRequest):
    """暂停记忆（单条或批量）— 暂停后仍在默认列表显示，但不参与语义搜索"""
    try:
        result = await batch_update_memory_state(
            memory_ids=request.memory_ids,
            new_state="paused",
            operator=request.operator or "user",
            reason=request.reason or "manual_pause",
        )

        # 触发 Webhook
        try:
            _wh_data = {
                "memory": f"暂停 {result['success']} 条记忆",
                "memory_id": ", ".join(request.memory_ids[:5]),
            }
            asyncio.ensure_future(webhook_service.trigger_webhooks("memory.paused", _wh_data, _mem_svc.http_client))
        except Exception:
            pass

        return result
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        logger.error(f"暂停记忆失败: {e}")
        raise HTTPException(status_code=500, detail=_safe_error_detail(e))


@router.post("/v1/memories/actions/restore")
async def restore_memories(request: RestoreMemoriesRequest):
    """恢复记忆到 active 状态（支持从 archived / paused 恢复，不支持从 deleted 恢复）"""
    try:
        collection_name = MEM0_CONFIG["vector_store"]["config"]["collection_name"]
        qdrant_client = get_memory().vector_store.client
        restorable_ids = []
        rejected = []

        for mid in request.memory_ids:
            try:
                points = qdrant_client.retrieve(collection_name=collection_name, ids=[mid], with_payload=True)
                if not points:
                    rejected.append({"id": mid, "error": "记忆不存在"})
                    continue
                current_state = (points[0].payload or {}).get("metadata", {}).get("state") or "active"
                if current_state == "deleted":
                    rejected.append({"id": mid, "error": "已删除的记忆不支持恢复"})
                elif current_state == "active":
                    rejected.append({"id": mid, "error": "记忆已经是活跃状态"})
                else:
                    restorable_ids.append(mid)
            except Exception as e:
                rejected.append({"id": mid, "error": str(e)})

        result = {"total": len(request.memory_ids), "success": 0, "failed": len(rejected), "results": []}

        if restorable_ids:
            batch_result = await batch_update_memory_state(
                memory_ids=restorable_ids,
                new_state="active",
                operator=request.operator or "user",
                reason=request.reason or "manual_restore",
            )
            result["success"] = batch_result["success"]
            result["failed"] += batch_result["failed"]
            result["results"] = batch_result["results"]

        for r in rejected:
            result["results"].append({"id": r["id"], "success": False, "error": r["error"]})

        # 触发 Webhook
        try:
            _wh_data = {
                "memory": f"恢复 {result['success']} 条记忆",
                "memory_id": ", ".join(restorable_ids[:5]),
            }
            asyncio.ensure_future(webhook_service.trigger_webhooks("memory.restored", _wh_data, _mem_svc.http_client))
        except Exception:
            pass

        return result
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        logger.error(f"恢复记忆失败: {e}")
        raise HTTPException(status_code=500, detail=_safe_error_detail(e))


@router.get("/v1/memories/{memory_id}/state-history")
async def get_memory_state_history(memory_id: str):
    """获取记忆的状态变更历史"""
    try:
        history = meta_service.get_status_history(memory_id)
        return {"memory_id": memory_id, "history": history}
    except Exception as e:
        logger.error(f"获取状态历史失败: {e}")
        raise HTTPException(status_code=500, detail=_safe_error_detail(e))


# ============ 数据回填接口 ============

@router.post("/v1/memories/backfill-state/", tags=["系统"])
async def backfill_memory_state():
    """回填所有缺 state 的记忆为显式 active（幂等操作）。
    同时为已有 deleted 状态的记忆补 deleted_at，为 archived 补 archived_at。"""
    try:
        collection_name = MEM0_CONFIG["vector_store"]["config"]["collection_name"]
        qdrant_client = get_memory().vector_store.client

        total = 0
        backfilled = 0
        already_ok = 0
        errors = 0

        from datetime import datetime as _dt, timezone as _tz
        now_iso = _dt.now(_tz.utc).isoformat()

        for memory in get_all_memories_raw(order_by="created_at", order_direction="asc"):
            total += 1
            mid = memory.get("id", "")
            if not mid:
                errors += 1
                continue

            try:
                points = qdrant_client.retrieve(collection_name=collection_name, ids=[mid], with_payload=True)
                if not points:
                    errors += 1
                    continue

                metadata = dict((points[0].payload or {}).get("metadata", {}) or {})
                needs_update = False

                if not metadata.get("state"):
                    metadata["state"] = "active"
                    metadata["state_updated_at"] = now_iso
                    metadata["state_updated_by"] = "system-migration"
                    needs_update = True

                if metadata.get("state") == "deleted" and not metadata.get("deleted_at"):
                    metadata["deleted_at"] = now_iso
                    needs_update = True

                if metadata.get("state") == "archived" and not metadata.get("archived_at"):
                    metadata["archived_at"] = now_iso
                    needs_update = True

                if not metadata.get("state_updated_at"):
                    metadata["state_updated_at"] = now_iso
                    metadata["state_updated_by"] = "system-migration"
                    needs_update = True

                if needs_update:
                    qdrant_client.set_payload(
                        collection_name=collection_name,
                        payload={"metadata": metadata},
                        points=[mid],
                    )
                    backfilled += 1
                else:
                    already_ok += 1
            except Exception as e:
                errors += 1
                logger.warning(f"回填记忆 {mid} 失败: {e}")

        invalidate_stats_cache()

        return {
            "message": "回填完成",
            "total_scanned": total,
            "backfilled": backfilled,
            "already_ok": already_ok,
            "errors": errors,
        }
    except Exception as e:
        logger.error(f"回填失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=_safe_error_detail(e))
