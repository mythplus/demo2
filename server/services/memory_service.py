"""
记忆核心服务 — Mem0 实例管理、数据格式化、多维筛选、AI 自动分类、统计缓存
"""

import json
import time
import logging
from typing import List, Dict, Any
from datetime import datetime

import httpx

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


import threading
from contextlib import contextmanager

# 保护 graph 属性临时摘除/恢复的锁（防止并发导入时互相干扰）
_graph_lock = threading.Lock()


@contextmanager
def disable_graph(m):
    """上下文管理器：临时禁用 Memory 实例的图谱功能。
    批量导入时使用，避免 Neo4j 关系名不合法导致整条记忆导入失败。
    退出上下文后自动恢复。"""
    with _graph_lock:
        original_enable_graph = getattr(m, 'enable_graph', False)
        try:
            m.enable_graph = False
            yield m
        finally:
            m.enable_graph = original_enable_graph


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


# ============ 多维筛选 ============

def apply_filters(memories: list, categories: list = None, state: str = None,
                  date_from: str = None, date_to: str = None, search: str = None) -> list:
    """对记忆列表应用多维筛选"""
    filtered = memories

    # 按状态筛选
    if state:
        filtered = [m for m in filtered if m.get("state", "active") == state]

    # 按分类筛选（包含任一分类即匹配）
    if categories:
        cat_set = set(categories)
        filtered = [m for m in filtered if set(m.get("categories", [])) & cat_set]

    # 按时间范围筛选
    # 辅助函数：将日期字符串统一解析为 offset-aware datetime（UTC）
    def _parse_dt(s: str) -> datetime:
        """解析日期/时间字符串，统一返回带 UTC 时区的 datetime"""
        from datetime import timezone
        s = s.strip()
        # 纯日期格式 YYYY-MM-DD，补充时间部分
        if len(s) == 10 and s[4] == '-' and s[7] == '-':
            return datetime.fromisoformat(s + "T00:00:00+00:00")
        # 带 Z 后缀的 ISO 格式
        dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
        # 如果解析结果无时区信息，默认当作 UTC
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
            # 如果是纯日期（无时间部分），将截止时间设为当天 23:59:59
            if len(date_to.strip()) == 10:
                to_dt = to_dt.replace(hour=23, minute=59, second=59)
            filtered = [m for m in filtered if m.get("created_at") and
                        _parse_dt(str(m["created_at"])) <= to_dt]
        except (ValueError, TypeError):
            pass

    # 文本搜索
    if search:
        keyword = search.lower()
        filtered = [m for m in filtered if
                    keyword in (m.get("memory", "") or "").lower() or
                    keyword in (m.get("user_id", "") or "").lower() or
                    keyword in (m.get("id", "") or "").lower()]

    return filtered


# ============ AI 自动分类 ============

async def auto_categorize_memory(memory_text: str) -> List[str]:
    """使用 LLM 对记忆内容进行自动分类（复用全局异步 HTTP 客户端）。
    根据 LLM provider 类型自动选择调用方式：
    - vllm / openai：使用 OpenAI 兼容 API（/v1/chat/completions）
    - ollama：使用 Ollama 私有 API（/api/generate）
    """
    try:
        # 构建分类描述文本
        cat_text = "\n".join(f"- {k}: {v}" for k, v in CATEGORY_DESCRIPTIONS.items())
        prompt = MEMORY_CATEGORIZATION_PROMPT.format(
            categories=cat_text,
            memory_content=memory_text,
        )

        provider = MEM0_CONFIG["llm"].get("provider", "ollama")
        config = MEM0_CONFIG["llm"]["config"]
        model = config.get("model", "")

        if provider in ("vllm", "openai"):
            # ---- OpenAI 兼容 API（vLLM / OpenAI） ----
            base_url = config.get("vllm_base_url", config.get("openai_base_url", ""))
            headers = {"Content-Type": "application/json"}
            api_key = config.get("api_key", "")
            if api_key:
                headers["Authorization"] = f"Bearer {api_key}"

            response = await http_client.post(
                f"{base_url}/chat/completions",
                json={
                    "model": model,
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.1,
                    "response_format": {"type": "json_object"},
                },
                headers=headers,
                timeout=30,
            )
            response.raise_for_status()
            result_text = response.json()["choices"][0]["message"]["content"]
        else:
            # ---- Ollama 私有 API（保持原有逻辑） ----
            ollama_base_url = config.get("ollama_base_url", "")
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
        logger.info(f"AI 自动分类结果: {valid} (原始: {raw_categories}, provider: {provider})")
        return valid

    except Exception as e:
        logger.warning(f"AI 自动分类失败: {e}")
        return []


# ============ Qdrant 全量查询 ============

def get_all_memories_raw() -> list:
    """获取所有记忆（完整分页滚动，不再限制 200 条）"""
    m = get_memory()
    try:
        collection_name = MEM0_CONFIG["vector_store"]["config"]["collection_name"]
        qdrant_client = m.vector_store.client
        all_records = []
        offset = None
        batch_size = 100

        while True:
            records, next_offset = qdrant_client.scroll(
                collection_name=collection_name,
                limit=batch_size,
                offset=offset,
                with_payload=True,
                with_vectors=False,
            )
            all_records.extend(records)
            if next_offset is None or not records:
                break
            offset = next_offset

        return [format_record(record) for record in all_records]
    except Exception as e:
        logger.warning(f"Qdrant 直接查询失败: {e}")
        return []


# ============ 查询记忆真实状态 ============

def get_real_states(memory_ids: list) -> dict:
    """从 Qdrant 直接查询记忆的真实 state（Mem0 search 返回的 metadata 可能不含自定义 state）"""
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


# ============ 统计缓存 ============

_stats_cache: Dict[str, Any] = {"data": None, "expire": 0.0}
_STATS_CACHE_TTL = 30  # 统计数据缓存 30 秒


def invalidate_stats_cache():
    """使统计缓存失效（在写操作后调用）"""
    _stats_cache["data"] = None
    _stats_cache["expire"] = 0.0


def get_stats_cache() -> Dict[str, Any]:
    """获取统计缓存"""
    return _stats_cache


def set_stats_cache(data: Any):
    """设置统计缓存"""
    _stats_cache["data"] = data
    _stats_cache["expire"] = time.time() + _STATS_CACHE_TTL
