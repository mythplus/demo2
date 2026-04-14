"""
记忆状态统一服务 — 所有状态变更都走这里
对齐 openmemory 的状态系统：active / paused / archived / deleted
"""

import asyncio
import logging
from datetime import datetime, timezone
from typing import Optional

from server.config import MEM0_CONFIG, VALID_STATES, _safe_error_detail
from server.services.log_service import save_state_history
from server.services.memory_service import (
    get_memory, invalidate_stats_cache, _get_qdrant_collection_and_client,
)

logger = logging.getLogger(__name__)


# ============ 状态元数据读取 ============

def get_memory_state_metadata(payload: dict) -> dict:
    """从 Qdrant payload 中提取状态相关元数据"""
    metadata = payload.get("metadata", {}) or {}
    return {
        "state": metadata.get("state") or "active",
        "state_updated_at": metadata.get("state_updated_at"),
        "state_updated_by": metadata.get("state_updated_by"),
        "archived_at": metadata.get("archived_at"),
        "deleted_at": metadata.get("deleted_at"),
    }


# ============ 统一状态变更入口 ============

async def update_memory_state(
    memory_id: str,
    new_state: str,
    operator: str = "system",
    reason: str = "",
) -> dict:
    """统一状态变更入口 — 所有状态变更都走这里。
    
    逻辑：
    1. 从 Qdrant 读取当前 payload
    2. 取出旧状态
    3. 校验状态合法性
    4. 幂等：old_state == new_state 直接返回
    5. 更新 metadata（state / state_updated_at / state_updated_by / archived_at / deleted_at）
    6. 写回 Qdrant
    7. 写 memory_state_history
    8. 同步关系库（如果可用）
    9. invalidate_stats_cache
    10. 返回结果
    """
    if new_state not in VALID_STATES:
        raise ValueError(f"无效的状态: {new_state}，合法值: {VALID_STATES}")

    collection_name, qdrant_client = _get_qdrant_collection_and_client()

    # 1. 读取当前 payload
    points = qdrant_client.retrieve(
        collection_name=collection_name,
        ids=[memory_id],
        with_payload=True,
    )
    if not points:
        raise ValueError(f"记忆不存在: {memory_id}")

    payload = points[0].payload or {}
    metadata = dict(payload.get("metadata", {}) or {})
    old_state = metadata.get("state") or "active"

    # 4. 幂等
    if old_state == new_state:
        return {
            "memory_id": memory_id,
            "old_state": old_state,
            "new_state": new_state,
            "changed": False,
            "message": f"状态已经是 {new_state}，无需变更",
        }

    # 5. 更新 metadata
    now_iso = datetime.now(timezone.utc).isoformat()
    metadata["state"] = new_state
    metadata["state_updated_at"] = now_iso
    metadata["state_updated_by"] = operator

    if new_state == "archived":
        metadata["archived_at"] = now_iso
    elif new_state == "deleted":
        metadata["deleted_at"] = now_iso
    # active / paused 不清空历史时间戳，只更新 state_updated_at

    # 6. 写回 Qdrant
    qdrant_client.set_payload(
        collection_name=collection_name,
        payload={"metadata": metadata},
        points=[memory_id],
    )

    # 7. 写状态历史
    try:
        save_state_history(
            memory_id=memory_id,
            old_state=old_state,
            new_state=new_state,
            changed_by=operator,
            reason=reason,
            changed_at=now_iso,
        )
    except Exception as e:
        logger.warning(f"状态历史写入失败（不影响主流程）: {e}")

    # 8. 同步关系库（如果可用）
    try:
        from server.services.meta_service import update_memory_meta
        await asyncio.to_thread(
            update_memory_meta,
            memory_id=memory_id,
            state=new_state,
            metadata=metadata,
            changed_by=operator,
            reason=reason,
        )
    except Exception as db_err:
        logger.warning(f"关系库状态同步失败（不影响主流程）: {db_err}")

    # 9. 缓存失效
    invalidate_stats_cache()

    logger.info(f"记忆 {memory_id} 状态变更: {old_state} -> {new_state} (by {operator}, reason: {reason})")

    return {
        "memory_id": memory_id,
        "old_state": old_state,
        "new_state": new_state,
        "changed": True,
        "state_updated_at": now_iso,
        "message": f"状态已从 {old_state} 变更为 {new_state}",
    }


# ============ 批量状态变更 ============

async def batch_update_memory_state(
    memory_ids: list[str],
    new_state: str,
    operator: str = "system",
    reason: str = "",
) -> dict:
    """批量状态变更"""
    if new_state not in VALID_STATES:
        raise ValueError(f"无效的状态: {new_state}")

    results = []
    success_count = 0
    failed_count = 0

    for mid in memory_ids:
        try:
            result = await update_memory_state(
                memory_id=mid,
                new_state=new_state,
                operator=operator,
                reason=reason,
            )
            results.append({"id": mid, "success": True, **result})
            if result.get("changed", True):
                success_count += 1
            else:
                # 幂等跳过也算成功
                success_count += 1
        except Exception as e:
            results.append({"id": mid, "success": False, "error": str(e)})
            failed_count += 1

    return {
        "total": len(memory_ids),
        "success": success_count,
        "failed": failed_count,
        "results": results,
    }


# ============ 默认列表状态过滤规则 ============

def resolve_list_state_filters(
    state: str | None = None,
    exclude_state: str | None = None,
    show_archived: bool = False,
) -> tuple[str | None, list[str]]:
    """解析列表查询的状态过滤参数。
    
    返回: (state_filter, exclude_states_list)
    
    规则（对齐 openmemory）：
    - 如果明确指定了 state，按指定的查
    - 如果没指定 state：默认排除 deleted 和 archived
    - 如果 show_archived=True：只排除 deleted
    - exclude_state 参数仍然生效
    """
    if state:
        # 明确指定了状态，直接用
        return state, []

    # 没指定 state，应用默认排除规则
    exclude_list = []
    if not show_archived:
        exclude_list.append("archived")
    exclude_list.append("deleted")

    # 额外的 exclude_state
    if exclude_state and exclude_state not in exclude_list:
        exclude_list.append(exclude_state)

    return None, exclude_list
