"""
记忆核心服务 — Mem0 实例管理、数据格式化、AI 自动分类、Qdrant 向量操作
对齐 OpenMemory 官方架构：结构化查询走关系库（meta_service），向量搜索走 Qdrant
"""

import asyncio
import copy
import json
import time
import logging
from typing import List, Dict, Any, Iterator
from datetime import datetime, timezone
from contextlib import contextmanager


import httpx
from qdrant_client.http.models import (
    DatetimeRange, Direction, FieldCondition, Filter, MatchAny, MatchValue, OrderBy,
)

from server.config import (
    MEM0_CONFIG, QDRANT_DATA_PATH, VALID_CATEGORIES,
    CATEGORY_DESCRIPTIONS, MEMORY_CATEGORIZATION_PROMPT,
)

logger = logging.getLogger(__name__)

# ============ 全局 Memory 实例 ============
memory_instance = None

# ============ 全局异步 HTTP 客户端（由 app.py lifespan 初始化） ============
http_client: httpx.AsyncClient | None = None


def get_memory():
    """获取 Mem0 Memory 实例（延迟初始化）"""
    global memory_instance
    if memory_instance is None:
        from mem0 import Memory
        logger.info(f"正在初始化 Mem0，Qdrant 数据目录: {QDRANT_DATA_PATH}")
        memory_instance = Memory.from_config(MEM0_CONFIG)
        logger.info("Mem0 初始化完成")
    return memory_instance


@contextmanager
def disable_graph(m):
    """上下文管理器：返回一个共享底层资源但禁用图谱的 Memory 代理实例。
    批量导入时使用，避免在共享单例上临时切换 enable_graph 导致并发污染。"""
    graph_disabled_memory = copy.copy(m)
    graph_disabled_memory.enable_graph = False
    graph_disabled_memory.graph = None
    yield graph_disabled_memory


# ============ 数据格式化 ============

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
        "metadata": metadata,
        "categories": metadata.get("categories", []),
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
    """将 Mem0 返回的记忆对象格式化（复用 extract_memory_fields，适配 Mem0 SDK 字段名差异）"""
    # Mem0 SDK 的 memory 字段叫 "memory"，而 Qdrant payload 里叫 "data"
    # 构建兼容 payload，让 extract_memory_fields 能正确提取
    payload = {
        "data": item.get("memory", ""),
        "id": item.get("id", ""),
        "user_id": item.get("user_id", ""),
        "agent_id": item.get("agent_id", ""),
        "run_id": item.get("run_id", ""),
        "hash": item.get("hash", ""),
        "metadata": item.get("metadata", {}),
        "created_at": item.get("created_at", ""),
        "updated_at": item.get("updated_at", ""),
    }
    return extract_memory_fields(payload)


# ============ AI 自动分类 ============

async def auto_categorize_memory(memory_text: str) -> List[str]:
    """使用 LLM 对记忆内容进行自动分类（复用全局异步 HTTP 客户端）"""
    try:
        # 构建分类描述文本
        cat_text = "\n".join(f"- {k}: {v}" for k, v in CATEGORY_DESCRIPTIONS.items())
        prompt = MEMORY_CATEGORIZATION_PROMPT.format(
            categories=cat_text,
            memory_content=memory_text,
        )

        # 调用 Ollama API（异步，复用全局客户端）
        ollama_base_url = MEM0_CONFIG["llm"]["config"]["ollama_base_url"]
        model = MEM0_CONFIG["llm"]["config"]["model"]

        response = await http_client.post(
            f"{ollama_base_url}/api/generate",
            json={
                "model": model,
                "prompt": prompt,
                "stream": False,
                "format": "json",
                "options": {"temperature": 0.1},
            },
            timeout=30,
        )
        response.raise_for_status()
        result_text = response.json().get("response", "")

        # 解析 JSON 结果
        parsed = json.loads(result_text)
        raw_categories = parsed.get("categories", [])

        # 校验：只保留合法的分类
        valid = [c for c in raw_categories if c in VALID_CATEGORIES]
        logger.info(f"AI 自动分类结果: {valid} (原始: {raw_categories})")
        return valid

    except Exception as e:
        logger.warning(f"AI 自动分类失败: {e}")
        return []


async def embed_query_text(text: str) -> List[float]:
    """根据当前 Embedder 配置生成查询向量。"""
    if http_client is None:
        raise RuntimeError("Embedder HTTP 客户端未初始化")

    embedder_config = MEM0_CONFIG.get("embedder", {})
    provider = embedder_config.get("provider", "ollama")
    config = embedder_config.get("config", {})
    model = config.get("model", "")
    base_url = config.get("ollama_base_url", config.get("openai_base_url", ""))

    if not model or not base_url:
        raise RuntimeError("Embedder 配置不完整")

    if provider == "ollama":
        response = await http_client.post(
            f"{base_url}/api/embeddings",
            json={"model": model, "prompt": text},
            timeout=15,
        )
        response.raise_for_status()
        embedding = response.json().get("embedding", [])
    else:
        headers = {"Content-Type": "application/json"}
        api_key = config.get("api_key", "")
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        response = await http_client.post(
            f"{base_url}/embeddings",
            json={"model": model, "input": text},
            headers=headers,
            timeout=15,
        )
        response.raise_for_status()
        data = response.json().get("data", [{}])
        embedding = data[0].get("embedding", []) if data else []

    if not isinstance(embedding, list) or not embedding:
        raise RuntimeError("Embedder 未返回有效向量")

    return embedding


async def semantic_search_memories(
    query: str,
    limit: int = 10,
    user_id: str | None = None,
    agent_id: str | None = None,
    run_id: str | None = None,
    exclude_ids: list[str] | None = None,
) -> List[Dict[str, Any]]:
    """直接基于 Qdrant 做语义搜索，作为 Mem0 SDK 全局搜索的回退路径。"""
    query_vector = await embed_query_text(query)
    collection_name, qdrant_client = _get_qdrant_collection_and_client()

    must = []
    if user_id:
        must.append(FieldCondition(key="user_id", match=MatchValue(value=user_id)))
    if agent_id:
        must.append(FieldCondition(key="agent_id", match=MatchValue(value=agent_id)))
    if run_id:
        must.append(FieldCondition(key="run_id", match=MatchValue(value=run_id)))
    query_filter = Filter(must=must) if must else None

    fetch_limit = min(max(limit * 3, limit + len(exclude_ids or []) + 10), 100)
    query_result = await asyncio.to_thread(
        qdrant_client.query_points,
        collection_name=collection_name,
        query=query_vector,
        query_filter=query_filter,
        limit=fetch_limit,
        with_payload=True,
        with_vectors=False,
    )

    excluded = {str(item) for item in (exclude_ids or []) if item}
    results: List[Dict[str, Any]] = []
    for point in getattr(query_result, "points", []) or []:
        formatted = format_record(point)
        point_id = formatted.get("id") or str(point.id)
        if point_id in excluded:
            continue

        formatted["score"] = point.score
        results.append(formatted)
        if len(results) >= limit:
            break

    return results


# ============ Qdrant 查询与聚合 ============


_DEFAULT_SCROLL_BATCH_SIZE = 128
_MAX_PAGE_SIZE = 200


def _get_qdrant_collection_and_client():
    """获取当前 Mem0 绑定的 Qdrant collection 和 client。"""
    m = get_memory()
    collection_name = MEM0_CONFIG["vector_store"]["config"]["collection_name"]
    return collection_name, m.vector_store.client


def _parse_dt_for_filter(value: str, end_of_day: bool = False):
    """将日期/时间字符串解析为带 UTC 时区的 datetime，用于 Qdrant 时间过滤。"""
    value = (value or "").strip()
    if not value:
        return None

    if len(value) == 10 and value[4] == "-" and value[7] == "-":
        suffix = "T23:59:59+00:00" if end_of_day else "T00:00:00+00:00"
        return datetime.fromisoformat(value + suffix)

    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def build_memory_filter(
    user_id: str | None = None,
    categories: list[str] | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
):
    """构建 Qdrant 过滤条件，将可下推的筛选尽量下推到存储层。"""
    must = []

    if user_id:
        must.append(FieldCondition(key="user_id", match=MatchValue(value=user_id)))

    valid_categories = [c for c in (categories or []) if c in VALID_CATEGORIES]
    if valid_categories:
        must.append(FieldCondition(key="metadata.categories", match=MatchAny(any=valid_categories)))

    dt_from = _parse_dt_for_filter(date_from, end_of_day=False) if date_from else None
    dt_to = _parse_dt_for_filter(date_to, end_of_day=True) if date_to else None
    if dt_from or dt_to:
        must.append(
            FieldCondition(
                key="created_at",
                range=DatetimeRange(gte=dt_from, lte=dt_to),
            )
        )

    if not must:
        return None
    return Filter(must=must)


def _client_side_matches(memory: dict, search: str | None = None) -> bool:
    """补充无法完全下推到 Qdrant 的客户端文本搜索。"""
    if not search:
        return True

    keyword = search.strip().lower()
    if not keyword:
        return True

    return (
        keyword in (memory.get("memory", "") or "").lower()
        or keyword in (memory.get("user_id", "") or "").lower()
        or keyword in (memory.get("id", "") or "").lower()
    )


def iter_memories_raw(
    user_id: str | None = None,
    categories: list[str] | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    search: str | None = None,
    order_by: str = "created_at",
    order_direction: str = "desc",
    batch_size: int = _DEFAULT_SCROLL_BATCH_SIZE,
) -> Iterator[dict]:
    """按批滚动遍历记忆数据，优先使用 Qdrant 端过滤，减少全量拉取后的本地筛选。
    如果 order_by 不被支持（如本地文件模式未建 payload index），自动回退到无排序模式。"""
    try:
        collection_name, qdrant_client = _get_qdrant_collection_and_client()
        scroll_filter = build_memory_filter(
            user_id=user_id,
            categories=categories,
            date_from=date_from,
            date_to=date_to,
        )
        offset = None
        order_key = order_by if order_by in {"created_at", "updated_at"} else "created_at"
        direction = Direction.ASC if str(order_direction).lower() == "asc" else Direction.DESC

        # 先尝试带 order_by 的查询；如果 Qdrant 不支持（本地模式无 payload index），回退到无排序
        use_order_by = True
        try:
            test_records, _ = qdrant_client.scroll(
                collection_name=collection_name,
                scroll_filter=scroll_filter,
                limit=1,
                order_by=OrderBy(key=order_key, direction=direction),
                with_payload=True,
                with_vectors=False,
            )
            # 如果查询成功但返回空，可能是真的没数据，也可能是 order_by 不兼容
            # 再用无排序查一次确认
            if not test_records:
                fallback_records, _ = qdrant_client.scroll(
                    collection_name=collection_name,
                    scroll_filter=scroll_filter,
                    limit=1,
                    with_payload=True,
                    with_vectors=False,
                )
                if fallback_records:
                    # 有数据但 order_by 返回空 → order_by 不兼容
                    use_order_by = False
                    logger.info("Qdrant order_by 返回空但无排序有数据，回退到无排序模式")
                else:
                    # 真的没数据
                    return
        except Exception as order_err:
            logger.info(f"Qdrant order_by 不支持，回退到无排序模式: {order_err}")
            use_order_by = False

        while True:
            scroll_kwargs = {
                "collection_name": collection_name,
                "scroll_filter": scroll_filter,
                "limit": max(1, min(batch_size, _MAX_PAGE_SIZE)),
                "offset": offset,
                "with_payload": True,
                "with_vectors": False,
            }
            if use_order_by:
                scroll_kwargs["order_by"] = OrderBy(key=order_key, direction=direction)

            records, next_offset = qdrant_client.scroll(**scroll_kwargs)
            if not records:
                break

            for record in records:
                formatted = format_record(record)
                if _client_side_matches(formatted, search=search):
                    yield formatted

            if next_offset is None:
                break
            offset = next_offset
    except Exception as e:
        logger.warning(f"Qdrant 直接查询失败: {e}")
        return


def get_all_memory_ids(
    user_id: str | None = None,
    categories: list[str] | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    search: str | None = None,
) -> list[str]:
    """获取当前筛选条件下的所有记忆 ID（用于前端全选功能），优先走关系库。"""
    from server.services.meta_service import query_all_memory_ids as _db_query
    try:
        return _db_query(
            user_id=user_id,
            categories=categories if isinstance(categories, list) else None,
            date_from=date_from, date_to=date_to, search=search,
        )
    except Exception as e:
        logger.warning(f"关系库查询所有 ID 失败: {e}")
        return []


def get_all_memories_raw(
    user_id: str | None = None,
    categories: list[str] | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    search: str | None = None,
    order_by: str = "created_at",
    order_direction: str = "desc",
) -> list:
    """获取记忆列表，优先使用 Qdrant 端过滤和排序，减少全量扫描后的本地处理。"""
    return list(
        iter_memories_raw(
            user_id=user_id,
            categories=categories,
            date_from=date_from,
            date_to=date_to,
            search=search,
            order_by=order_by,
            order_direction=order_direction,
        )
    )


def get_memories_page(
    user_id: str | None = None,
    categories: list[str] | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    search: str | None = None,
    page: int = 1,
    page_size: int = 20,
    order_by: str = "created_at",
    order_direction: str = "desc",
) -> dict:
    """获取分页记忆列表 — 优先从关系库查询，回退到 Qdrant 直接查询。"""
    from server.services.meta_service import query_memories_page as _db_query
    try:
        return _db_query(
            user_id=user_id,
            categories=categories if isinstance(categories, list) else None,
            date_from=date_from, date_to=date_to, search=search,
            page=page, page_size=page_size,
            sort_by=order_by, sort_order=order_direction,
        )
    except Exception as e:
        logger.warning(f"关系库分页查询失败，回退到 Qdrant: {e}")
        return _qdrant_get_memories_page(
            user_id=user_id, categories=categories,
            date_from=date_from, date_to=date_to, search=search,
            page=page, page_size=page_size,
            order_by=order_by, order_direction=order_direction,
        )


def _qdrant_get_memories_page(
    user_id=None, categories=None,
    date_from=None, date_to=None, search=None,
    page=1, page_size=20, order_by="created_at",
    order_direction="desc",
) -> dict:
    """Qdrant 直接分页查询（回退方案，数据迁移前使用）"""
    safe_page = max(1, int(page or 1))
    safe_page_size = max(1, min(int(page_size or 20), _MAX_PAGE_SIZE))
    start = (safe_page - 1) * safe_page_size
    end = start + safe_page_size

    total: int | None = None
    if not search:
        try:
            collection_name, qdrant_client = _get_qdrant_collection_and_client()
            count_result = qdrant_client.count(
                collection_name=collection_name,
                count_filter=build_memory_filter(
                    user_id=user_id, categories=categories,
                    date_from=date_from, date_to=date_to,
                ),
                exact=True,
            )
            total = int(getattr(count_result, "count", 0))
        except Exception as e:
            logger.warning(f"Qdrant count 查询失败: {e}")
            total = None

    scanned = 0
    items = []
    for memory in iter_memories_raw(
        user_id=user_id, categories=categories,
        date_from=date_from, date_to=date_to, search=search,
        order_by=order_by, order_direction=order_direction,
    ):
        if start <= scanned < end:
            items.append(memory)
        scanned += 1
        if total is not None and not search and scanned >= end:
            break

    # L3: 存在 search 关键词时 total 只是 scanned 估算值（未真正走到数据末尾无法得知精确数），
    # 通过 total_is_estimate 告知前端，前端可以显示"已加载 N 条"而非"共 N 页"
    total_is_estimate = False
    if total is None:
        total = scanned
        total_is_estimate = True

    total_pages = (total + safe_page_size - 1) // safe_page_size if total > 0 else 1
    return {
        "items": items, "total": total, "page": safe_page,
        "page_size": safe_page_size, "total_pages": total_pages,
        "total_is_estimate": total_is_estimate,
    }


def get_memory_summary(limit_recent: int = 5, limit_top_users: int = 10) -> dict:
    """获取首页摘要数据 — 优先从关系库查询，带缓存。"""
    safe_recent_limit = max(1, min(int(limit_recent or 5), 20))
    safe_top_users_limit = max(1, min(int(limit_top_users or 10), 50))

    cache = get_summary_cache()
    now_ts = time.time()
    if cache["data"] is not None and now_ts < cache["expire"]:
        data = cache["data"]
        return {
            "recent_memories": data.get("recent_memories", [])[:safe_recent_limit],
            "top_users": data.get("top_users", [])[:safe_top_users_limit],
        }

    from server.services.meta_service import get_summary_from_db
    try:
        # 缓存最大范围的数据，按需切片返回
        payload = get_summary_from_db(limit_recent=20, limit_top_users=50)
        set_summary_cache(payload)
        return {
            "recent_memories": payload.get("recent_memories", [])[:safe_recent_limit],
            "top_users": payload.get("top_users", [])[:safe_top_users_limit],
        }
    except Exception as e:
        logger.warning(f"关系库摘要查询失败: {e}")
        return {"recent_memories": [], "top_users": []}


def get_users_summary() -> list[dict]:
    """按用户聚合记忆摘要 — 优先从关系库查询，带缓存。"""
    cache = get_users_cache()
    now_ts = time.time()
    if cache["data"] is not None and now_ts < cache["expire"]:
        return cache["data"]

    from server.services.meta_service import get_users_summary_from_db
    try:
        result = get_users_summary_from_db()
        set_users_cache(result)
        return result
    except Exception as e:
        logger.warning(f"关系库用户汇总查询失败: {e}")
        return []


def compute_memory_stats() -> dict:
    """统计信息 — 优先从关系库聚合。"""
    from server.services.meta_service import compute_stats_from_db
    try:
        return compute_stats_from_db()
    except Exception as e:
        logger.warning(f"关系库统计查询失败: {e}")
        return {
            "total_memories": 0, "total_users": 0,
            "category_distribution": {},
            "state_distribution": {"active": 0, "paused": 0, "deleted": 0},
            "uncategorized_count": 0,
            "daily_counter": {},
        }



# ============ 统计与摘要缓存 ============

_stats_cache: Dict[str, Any] = {"data": None, "expire": 0.0}
_users_cache: Dict[str, Any] = {"data": None, "expire": 0.0}
_summary_cache: Dict[str, Any] = {"data": None, "expire": 0.0}
_STATS_CACHE_TTL = 30  # 统计数据缓存 30 秒
_USERS_CACHE_TTL = 30  # 用户汇总缓存 30 秒
_SUMMARY_CACHE_TTL = 30  # 首页摘要缓存 30 秒


def invalidate_stats_cache():
    """使统计与摘要缓存失效（在写操作后调用）"""
    for cache in (_stats_cache, _users_cache, _summary_cache):
        cache["data"] = None
        cache["expire"] = 0.0


def get_stats_cache() -> Dict[str, Any]:
    """获取统计缓存"""
    return _stats_cache


def set_stats_cache(data: Any):
    """设置统计缓存"""
    _stats_cache["data"] = data
    _stats_cache["expire"] = time.time() + _STATS_CACHE_TTL


def get_users_cache() -> Dict[str, Any]:
    """获取用户汇总缓存"""
    return _users_cache


def set_users_cache(data: Any):
    """设置用户汇总缓存"""
    _users_cache["data"] = data
    _users_cache["expire"] = time.time() + _USERS_CACHE_TTL


def get_summary_cache() -> Dict[str, Any]:
    """获取首页摘要缓存"""
    return _summary_cache


def set_summary_cache(data: Any):
    """设置首页摘要缓存"""
    _summary_cache["data"] = data
    _summary_cache["expire"] = time.time() + _SUMMARY_CACHE_TTL
