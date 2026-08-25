"""
Mem0 Dashboard 后端 - 记忆引擎模块（Mem0 + Qdrant 操作）
"""
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional, List, Dict, Any

from app.config import MEM0_CONFIG, QDRANT_DATA_PATH, VALID_CATEGORIES

logger = logging.getLogger(__name__)

# ============ 全局 Memory 实例 ============
memory_instance = None


def get_memory():
    """获取全局 Mem0 Memory 实例（延迟初始化，使用默认配置）"""
    global memory_instance
    if memory_instance is None:
        from mem0 import Memory
        logger.info(f"正在初始化 Mem0，Qdrant 数据目录: {QDRANT_DATA_PATH}")
        memory_instance = Memory.from_config(MEM0_CONFIG)
        logger.info("Mem0 初始化完成")
    return memory_instance


# ============ 租户级 Memory 实例 ============
_tenant_memory_cache: dict = {}  # tenant_id → Memory instance


def get_tenant_memory(tenant_id: str):
    """
    获取租户级 Memory 实例。

    - 如果租户有自定义 LLM/Embedder 配置，则创建独立实例。
    - 如果租户无自定义配置，则复用全局实例（节省资源）。
    - 实例按 tenant_id 缓存，配置变更后需调用 invalidate_tenant_memory() 清除。
    """
    global memory_instance

    from app.tenant_db import get_tenant_config, get_tenant_memory_config

    tenant_cfg = get_tenant_config(tenant_id)
    if not tenant_cfg or (not tenant_cfg.get("llm_config") and not tenant_cfg.get("embedder_config")):
        # 无自定义配置，复用全局实例
        return get_memory()

    # 有自定义配置，检查缓存
    if tenant_id in _tenant_memory_cache:
        return _tenant_memory_cache[tenant_id]

    from mem0 import Memory
    tenant_config = get_tenant_memory_config(tenant_id)
    logger.info(f"正在初始化租户 {tenant_id} 的独立 Memory 实例")
    instance = Memory.from_config(tenant_config)
    _tenant_memory_cache[tenant_id] = instance
    logger.info(f"租户 {tenant_id} Memory 实例初始化完成")
    return instance


def invalidate_tenant_memory(tenant_id: str = None):
    """
    清除租户 Memory 实例缓存。
    tenant_id=None 时清除所有租户缓存（配置全局变更时使用）。
    """
    global _tenant_memory_cache
    if tenant_id:
        _tenant_memory_cache.pop(tenant_id, None)
        logger.info(f"已清除租户 {tenant_id} 的 Memory 实例缓存")
    else:
        _tenant_memory_cache.clear()
        logger.info("已清除所有租户 Memory 实例缓存")


def extract_memory_fields(payload: dict) -> dict:
    """从 Qdrant payload 中提取记忆字段"""
    metadata = payload.get("metadata", {}) or {}
    return {
        "id": str(payload.get("id", "")),
        "memory": payload.get("data", payload.get("memory", "")),
        "user_id": payload.get("user_id", ""),
        "agent_id": payload.get("agent_id", ""),
        "run_id": payload.get("run_id", ""),
        "hash": payload.get("hash", ""),
        "metadata": metadata,
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
    """将 Mem0 返回的记忆对象格式化"""
    metadata = item.get("metadata", {}) or {}
    return {
        "id": item.get("id", ""),
        "memory": item.get("memory", ""),
        "user_id": item.get("user_id", ""),
        "agent_id": item.get("agent_id", ""),
        "run_id": item.get("run_id", ""),
        "hash": item.get("hash", ""),
        "metadata": metadata,
        "categories": metadata.get("categories", []),
        "state": metadata.get("state", "active"),
        "created_at": item.get("created_at", ""),
        "updated_at": item.get("updated_at", ""),
    }


def get_all_memories_raw(max_results: int = None, tenant_id: str = None) -> list:
    """获取所有记忆（完整分页滚动，可选限制最大数量，可选按租户过滤）"""
    m = get_memory()
    try:
        collection_name = MEM0_CONFIG["vector_store"]["config"]["collection_name"]
        qdrant_client = m.vector_store.client
        all_records = []
        offset = None
        batch_size = 256  # 增大批次减少往返次数

        # 构建租户过滤条件
        from qdrant_client.models import ScrollRequest, Filter, FieldCondition, MatchValue
        scroll_filter = None
        if tenant_id:
            scroll_filter = Filter(must=[
                FieldCondition(key="tenant_id", match=MatchValue(value=tenant_id))
            ])

        while True:
            records, next_offset = qdrant_client.scroll(
                collection_name=collection_name,
                limit=batch_size,
                offset=offset,
                with_payload=True,
                with_vectors=False,
                scroll_filter=scroll_filter,
            )
            all_records.extend(records)
            if next_offset is None or not records:
                break
            if max_results is not None and len(all_records) >= max_results:
                all_records = all_records[:max_results]
                break
            offset = next_offset

        return [format_record(record) for record in all_records]
    except Exception as e:
        logger.warning(f"Qdrant 直接查询失败: {e}")
        return []


def get_real_states(memory_ids: list) -> dict:
    """从 Qdrant 直接查询记忆的真实 state"""
    if not memory_ids:
        return {}
    try:
        m = get_memory()
        collection_name = MEM0_CONFIG["vector_store"]["config"]["collection_name"]
        qdrant_client = m.vector_store.client
        points = qdrant_client.retrieve(
            collection_name=collection_name,
            ids=memory_ids,
            with_payload=True,
        )
        state_map = {}
        for p in points:
            pid = str(p.id)
            payload = p.payload or {}
            metadata = payload.get("metadata", {}) or {}
            state_map[pid] = metadata.get("state", "active")
        return state_map
    except Exception as e:
        logger.warning(f"查询记忆真实状态失败: {e}")
        return {}


def apply_filters(memories: list, categories: list = None, state: str = None,
                  date_from: str = None, date_to: str = None, search: str = None) -> list:
    """对记忆列表应用多维筛选"""
    filtered = memories

    if state:
        filtered = [m for m in filtered if m.get("state", "active") == state]

    if categories:
        cat_set = set(categories)
        filtered = [m for m in filtered if set(m.get("categories", [])) & cat_set]

    def _parse_dt(s: str) -> datetime:
        s = s.strip()
        if len(s) == 10 and s[4] == '-' and s[7] == '-':
            return datetime.fromisoformat(s + "T00:00:00+00:00")
        dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt

    if date_from:
        try:
            from_dt = _parse_dt(date_from)
            filtered = [m for m in filtered if m.get("created_at") and
                        _parse_dt(str(m["created_at"])) >= from_dt]
        except (ValueError, TypeError):
            pass

    if date_to:
        try:
            to_dt = _parse_dt(date_to)
            if len(date_to.strip()) == 10:
                to_dt = to_dt.replace(hour=23, minute=59, second=59)
            filtered = [m for m in filtered if m.get("created_at") and
                        _parse_dt(str(m["created_at"])) <= to_dt]
        except (ValueError, TypeError):
            pass

    if search:
        keyword = search.lower()
        filtered = [m for m in filtered if
                    keyword in (m.get("memory", "") or "").lower() or
                    keyword in (m.get("user_id", "") or "").lower() or
                    keyword in (m.get("id", "") or "").lower()]

    return filtered
