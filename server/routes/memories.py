"""
记忆 CRUD 路由 — 添加/获取/更新/删除/批量导入/批量删除/修改历史
"""

import asyncio
import logging
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from server.config import MEM0_CONFIG, VALID_CATEGORIES, _safe_error_detail
from server.models.schemas import (
    AddMemoryRequest, UpdateMemoryRequest,
    BatchImportItem, BatchImportRequest, BatchImportResponse, BatchImportResultItem,
    BatchDeleteRequest, BatchDeleteResponse,
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

logger = logging.getLogger(__name__)

router = APIRouter(tags=["记忆管理"])


# ============ 双写重试工具 ============

# B3 P1-9 整改：重试总耗时从 3s（1+2）降到 ~0.6s（0.2+0.4），
# 避免前端 5s 超时期间后端还在重试导致"前端已 abort、后端继续"的错位。
_RETRY_BASE_DELAY = 0.2  # 秒
_RETRY_MAX_DELAY = 1.0   # 秒


async def _retry_db_write(func, *args, max_retries: int = 3, desc: str = "关系库双写", **kwargs):
    """带重试的关系库双写操作，避免 Qdrant 与关系库数据不一致。

    B3 P0-2 整改：全部失败后**抛出原始异常**，而不是静默返回 None。
    这样上层路由的 Qdrant 物理回滚逻辑才能被触发，避免 Qdrant 与关系库数据漂移。
    调用方若希望"PG 失败不阻断主流程"（如审计日志等非关键路径），应在调用点显式 try/except 包裹。

    B3 P1-9 整改：指数退避从 1s/2s 改为 0.2s/0.4s（上限 1s），
    3 次重试总等待 ≤ 0.6s，留足时间给前端 5s 超时前收到响应。

    B3 P2-12 整改：注释与实现对齐 —— 重试"之间"只 sleep max_retries-1 次。
    """
    last_err: Optional[Exception] = None
    for attempt in range(1, max_retries + 1):
        try:
            return await asyncio.to_thread(func, *args, **kwargs)
        except Exception as e:
            last_err = e
            if attempt < max_retries:
                delay = min(_RETRY_BASE_DELAY * (2 ** (attempt - 1)), _RETRY_MAX_DELAY)
                logger.warning(
                    f"{desc}第 {attempt} 次失败，{delay:.1f}s 后重试: {e}",
                    exc_info=True,
                )
                await asyncio.sleep(delay)
            else:
                logger.error(
                    f"{desc}经过 {max_retries} 次重试后仍然失败: {e}",
                    exc_info=True,
                )
    # B3 P0-2：抛出最后一次的原始异常，由调用方决定如何回滚 / 返回给用户
    assert last_err is not None  # 至少进入过一次循环，不可能为 None
    raise last_err


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
        # 如果用户未手动选择标签
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
        # Mem0 的 graph_store 分支与 infer 参数无关，只要启用 graph 就会调 LLM 抽取
        # 实体关系；当 LLM（尤其是本地小模型）返回不规范 JSON 时，mem0 的
        # graph_memory 会抛 KeyError: 'source' / 'destination' / 'relationship' 等，
        # 导致整个 add 失败。这里做一次降级：图谱抽取异常时自动禁用图谱重试，
        # 保证向量库核心写入不被边缘内容阻塞。
        # B3 P2-13：降级捕获从 (KeyError, ValueError, TypeError) 扩大到 Exception，
        # 涵盖 Mem0 自定义异常、AttributeError 等边缘场景，同时记录降级原因便于排查。
        def _add_with_graph_fallback():
            try:
                return m.add(messages=messages, infer=request.infer, **kwargs)
            except Exception as graph_err:
                logger.warning(
                    f"图谱关系抽取失败，降级为仅向量存储后重试：{type(graph_err).__name__}: {graph_err}",
                    exc_info=True,
                )
                with disable_graph(m) as m_no_graph:
                    return m_no_graph.add(messages=messages, infer=request.infer, **kwargs)

        result = await asyncio.to_thread(_add_with_graph_fallback)

        added_items = []
        if isinstance(result, dict) and "results" in result:
            added_items = [r for r in result["results"] if r.get("id")]
        elif isinstance(result, list):
            added_items = [r for r in result if r.get("id")]

        # B3 P0-1 修复：Mem0 返回的 results 中 event 字段可能是 ADD / UPDATE / NONE / DELETE。
        # 只有 event=ADD 才代表"真正新增的 Qdrant 点"，回滚时才能安全删除；
        # UPDATE/NONE/DELETE 事件对应已存在的记忆，误删会造成用户数据丢失。
        added_ids_for_rollback = [
            str(item.get("id"))
            for item in added_items
            if item.get("id") and str(item.get("event", "")).upper() == "ADD"
        ]

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
                event_type = str(item.get("event", "ADD")).upper()

                # 审计日志：记录实际事件类型（ADD / UPDATE）
                save_memory_audit_snapshot(mid, event_type, memory_text, init_cats)

                # 双写关系库：根据 Mem0 返回的 event 区分 INSERT / UPDATE
                # Mem0 SDK 对语义相似的内容会复用已有 ID 并返回 event=UPDATE，
                # 此时 PG 中该 ID 已存在，必须走 update 而非 insert，否则主键冲突。
                if event_type == "UPDATE":
                    update_result = await _retry_db_write(
                        meta_service.update_memory_meta,
                        memory_id=mid,
                        content=memory_text,
                        categories=init_cats,
                        metadata=current_meta,
                        desc=f"更新记忆 {mid} 关系库双写（Mem0 UPDATE 事件）",
                    )
                    # 兜底：如果 PG 中该记录不存在（之前双写失败过），fallback 到 create
                    if update_result is None:
                        logger.warning(f"Mem0 返回 UPDATE 事件但 PG 中无记录 {mid}，降级为 INSERT")
                        await _retry_db_write(
                            meta_service.create_memory_meta,
                            memory_id=mid,
                            user_id=user_id,
                            content=memory_text,
                            hash_value=item.get("hash", "") if isinstance(item, dict) else "",
                            agent_id=request.agent_id or "",
                            run_id=request.run_id or "",
                            categories=init_cats,
                            metadata=current_meta,
                            desc=f"添加记忆 {mid} 关系库双写（UPDATE 降级 INSERT）",
                        )
                else:
                    await _retry_db_write(
                        meta_service.create_memory_meta,
                        memory_id=mid,
                        user_id=user_id,
                        content=memory_text,
                        hash_value=item.get("hash", "") if isinstance(item, dict) else "",
                        agent_id=request.agent_id or "",
                        run_id=request.run_id or "",
                        categories=init_cats,
                        metadata=current_meta,
                        desc=f"添加记忆 {mid} 关系库双写",
                    )

        invalidate_stats_cache()

        # 触发 Webhook（托管到统一后台任务管理器）
        _wh_data = {
            "user_id": user_id,
            "memory": " ".join(msg.content for msg in request.messages)[:200],
            "memory_id": ", ".join(added_ids_for_rollback) if added_ids_for_rollback else "",
        }
        webhook_service.schedule_webhook_delivery("memory.added", _wh_data, _mem_svc.http_client)


        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("添加记忆失败")

        if added_ids_for_rollback:
            try:
                from qdrant_client.models import PointIdsList
                collection_name = MEM0_CONFIG["vector_store"]["config"]["collection_name"]
                qdrant_client = get_memory().vector_store.client
                qdrant_client.delete(
                    collection_name=collection_name,
                    points_selector=PointIdsList(points=added_ids_for_rollback),
                )
                invalidate_stats_cache()
                logger.warning(f"添加记忆补写失败，已物理回滚 {len(added_ids_for_rollback)} 条记忆")
            except Exception as rollback_err:
                logger.error(f"添加记忆补写失败后的物理回滚也失败: {rollback_err}")

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
        """将已新增但补写失败的记忆物理删除。"""
        if not memory_ids:
            return
        from qdrant_client.models import PointIdsList
        qdrant_client.delete(
            collection_name=collection_name,
            points_selector=PointIdsList(points=memory_ids),
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
                    with disable_graph(m) as m_no_graph:
                        return m_no_graph.add(messages=messages, infer=request.infer, **kwargs)
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
                        # B3 P2-2: save_memory_audit_snapshot 内部已是队列投递，无需 to_thread
                        save_memory_audit_snapshot(mid, "ADD", memory_text, init_cats)

                        # 双写关系库（对齐 OpenMemory 架构，带重试）
                        await _retry_db_write(
                            meta_service.create_memory_meta,
                            memory_id=mid,
                            user_id=uid,
                            content=memory_text,
                            hash_value=added_item.get("hash", "") if isinstance(added_item, dict) else "",
                            categories=init_cats,
                            metadata=(_pts[0].payload or {}).get("metadata", {}) if _pts else {},
                            desc=f"批量导入第 {idx+1} 条关系库双写",
                        )
                    except Exception as audit_err:
                        logger.warning(f"批量导入第 {idx+1} 条审计日志写入失败（记忆已成功导入）: {audit_err}", exc_info=True)

                first_id = None
                first_memory = None
                if isinstance(result, dict) and "results" in result and result["results"]:
                    first_id = result["results"][0].get("id")
                    first_memory = result["results"][0].get("memory")

                return BatchImportResultItem(
                    index=idx, success=True, id=first_id, memory=first_memory
                )
            except Exception as e:
                # B3 P1-1: 用 error + exc_info 记录完整堆栈，便于排查"多行添加失败"根因
                logger.error(f"批量导入第 {idx+1} 条失败: {e}", exc_info=True)
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
    # 注意：使用 return_exceptions=True，保证即便 _process_single_item 未预期抛出异常
    # （例如 TaskGroup 内的取消、KeyboardInterrupt 子类等），也不会让整个批量请求 500，
    # 其它已成功的记忆依然能在响应中返回给前端。
    tasks = [_process_single_item(idx, item) for idx, item in enumerate(request.items)]
    raw_results = await asyncio.gather(*tasks, return_exceptions=True)

    # 把裸异常转换为 BatchImportResultItem，保持返回值类型一致
    results: list[BatchImportResultItem] = []
    for idx, r in enumerate(raw_results):
        if isinstance(r, Exception):
            logger.error(
                f"批量导入第 {idx+1} 条出现未预期异常（已被 gather 捕获）: {r}",
                exc_info=r,
            )
            results.append(
                BatchImportResultItem(
                    index=idx, success=False, error=_safe_error_detail(r)
                )
            )
        else:
            results.append(r)

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
    parts = [f"批量导入 {request.total} 条记忆，成功 {request.success} 条，失败 {request.failed} 条"]
    if request.skipped > 0:
        parts.append(f"跳过 {request.skipped} 条")
    _wh_data = {
        "memory": "，".join(parts),
        "memory_id": "",
    }
    webhook_service.schedule_webhook_delivery("memory.batch_imported", _wh_data, _mem_svc.http_client)

    return {"message": "通知已发送"}


@router.get("/v1/memories/")
async def get_memories(
    user_id: Optional[str] = Query(None),
    categories: Optional[str] = Query(None, description="逗号分隔的分类列表"),
    date_from: Optional[str] = Query(None, description="起始日期 ISO 格式"),
    date_to: Optional[str] = Query(None, description="截止日期 ISO 格式"),
    search: Optional[str] = Query(None, description="文本搜索关键词"),
    page: Optional[int] = Query(None, ge=1, description="页码，传入后启用服务端分页"),
    page_size: Optional[int] = Query(None, ge=1, le=200, description="每页条数，默认 20，最大 200"),
    sort_by: Optional[str] = Query("created_at", description="排序字段: created_at/updated_at"),
    sort_order: Optional[str] = Query("desc", description="排序方向: asc/desc"),
):
    """获取记忆列表"""
    try:
        cat_list = [c.strip() for c in categories.split(",") if c.strip()] if categories else None

        if page is not None or page_size is not None:
            return get_memories_page(
                user_id=user_id,
                categories=cat_list,
                date_from=date_from,
                date_to=date_to,
                search=search,
                page=page or 1,
                page_size=page_size or 20,
                order_by=sort_by or "created_at",
                order_direction=sort_order or "desc",
            )

        return get_all_memories_raw(
            user_id=user_id,
            categories=cat_list,
            date_from=date_from,
            date_to=date_to,
            search=search,
            order_by=sort_by or "created_at",
            order_direction=sort_order or "desc",
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
    date_from: Optional[str] = Query(None, description="起始日期 ISO 格式"),
    date_to: Optional[str] = Query(None, description="截止日期 ISO 格式"),
    search: Optional[str] = Query(None, description="文本搜索关键词"),
):
    """获取当前筛选条件下的所有记忆 ID（用于前端全选功能）"""
    try:
        cat_list = [c.strip() for c in categories.split(",") if c.strip()] if categories else None
        ids = get_all_memory_ids(
            user_id=user_id,
            categories=cat_list,
            date_from=date_from,
            date_to=date_to,
            search=search,
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

        # 合并其他 metadata
        if request.metadata is not None:
            for k, v in request.metadata.items():
                if k not in ("categories",):
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

        # B3 P1-5 修复：双写关系库失败时，尝试回滚 Qdrant 到旧状态，
        # 避免 Qdrant 已更新但 PG 还是旧数据的漂移。
        try:
            await _retry_db_write(
                meta_service.update_memory_meta,
                memory_id=memory_id,
                content=new_memory_text if request.text else None,
                categories=new_cats if (request.categories is not None or request.auto_categorize) else None,
                metadata=current_metadata,
                desc=f"更新记忆 {memory_id} 关系库双写",
            )
        except Exception as db_err:
            logger.error(f"更新记忆 {memory_id} 关系库双写失败，尝试回滚 Qdrant: {db_err}", exc_info=True)
            # 尝试把 Qdrant 的 metadata 恢复到更新前的状态
            try:
                qdrant_client.set_payload(
                    collection_name=collection_name,
                    payload={"metadata": old_meta},
                    points=[memory_id],
                )
                if request.text:
                    # 文本也要回滚（通过 Mem0 SDK）
                    await asyncio.to_thread(m.update, memory_id=memory_id, data=old_memory_text)
                logger.info(f"Qdrant 回滚成功: {memory_id}")
            except Exception as rollback_err:
                logger.error(f"Qdrant 回滚也失败（数据可能不一致）: {rollback_err}", exc_info=True)
            raise HTTPException(
                status_code=500,
                detail="关系库同步失败，已尝试回滚向量库。请重新保存。",
            )

        invalidate_stats_cache()

        logger.info(f"已更新记忆 {memory_id} 的 metadata: categories={new_cats}")

        # 触发 Webhook（托管到统一后台任务管理器）
        _wh_data = {"memory_id": memory_id, "memory": new_memory_text[:200], "user_id": old_payload.get("user_id", "")}
        webhook_service.schedule_webhook_delivery("memory.updated", _wh_data, _mem_svc.http_client)


        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"更新记忆失败: {e}")
        raise HTTPException(status_code=500, detail=_safe_error_detail(e))


@router.delete("/v1/memories/{memory_id}/")
async def delete_memory_by_id(memory_id: str):
    """物理删除单条记忆 — 从 Qdrant 与关系库中彻底抹除，**不可恢复**。"""
    try:
        from qdrant_client.models import PointIdsList

        collection_name = MEM0_CONFIG["vector_store"]["config"]["collection_name"]
        qdrant_client = get_memory().vector_store.client

        # 1. 先从 Qdrant 获取记忆信息（用于日志和 Webhook）
        # B3 P1-4 修复：区分"记忆不存在"（404）和"Qdrant 连接失败"（503）
        old_memory_text = ""
        old_categories: list = []
        user_id = ""
        try:
            points = qdrant_client.retrieve(collection_name=collection_name, ids=[memory_id], with_payload=True)
            if points:
                payload = points[0].payload or {}
                old_memory_text = payload.get("data", "")
                old_categories = (payload.get("metadata", {}) or {}).get("categories", [])
                user_id = payload.get("user_id", "")
            else:
                raise HTTPException(status_code=404, detail="记忆不存在")
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Qdrant 查询记忆失败（无法确认记忆是否存在）: {e}", exc_info=True)
            raise HTTPException(status_code=503, detail=f"向量数据库暂不可用: {_safe_error_detail(e)}")

        # 2. 物理删除 Qdrant 中的向量
        try:
            qdrant_client.delete(
                collection_name=collection_name,
                points_selector=PointIdsList(points=[memory_id]),
            )
        except Exception as e:
            logger.error(f"Qdrant 物理删除失败: {e}")
            raise HTTPException(status_code=500, detail=_safe_error_detail(e))

        # 3. 关系库物理删除（带重试）
        await _retry_db_write(
            meta_service.hard_delete_memory_meta, memory_id,
            desc=f"物理删除记忆 {memory_id} 关系库",
        )

        # 4. 记录 DELETE 事件到修改历史
        try:
            save_change_log(memory_id, "DELETE", old_memory_text, old_categories)
        except Exception as log_err:
            logger.warning(f"记录删除日志失败（不影响主流程）: {log_err}", exc_info=True)

        # 5. 触发 Webhook（托管到统一后台任务管理器）
        _wh_data = {"memory_id": memory_id, "memory": old_memory_text[:200] if old_memory_text else "", "user_id": user_id}
        webhook_service.schedule_webhook_delivery("memory.deleted", _wh_data, _mem_svc.http_client)

        invalidate_stats_cache()
        return {"message": "记忆已删除（不可恢复）"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"删除记忆失败: {e}")
        raise HTTPException(status_code=500, detail=_safe_error_detail(e))


@router.delete("/v1/memories/{memory_id}/hard-delete")
async def hard_delete_memory_by_id(memory_id: str):
    """物理删除单条记忆 — 从 Qdrant 和关系库中彻底删除，不可恢复。
    （与 DELETE /v1/memories/{memory_id}/ 等效，保留此端点用于外部显式调用场景。）"""
    try:
        from qdrant_client.models import PointIdsList

        collection_name = MEM0_CONFIG["vector_store"]["config"]["collection_name"]
        qdrant_client = get_memory().vector_store.client

        # B3 P0-4 修复：区分"记忆不存在"（404）和"Qdrant 连接失败"（503），
        # 不再把连接异常伪装成"没数据"后继续执行删除。
        old_memory_text = ""
        old_categories: list = []
        user_id = ""
        try:
            points = qdrant_client.retrieve(collection_name=collection_name, ids=[memory_id], with_payload=True)
            if points:
                payload = points[0].payload or {}
                old_memory_text = payload.get("data", "")
                old_categories = (payload.get("metadata", {}) or {}).get("categories", [])
                user_id = payload.get("user_id", "")
            else:
                raise HTTPException(status_code=404, detail="记忆不存在")
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Qdrant 查询记忆失败（无法确认记忆是否存在）: {e}", exc_info=True)
            raise HTTPException(status_code=503, detail=f"向量数据库暂不可用: {_safe_error_detail(e)}")

        # 2. 物理删除 Qdrant 中的向量
        qdrant_client.delete(
            collection_name=collection_name,
            points_selector=PointIdsList(points=[memory_id]),
        )

        # 3. 物理删除关系库中的元数据（带重试；失败不阻断，但记录错误）
        try:
            await _retry_db_write(
                meta_service.hard_delete_memory_meta, memory_id,
                desc=f"硬删除记忆 {memory_id} 关系库物理删除",
            )
        except Exception as db_err:
            logger.error(f"硬删除记忆 {memory_id} 关系库失败（Qdrant 已删）: {db_err}", exc_info=True)
        if user_id:
            try:
                from server.services.graph_service import neo4j_query
                neo4j_query(
                    "MATCH (n {user_id: $user_id}) WHERE NOT (n)-[]-() DELETE n",
                    {"user_id": user_id},
                )
            except Exception as graph_err:
                logger.warning(f"清理 Neo4j 孤儿实体失败（不影响主流程）: {graph_err}")

        # 5. 记录 HARD_DELETE 事件
        try:
            save_change_log(memory_id, "HARD_DELETE", old_memory_text, old_categories)
        except Exception as log_err:
            logger.warning(f"记录硬删除日志失败（不影响主流程）: {log_err}")

        # 6. 触发 Webhook
        _wh_data = {"memory_id": memory_id, "memory": old_memory_text[:200] if old_memory_text else "", "user_id": user_id}
        webhook_service.schedule_webhook_delivery("memory.hard_deleted", _wh_data, _mem_svc.http_client)

        invalidate_stats_cache()
        return {"message": "记忆已永久删除（不可恢复）"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"硬删除记忆失败: {e}")
        raise HTTPException(status_code=500, detail=_safe_error_detail(e))


@router.delete("/v1/memories/")
async def delete_all_memories(
    user_id: Optional[str] = Query(None),
    confirm: bool = Query(False, description="清空全部记忆时必须传 confirm=true 以防误操作"),
):
    """物理删除用户的所有记忆（或全部记忆）— **不可恢复**，直接从 Qdrant 和关系库中抹除。
    清空全部时需要 confirm=true 确认。仅适用于开发调试或明确的数据清理需求。"""
    try:
        from qdrant_client.models import Filter, FieldCondition, MatchValue, PointIdsList
        m = get_memory()
        collection_name = MEM0_CONFIG["vector_store"]["config"]["collection_name"]
        qdrant_client = m.vector_store.client

        # 无 user_id 时必须显式确认
        if not user_id and not confirm:
            raise HTTPException(
                status_code=400,
                detail="清空全部记忆是危险操作，请传入 confirm=true 参数以确认执行",
            )

        scroll_filter = None
        if user_id:
            scroll_filter = Filter(
                must=[FieldCondition(key="user_id", match=MatchValue(value=user_id))],
            )

        # B3 P0-3 修复：用 try/finally 保证 invalidate_stats_cache 一定执行；
        # 每页的 PG 删除失败不阻断后续页（记录 warning），但 Qdrant 删除失败立即中止。
        total_deleted = 0
        next_offset = None
        try:
            while True:
                records, next_offset = qdrant_client.scroll(
                    collection_name=collection_name,
                    scroll_filter=scroll_filter,
                    limit=100,
                    offset=next_offset,
                    with_payload=True,
                    with_vectors=False,
                )
                if not records:
                    break
                ids = [str(record.id) for record in records]

                # 记录删除日志（非关键路径，失败只 warning）
                for point in records:
                    mid = str(point.id)
                    payload = point.payload or {}
                    try:
                        old_memory_text = payload.get("data", "")
                        old_categories = (payload.get("metadata", {}) or {}).get("categories", [])
                        save_change_log(mid, "DELETE", old_memory_text, old_categories)
                    except Exception as e:
                        # 非关键路径：记录 DELETE 审计日志失败不影响删除主流程，
                        # 但必须留下 warning，方便后续排查“删除记录丢失”类问题（禁止静默失败）
                        logger.warning(
                            f"记录 DELETE 审计日志失败 memory_id={mid}: {e}",
                            exc_info=True,
                        )

                # 物理删除 Qdrant 向量
                try:
                    qdrant_client.delete(
                        collection_name=collection_name,
                        points_selector=PointIdsList(points=ids),
                    )
                except Exception as e:
                    logger.error(f"Qdrant 批量删除失败: {e}", exc_info=True)
                    raise HTTPException(status_code=500, detail=_safe_error_detail(e))

                # 关系库批量物理删除（B3 P0-2 改造后失败会抛异常，这里 catch 住避免中断循环）
                try:
                    await _retry_db_write(
                        meta_service.batch_hard_delete_memory_meta, ids,
                        desc=f"{'用户 ' + user_id if user_id else '全部'} 关系库批量物理删除",
                    )
                except Exception as db_err:
                    logger.error(f"关系库批量删除失败（Qdrant 已删，数据可能不一致）: {db_err}", exc_info=True)

                total_deleted += len(ids)
                if next_offset is None:
                    break
        finally:
            # B3 P0-3：无论成功/失败/中途异常，都刷新统计缓存
            invalidate_stats_cache()
        scope_label = f"用户 {user_id}" if user_id else "所有"

        # 触发 Webhook 通知：带 user_id 视为"清空该用户"（user.hard_deleted），
        # 否则是危险的全库清空（memory.batch_hard_deleted）。
        # 与 hard_delete_user / 单条硬删 等路径保持事件语义一致，避免用户详情页
        # 清空记忆时订阅"用户删除"的 Webhook 收不到通知。
        try:
            if user_id:
                _wh_data = {
                    "user_id": user_id,
                    "memory": f"用户 {user_id} 的所有记忆已清空（共 {total_deleted} 条）",
                    "event_detail": "delete_all_memories_by_user",
                    "deleted_memories_count": total_deleted,
                }
                webhook_service.schedule_webhook_delivery(
                    "user.hard_deleted", _wh_data, _mem_svc.http_client
                )
            else:
                _wh_data = {
                    "memory": f"全库记忆已永久清空（共 {total_deleted} 条）",
                    "event_detail": "delete_all_memories_global",
                    "deleted_memories_count": total_deleted,
                }
                webhook_service.schedule_webhook_delivery(
                    "memory.batch_hard_deleted", _wh_data, _mem_svc.http_client
                )
        except Exception as wh_err:
            # Webhook 属于旁路通知，失败不应影响主流程的删除结果
            logger.warning(f"delete_all_memories Webhook 派发失败（不影响主流程）: {wh_err}")

        return {
            "message": f"{scope_label}的记忆已永久删除（共 {total_deleted} 条，不可恢复）",
            "deleted": total_deleted,
        }
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
        next_offset = None
        # 1. 分页滚动物理删除该用户在 Qdrant 中的所有记忆（包括已软删除的）
        while True:
            records, next_offset = qdrant_client.scroll(
                collection_name=collection_name,
                scroll_filter=Filter(
                    must=[
                        FieldCondition(key="user_id", match=MatchValue(value=user_id)),
                    ],
                ),
                limit=100,
                offset=next_offset,
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
            if next_offset is None:
                break

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

        # 3. 清理 PostgreSQL memories_meta 表中该用户的所有记忆元数据
        meta_deleted = 0
        try:
            meta_deleted = await _retry_db_write(
                meta_service.hard_delete_user_memory_meta,
                user_id,
                desc=f"用户 {user_id} 关系库物理删除",
            ) or 0
        except Exception as db_err:
            logger.error(f"清理用户 {user_id} 的关系库元数据失败: {db_err}")


        invalidate_stats_cache()
        logger.info(f"已硬删除用户 {user_id} 的所有记忆（共 {total_deleted} 条）")

        # 触发 Webhook（硬删除用户，托管到统一后台任务管理器）
        _wh_data = {
            "user_id": user_id,
            "memory": f"用户 {user_id} 已被删除（记忆 {total_deleted} 条，图谱实体 {graph_deleted} 个）",
            "event_detail": "hard_delete_user",
            "deleted_memories_count": total_deleted,
            "deleted_graph_entities_count": graph_deleted,
        }
        webhook_service.schedule_webhook_delivery("user.hard_deleted", _wh_data, _mem_svc.http_client)


        return {
            "message": f"用户 {user_id} 及其所有数据已永久删除（记忆 {total_deleted} 条，图谱实体 {graph_deleted} 个，元数据 {meta_deleted} 条）"
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"硬删除用户失败: {e}")
        raise HTTPException(status_code=500, detail=_safe_error_detail(e))


# ============ 批量删除接口 ============

@router.post("/v1/memories/batch-delete")
async def batch_delete_memories(request: BatchDeleteRequest):
    """批量物理删除记忆 — 从 Qdrant 和关系库中彻底删除，**不可恢复**。"""
    if not request.memory_ids:
        raise HTTPException(status_code=400, detail="memory_ids 不能为空")

    try:
        from qdrant_client.models import PointIdsList
        m = get_memory()
        collection_name = MEM0_CONFIG["vector_store"]["config"]["collection_name"]
        qdrant_client = m.vector_store.client

        results: List[Optional[Dict[str, Any]]] = [None] * len(request.memory_ids)
        success_count = 0
        failed_count = 0
        deleted_ids: List[str] = []

        # 批量获取所有记忆的当前信息（用于日志）
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

        # 逐条删除
        for idx, mid in enumerate(request.memory_ids):
            point = points_map.get(mid)
            if not point:
                results[idx] = {"id": mid, "success": False, "error": "记忆不存在"}
                failed_count += 1
                continue

            try:
                payload = point.payload or {}
                old_memory_text = payload.get("data", "")
                old_categories = (payload.get("metadata", {}) or {}).get("categories", [])

                # 记录删除日志
                try:
                    save_change_log(mid, "DELETE", old_memory_text, old_categories)
                except Exception as log_err:
                    logger.warning(f"记录批量删除历史失败 memory_id={mid}: {log_err}")

                results[idx] = {"id": mid, "success": True}
                success_count += 1
                deleted_ids.append(mid)
            except Exception as e:
                logger.error(f"批量删除单条处理失败 memory_id={mid}: {e}")
                results[idx] = {"id": mid, "success": False, "error": "删除失败"}
                failed_count += 1

        final_results = [
            item if item is not None else {"id": request.memory_ids[idx], "success": False, "error": "删除结果未知"}
            for idx, item in enumerate(results)
        ]

        if deleted_ids:
            # 物理删除 Qdrant 向量
            try:
                qdrant_client.delete(
                    collection_name=collection_name,
                    points_selector=PointIdsList(points=deleted_ids),
                )
            except Exception as e:
                logger.error(f"Qdrant 批量物理删除失败: {e}")
                raise HTTPException(status_code=500, detail=_safe_error_detail(e))

            invalidate_stats_cache()

            # 关系库批量物理删除（带重试）
            await _retry_db_write(
                meta_service.batch_hard_delete_memory_meta,
                memory_ids=deleted_ids,
                desc="批量删除关系库物理删除",
            )

        # 触发 Webhook（批量删除汇总通知，托管到统一后台任务管理器）
        _id_summary = ", ".join(deleted_ids[:5])
        if len(deleted_ids) > 5:
            _id_summary += f" ...等共 {len(deleted_ids)} 条"
        _wh_data = {
            "memory": f"批量删除 {len(request.memory_ids)} 条记忆（不可恢复），成功 {success_count} 条，失败 {failed_count} 条",
            "memory_id": _id_summary,
        }
        webhook_service.schedule_webhook_delivery("memory.batch_deleted", _wh_data, _mem_svc.http_client)


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


@router.post("/v1/memories/batch-hard-delete")
async def batch_hard_delete_memories(request: BatchDeleteRequest):
    """批量物理删除记忆 — 从 Qdrant 和关系库中彻底删除，**不可恢复**。
    （与 /v1/memories/batch-delete 等效，保留此端点用于外部显式调用场景。）"""
    if not request.memory_ids:
        raise HTTPException(status_code=400, detail="memory_ids 不能为空")

    try:
        from qdrant_client.models import PointIdsList
        m = get_memory()
        collection_name = MEM0_CONFIG["vector_store"]["config"]["collection_name"]
        qdrant_client = m.vector_store.client

        results: List[Optional[Dict[str, Any]]] = [None] * len(request.memory_ids)
        success_count = 0
        failed_count = 0
        deleted_ids: List[str] = []
        points_map: Dict[str, Any] = {}

        try:
            points = qdrant_client.retrieve(
                collection_name=collection_name,
                ids=request.memory_ids,
                with_payload=True,
            )
            points_map = {str(p.id): p for p in points}
        except Exception as e:
            logger.warning(f"批量硬删查询记忆失败（继续尝试）: {e}")

        for idx, mid in enumerate(request.memory_ids):
            try:
                point = points_map.get(mid)
                payload = (point.payload if point else {}) or {}
                old_memory_text = payload.get("data", "")
                old_categories = (payload.get("metadata", {}) or {}).get("categories", [])

                qdrant_client.delete(
                    collection_name=collection_name,
                    points_selector=PointIdsList(points=[mid]),
                )

                try:
                    save_change_log(mid, "HARD_DELETE", old_memory_text, old_categories)
                except Exception as log_err:
                    logger.warning(f"记录批量硬删历史失败 memory_id={mid}: {log_err}")

                results[idx] = {"id": mid, "success": True}
                success_count += 1
                deleted_ids.append(mid)
            except Exception as e:
                logger.error(f"批量硬删单条失败 memory_id={mid}: {e}")
                results[idx] = {"id": mid, "success": False, "error": "删除失败"}
                failed_count += 1

        final_results = [
            item if item is not None else {"id": request.memory_ids[idx], "success": False, "error": "删除结果未知"}
            for idx, item in enumerate(results)
        ]

        if success_count > 0:
            invalidate_stats_cache()
            await _retry_db_write(
                meta_service.batch_hard_delete_memory_meta,
                memory_ids=deleted_ids,
                desc="批量硬删关系库物理删除",
            )
            # 清理 Neo4j 孤儿实体
            try:
                deleted_user_ids = set()
                for mid in deleted_ids:
                    point = points_map.get(mid)
                    if point and point.payload:
                        uid = point.payload.get("user_id", "")
                        if uid:
                            deleted_user_ids.add(uid)
                if deleted_user_ids:
                    from server.services.graph_service import neo4j_query
                    for uid in deleted_user_ids:
                        neo4j_query(
                            "MATCH (n {user_id: $user_id}) WHERE NOT (n)-[]-() DELETE n",
                            {"user_id": uid},
                        )
            except Exception as graph_err:
                logger.warning(f"清理 Neo4j 孤儿实体失败（不影响主流程）: {graph_err}")

        _id_summary = ", ".join(deleted_ids[:5])
        if len(deleted_ids) > 5:
            _id_summary += f" ...等共 {len(deleted_ids)} 条"
        _wh_data = {
            "memory": f"批量硬删除 {len(request.memory_ids)} 条记忆，成功 {success_count} 条，失败 {failed_count} 条（不可恢复）",
            "memory_id": _id_summary,
        }
        webhook_service.schedule_webhook_delivery("memory.batch_hard_deleted", _wh_data, _mem_svc.http_client)

        return BatchDeleteResponse(
            total=len(request.memory_ids),
            success=success_count,
            failed=failed_count,
            results=final_results,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"批量硬删记忆失败: {e}")
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
        except Exception as e:
            # 查询 Qdrant 当前分类失败属非关键路径（展示历史时有 categories 更好，
            # 没有也不影响主流程），但必须记录 warning，避免静默失败
            logger.warning(
                f"获取记忆当前分类失败 memory_id={memory_id}: {e}",
                exc_info=True,
            )

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
    """将 Qdrant 中现有记忆的元数据迁移到关系库（幂等操作，可重复执行）

    B3 P1-6 整改：生产环境禁止调用（应通过运维脚本或 alembic 迁移完成），
    避免任何人通过 API 触发全量扫描拖垮 PG 连接池。
    """
    from server.config import IS_PRODUCTION
    if IS_PRODUCTION:
        raise HTTPException(
            status_code=403,
            detail="生产环境禁止通过 API 触发数据迁移。请使用运维脚本或 alembic 迁移。",
        )

    from server.models.models import MemoryMeta, Category, memory_categories as mc_table
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
                        except (ValueError, TypeError) as e:
                            # 迁移场景：旧数据 updated_at 格式不规范时允许降级为 None，
                            # 但必须留下 warning，避免迁移结果默默丢字段
                            logger.warning(
                                f"迁移时解析 updated_at 失败 memory_id={mid}, value={memory.get('updated_at')!r}: {e}"
                            )

                    record = MemoryMeta(
                        id=mid,
                        user_id=memory.get("user_id", ""),
                        agent_id=memory.get("agent_id", ""),
                        run_id=memory.get("run_id", ""),
                        content=memory.get("memory", ""),
                        hash=memory.get("hash", ""),
                        metadata_=memory.get("metadata", {}),
                        created_at=created_at or datetime.now(timezone.utc),
                        updated_at=updated_at,
                    )

                    categories = memory.get("categories", [])
                    for cat_name in categories:
                        if cat_name in existing_cats:
                            record.categories.append(existing_cats[cat_name])

                    db.add(record)

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
