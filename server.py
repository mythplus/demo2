"""
Mem0 Dashboard 后端 API 服务
使用 FastAPI 实现，Qdrant 采用本地文件模式（无需额外部署向量数据库）
"""

import os
import json
import time
import logging
import sqlite3
import yaml
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from pydantic import BaseModel, Field, field_validator
import uvicorn

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ============ 环境模式 ============
# 通过环境变量 MEM0_ENV 控制，production 为生产模式，其他为开发模式
IS_PRODUCTION = os.environ.get("MEM0_ENV", "development").lower() == "production"

# ============ Qdrant 本地文件存储路径 ============
# 使用项目目录下的 qdrant_data 文件夹，基于当前文件位置动态计算
QDRANT_DATA_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "qdrant_data")

def _safe_error_detail(e: Exception) -> str:
    """安全的异常信息：生产环境返回通用提示，开发环境返回详细错误"""
    if IS_PRODUCTION:
        return "服务器内部错误，请稍后重试"
    return str(e)

# ============ 配置文件路径 ============
CONFIG_FILE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.yaml")


import re as _re

def _resolve_env_vars(value):
    """递归替换配置值中的 ${ENV_VAR} 为环境变量实际值"""
    if isinstance(value, str):
        def _replace(match):
            env_name = match.group(1)
            return os.environ.get(env_name, "")
        return _re.sub(r'\$\{(\w+)\}', _replace, value)
    elif isinstance(value, dict):
        return {k: _resolve_env_vars(v) for k, v in value.items()}
    elif isinstance(value, list):
        return [_resolve_env_vars(item) for item in value]
    return value

def load_config_from_yaml() -> dict:
    """从 config.yaml 文件实时读取配置，返回与 MEM0_CONFIG 兼容的字典格式。
    支持 ${ENV_VAR} 语法引用环境变量。"""
    try:
        with open(CONFIG_FILE_PATH, "r", encoding="utf-8") as f:
            yaml_config = yaml.safe_load(f)
        if not yaml_config:
            logger.warning("config.yaml 为空，使用默认配置")
            return {}

        # 递归替换环境变量
        yaml_config = _resolve_env_vars(yaml_config)

        # 构建与 MEM0_CONFIG 兼容的格式
        config = {}

        # LLM 配置
        if "llm" in yaml_config:
            config["llm"] = {
                "provider": yaml_config["llm"].get("provider", "ollama"),
                "config": yaml_config["llm"].get("config", {}),
            }

        # Embedder 配置
        if "embedder" in yaml_config:
            config["embedder"] = {
                "provider": yaml_config["embedder"].get("provider", "ollama"),
                "config": yaml_config["embedder"].get("config", {}),
            }

        # 向量数据库配置（补充 path 和 on_disk，这些不放在 yaml 中）
        if "vector_store" in yaml_config:
            vs_config = yaml_config["vector_store"].get("config", {})
            vs_config["path"] = QDRANT_DATA_PATH
            if "on_disk" not in vs_config:
                vs_config["on_disk"] = True
            config["vector_store"] = {
                "provider": yaml_config["vector_store"].get("provider", "qdrant"),
                "config": vs_config,
            }

        # 图数据库配置
        if "graph_store" in yaml_config:
            config["graph_store"] = {
                "provider": yaml_config["graph_store"].get("provider", "neo4j"),
                "config": yaml_config["graph_store"].get("config", {}),
            }

        # 版本号
        if "version" in yaml_config:
            config["version"] = yaml_config["version"]

        # 安全配置
        if "security" in yaml_config:
            config["security"] = yaml_config["security"]

        return config
    except FileNotFoundError:
        logger.warning(f"配置文件 {CONFIG_FILE_PATH} 不存在，使用内置默认配置")
        return {}
    except Exception as e:
        logger.error(f"读取配置文件失败: {e}，使用内置默认配置")
        return {}


# ============ Mem0 配置（从 config.yaml 加载，启动时初始化一次） ============
_yaml_config = load_config_from_yaml()
MEM0_CONFIG = _yaml_config if _yaml_config else {
    "vector_store": {
        "provider": "qdrant",
        "config": {
            "collection_name": "mem0",
            "embedding_model_dims": 768,
            "path": QDRANT_DATA_PATH,
            "on_disk": True,
        },
    },
    "llm": {
        "provider": "ollama",
        "config": {
            "model": "qwen2.5:7b",
            "ollama_base_url": "http://9.134.231.238:11434",
            "temperature": 0.1,
        },
    },
    "embedder": {
        "provider": "ollama",
        "config": {
            "model": "nomic-embed-text",
            "ollama_base_url": "http://9.134.231.238:11434",
        },
    },
    "graph_store": {
        "provider": "neo4j",
        "config": {
            "url": "bolt://9.134.231.238:7687",
            "username": "neo4j",
            "password": "mem0_neo4j_2024",
        },
    },
    "version": "v1.1",
}
logger.info(f"配置加载完成，LLM: {MEM0_CONFIG.get('llm', {}).get('config', {}).get('model', 'unknown')}")

# ============ 分类和状态常量 ============
VALID_CATEGORIES = {
    "personal", "relationships", "preferences", "health", "travel",
    "work", "education", "projects", "ai_ml_technology", "technical_support",
    "finance", "shopping", "legal", "entertainment", "messages",
    "customer_support", "product_feedback", "news", "organization", "goals",
}
VALID_STATES = {"active", "paused", "deleted"}

# ============ AI 自动分类 Prompt ============
CATEGORY_DESCRIPTIONS = {
    "personal": "个人 — 家庭、朋友、家居、爱好、生活方式",
    "relationships": "关系 — 社交网络、伴侣、同事、朋友关系",
    "preferences": "偏好 — 喜好、厌恶、习惯、喜欢的媒体",
    "health": "健康 — 体能、心理健康、饮食、睡眠",
    "travel": "旅行 — 旅行计划、通勤、喜欢的地方、行程",
    "work": "工作 — 职位、公司、项目、晋升",
    "education": "教育 — 课程、学位、证书、技能发展",
    "projects": "项目 — 待办事项、里程碑、截止日期、状态更新",
    "ai_ml_technology": "AI/ML与技术 — 基础设施、算法、工具、研究",
    "technical_support": "技术支持 — Bug报告、错误日志、修复",
    "finance": "财务 — 收入、支出、投资、账单",
    "shopping": "购物 — 购买、愿望清单、退货、配送",
    "legal": "法律 — 合同、政策、法规、隐私",
    "entertainment": "娱乐 — 电影、音乐、游戏、书籍、活动",
    "messages": "消息 — 邮件、短信、提醒、通知",
    "customer_support": "客户支持 — 工单、咨询、解决方案",
    "product_feedback": "产品反馈 — 评分、Bug报告、功能请求",
    "news": "新闻 — 文章、头条、热门话题",
    "organization": "组织 — 会议、预约、日历",
    "goals": "目标 — 目标、KPI、长期规划",
}

MEMORY_CATEGORIZATION_PROMPT = """你是一个记忆分类助手。请根据以下记忆内容，从给定的分类列表中选择最合适的分类标签。
一条记忆可以属于多个分类，但请只选择真正相关的分类，不要过度标注。

可用的分类列表：
{categories}

请严格按照以下 JSON 格式返回结果，不要输出任何其他内容：
{{"categories": ["分类1", "分类2"]}}

如果没有任何分类匹配，返回空数组：
{{"categories": []}}

记忆内容：
{memory_content}"""


def _auto_categorize_memory(memory_text: str) -> List[str]:
    """使用 LLM 对记忆内容进行自动分类"""
    try:
        import requests

        # 构建分类描述文本
        cat_text = "\n".join(f"- {k}: {v}" for k, v in CATEGORY_DESCRIPTIONS.items())
        prompt = MEMORY_CATEGORIZATION_PROMPT.format(
            categories=cat_text,
            memory_content=memory_text,
        )

        # 调用 Ollama API
        ollama_base_url = MEM0_CONFIG["llm"]["config"]["ollama_base_url"]
        model = MEM0_CONFIG["llm"]["config"]["model"]

        response = requests.post(
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

# ============ 访问日志 SQLite 存储 ============
ACCESS_LOG_DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "access_logs.db")


def _get_db_conn():
    """获取 SQLite 连接（统一工厂函数，自动设置 busy_timeout 避免并发锁定）"""
    conn = sqlite3.connect(ACCESS_LOG_DB_PATH)
    conn.execute("PRAGMA busy_timeout=5000")
    return conn


def _init_access_log_db():
    """初始化访问日志和请求日志数据库"""
    conn = _get_db_conn()
    # 启用 WAL 模式（持久化设置，只需初始化时执行一次）
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS access_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            memory_id TEXT NOT NULL,
            action TEXT NOT NULL,
            memory_preview TEXT,
            timestamp TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_access_logs_memory_id ON access_logs(memory_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_access_logs_timestamp ON access_logs(timestamp)")
    # 请求日志表
    conn.execute("""
        CREATE TABLE IF NOT EXISTS request_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            method TEXT NOT NULL,
            path TEXT NOT NULL,
            request_type TEXT,
            user_id TEXT,
            status_code INTEGER,
            latency_ms REAL,
            payload_summary TEXT,
            error TEXT
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_request_logs_timestamp ON request_logs(timestamp)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_request_logs_type ON request_logs(request_type)")
    # 自建修改历史表（Mem0 原生 history 时间不准，自己记录完整操作历史）
    conn.execute("""
        CREATE TABLE IF NOT EXISTS memory_change_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            memory_id TEXT NOT NULL,
            event TEXT NOT NULL,
            old_memory TEXT,
            new_memory TEXT,
            categories TEXT NOT NULL DEFAULT '[]',
            old_categories TEXT NOT NULL DEFAULT '[]',
            timestamp TEXT NOT NULL
        )
    """)
    # 兼容旧表：如果 old_categories 列不存在则添加
    try:
        conn.execute("ALTER TABLE memory_change_logs ADD COLUMN old_categories TEXT NOT NULL DEFAULT '[]'")
    except Exception:
        pass  # 列已存在，忽略
    conn.execute("CREATE INDEX IF NOT EXISTS idx_mcl_memory_id ON memory_change_logs(memory_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_mcl_timestamp ON memory_change_logs(timestamp)")
    # 保留旧表兼容（不删除）
    conn.execute("""
        CREATE TABLE IF NOT EXISTS category_snapshots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            memory_id TEXT NOT NULL,
            categories TEXT NOT NULL DEFAULT '[]',
            timestamp TEXT NOT NULL
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_cat_snap_memory_id ON category_snapshots(memory_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_cat_snap_timestamp ON category_snapshots(timestamp)")
    conn.commit()
    conn.close()


def _save_category_snapshot(memory_id: str, categories: list, timestamp: str = ""):
    """记录一次标签快照"""
    try:
        ts = timestamp or datetime.now().isoformat()
        cats_json = json.dumps(categories, ensure_ascii=False)
        conn = _get_db_conn()
        conn.execute(
            "INSERT INTO category_snapshots (memory_id, categories, timestamp) VALUES (?, ?, ?)",
            (memory_id, cats_json, ts),
        )
        conn.commit()
        conn.close()
    except Exception as e:
        logger.warning(f"记录标签快照失败: {e}")


def _save_change_log(memory_id: str, event: str, new_memory: str,
                     categories: list, old_memory: str = None,
                     old_categories: list = None):
    """记录一条修改历史（自建，带真实时间和标签快照）"""
    try:
        ts = datetime.now().isoformat()
        cats_json = json.dumps(categories, ensure_ascii=False)
        old_cats_json = json.dumps(old_categories or [], ensure_ascii=False)
        conn = _get_db_conn()
        conn.execute(
            """INSERT INTO memory_change_logs
               (memory_id, event, old_memory, new_memory, categories, old_categories, timestamp)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (memory_id, event, old_memory or "", new_memory, cats_json, old_cats_json, ts),
        )
        conn.commit()
        conn.close()
    except Exception as e:
        logger.warning(f"记录修改历史失败: {e}")


def _get_change_logs(memory_id: str) -> list:
    """获取某条记忆的自建修改历史（时间正序）"""
    try:
        conn = _get_db_conn()
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            """SELECT event, old_memory, new_memory, categories, old_categories, timestamp
               FROM memory_change_logs WHERE memory_id = ? ORDER BY timestamp ASC""",
            (memory_id,),
        ).fetchall()
        conn.close()
        result = []
        for row in rows:
            try:
                cats = json.loads(row["categories"])
            except (json.JSONDecodeError, TypeError):
                cats = []
            try:
                old_cats = json.loads(row["old_categories"])
            except (json.JSONDecodeError, TypeError, KeyError):
                old_cats = []
            result.append({
                "id": f"cl-{memory_id[:8]}-{len(result)}",
                "memory_id": memory_id,
                "event": row["event"],
                "old_memory": row["old_memory"] or None,
                "new_memory": row["new_memory"],
                "categories": cats,
                "old_categories": old_cats,
                "created_at": row["timestamp"],
            })
        return result
    except Exception as e:
        logger.warning(f"查询修改历史失败: {e}")
        return []


def _log_access(memory_id: str, action: str, memory_preview: str = ""):
    """记录一条访问日志"""
    try:
        conn = _get_db_conn()
        conn.execute(
            "INSERT INTO access_logs (memory_id, action, memory_preview, timestamp) VALUES (?, ?, ?, ?)",
            (memory_id, action, memory_preview[:100] if memory_preview else "", datetime.now().isoformat()),
        )
        conn.commit()
        conn.close()
    except Exception as e:
        logger.warning(f"记录访问日志失败: {e}")


def _get_access_logs(memory_id: str = None, limit: int = 50, offset: int = 0) -> list:
    """查询访问日志"""
    try:
        conn = _get_db_conn()
        conn.row_factory = sqlite3.Row
        if memory_id:
            rows = conn.execute(
                "SELECT * FROM access_logs WHERE memory_id = ? ORDER BY timestamp DESC LIMIT ? OFFSET ?",
                (memory_id, limit, offset),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM access_logs ORDER BY timestamp DESC LIMIT ? OFFSET ?",
                (limit, offset),
            ).fetchall()
        conn.close()
        return [dict(row) for row in rows]
    except Exception as e:
        logger.warning(f"查询访问日志失败: {e}")
        return []


# ============ 请求日志工具函数 ============

# 路径 → 请求类型映射
_PATH_TYPE_MAP = {
    ("POST", "/v1/memories/"): "添加",
    ("POST", "/v1/memories/search/"): "搜索",
    ("DELETE",): "删除",
    ("PUT",): "更新",
    ("GET", "/v1/memories/"): "获取全部",
    ("GET", "/v1/stats/"): "统计",
}


def _classify_request(method: str, path: str) -> str:
    """根据 HTTP 方法和路径推断请求类型（只分类前端写操作）"""
    if method == "POST" and "/search" in path:
        return "搜索"
    if method == "POST" and "/memories" in path:
        return "添加"
    if method == "PUT":
        return "更新"
    if method == "DELETE":
        return "删除"
    # 其余请求不应被记录，兜底返回方法名
    return method


def _extract_user_from_request(method: str, path: str, body: str) -> str:
    """尝试从请求中提取 user_id"""
    # 从 query params
    if "user_id=" in path:
        for part in path.split("?")[1].split("&") if "?" in path else []:
            if part.startswith("user_id="):
                return part.split("=", 1)[1]
    # 从 body
    if body:
        try:
            data = json.loads(body)
            if isinstance(data, dict) and "user_id" in data:
                return data["user_id"] or ""
        except (json.JSONDecodeError, TypeError):
            pass
    return ""


def _summarize_payload(method: str, path: str, body: str) -> str:
    """生成请求载荷摘要"""
    if not body:
        # GET 请求从 query params 提取
        if "?" in path:
            return path.split("?", 1)[1][:200]
        return ""
    try:
        data = json.loads(body)
        if isinstance(data, dict):
            # 过滤掉过长的字段
            summary = {}
            for k, v in data.items():
                if k == "messages":
                    summary[k] = f"[{len(v)} msg]" if isinstance(v, list) else str(v)[:50]
                elif isinstance(v, str) and len(v) > 80:
                    summary[k] = v[:80] + "..."
                else:
                    summary[k] = v
            return json.dumps(summary, ensure_ascii=False)[:300]
    except (json.JSONDecodeError, TypeError):
        pass
    return body[:200]


def _log_request(timestamp: str, method: str, path: str, request_type: str,
                 user_id: str, status_code: int, latency_ms: float,
                 payload_summary: str, error: str = ""):
    """记录一条请求日志"""
    try:
        conn = _get_db_conn()
        conn.execute(
            """INSERT INTO request_logs
               (timestamp, method, path, request_type, user_id, status_code, latency_ms, payload_summary, error)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (timestamp, method, path, request_type, user_id, status_code,
             round(latency_ms, 2), payload_summary[:500], error[:500]),
        )
        conn.commit()
        conn.close()
    except Exception as e:
        logger.warning(f"记录请求日志失败: {e}")


def _get_request_logs(request_type: str = None, since: str = None, until: str = None, limit: int = 50, offset: int = 0) -> tuple:
    """查询请求日志，返回 (logs, total)"""
    try:
        conn = _get_db_conn()
        conn.row_factory = sqlite3.Row

        where = "WHERE 1=1"
        params: list = []
        if request_type:
            where += " AND request_type = ?"
            params.append(request_type)
        if since:
            where += " AND timestamp >= ?"
            params.append(since)
        if until:
            where += " AND timestamp <= ?"
            params.append(until)

        # 总数
        total = conn.execute(f"SELECT COUNT(*) FROM request_logs {where}", params).fetchone()[0]

        # 分页数据
        rows = conn.execute(
            f"SELECT * FROM request_logs {where} ORDER BY timestamp DESC LIMIT ? OFFSET ?",
            params + [limit, offset],
        ).fetchall()
        conn.close()
        return [dict(row) for row in rows], total
    except Exception as e:
        logger.warning(f"查询请求日志失败: {e}")
        return [], 0


# ============ 全局 Memory 实例 ============
memory_instance = None


def get_memory():
    """获取 Mem0 Memory 实例（延迟初始化）"""
    global memory_instance
    if memory_instance is None:
        from mem0 import Memory
        logger.info(f"正在初始化 Mem0，Qdrant 数据目录: {QDRANT_DATA_PATH}")
        memory_instance = Memory.from_config(MEM0_CONFIG)
        logger.info("Mem0 初始化完成")
    return memory_instance


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
    """将 Mem0 返回的记忆对象格式化，提取 categories 和 state"""
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


# ============ 请求/响应模型 ============

class MemoryMessage(BaseModel):
    role: str = Field(..., max_length=20)  # "user" | "assistant" | "system"
    content: str = Field(..., max_length=10000)  # 单条消息最大 10000 字符


class AddMemoryRequest(BaseModel):
    messages: List[MemoryMessage] = Field(..., max_length=50)  # 单次最多 50 条消息
    user_id: Optional[str] = Field(None, max_length=100)
    agent_id: Optional[str] = Field(None, max_length=100)
    run_id: Optional[str] = Field(None, max_length=100)
    metadata: Optional[Dict[str, Any]] = None
    categories: Optional[List[str]] = None
    state: Optional[str] = "active"
    infer: Optional[bool] = True  # True: AI 自动提取关键记忆（可能拆分为多条）; False: 原文整条存储
    auto_categorize: Optional[bool] = True  # True: 未手动选择标签时由 AI 自动分类


class SearchMemoryRequest(BaseModel):
    query: str = Field(..., max_length=500)  # 搜索查询最大 500 字符
    user_id: Optional[str] = Field(None, max_length=100)
    agent_id: Optional[str] = Field(None, max_length=100)
    run_id: Optional[str] = Field(None, max_length=100)
    limit: Optional[int] = Field(10, ge=1, le=100)  # 返回数量限制 1-100


class UpdateMemoryRequest(BaseModel):
    text: Optional[str] = Field(None, max_length=10000)  # 更新内容最大 10000 字符
    metadata: Optional[Dict[str, Any]] = None
    categories: Optional[List[str]] = Field(None, max_length=20)  # 最多 20 个分类
    state: Optional[str] = Field(None, max_length=20)
    auto_categorize: Optional[bool] = False  # True: 对当前内容重新 AI 自动分类


# ============ 应用生命周期 ============

@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用启动时初始化 Mem0"""
    logger.info("=" * 50)
    logger.info("Mem0 Dashboard 后端服务启动中...")
    logger.info(f"Qdrant 存储模式: 本地文件模式 (on_disk)")
    logger.info(f"Qdrant 数据目录: {QDRANT_DATA_PATH}")
    logger.info("=" * 50)
    # 预初始化 Memory 实例
    get_memory()
    # 初始化访问日志数据库
    _init_access_log_db()
    logger.info(f"访问日志数据库: {ACCESS_LOG_DB_PATH}")
    yield
    # 关闭全局 Neo4j 驱动
    _close_neo4j_driver()
    logger.info("Mem0 Dashboard 后端服务已关闭")


# ============ FastAPI 应用 ============

app = FastAPI(
    title="Mem0 Dashboard API",
    description="Mem0 记忆管理后端服务（Qdrant 本地文件模式）",
    version="1.1.0",
    lifespan=lifespan,
)

# CORS 配置（从 config.yaml 读取允许的来源）
_cors_origins_str = MEM0_CONFIG.get("security", {}).get("cors_origins", "*")
_cors_origins = [o.strip() for o in _cors_origins_str.split(",") if o.strip()] if _cors_origins_str != "*" else ["*"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True if _cors_origins != ["*"] else False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ============ API Key 认证中间件 ============
_configured_api_key = MEM0_CONFIG.get("security", {}).get("api_key", "")

class ApiKeyAuthMiddleware(BaseHTTPMiddleware):
    """API Key 认证中间件：如果配置了 api_key，则所有非健康检查请求都需要携带有效的 API Key"""

    # 免认证的路径（健康检查、OPTIONS 预检请求）
    SKIP_PATHS = {"/", "/docs", "/redoc", "/openapi.json"}

    async def dispatch(self, request: Request, call_next):
        # 如果未配置 API Key，跳过认证
        if not _configured_api_key:
            return await call_next(request)

        # OPTIONS 预检请求和免认证路径跳过
        if request.method == "OPTIONS" or request.url.path in self.SKIP_PATHS:
            return await call_next(request)

        # 从请求头中获取 API Key
        auth_header = request.headers.get("Authorization", "")
        api_key_header = request.headers.get("X-API-Key", "")

        # 支持两种方式：Bearer token 或 X-API-Key 头
        provided_key = ""
        if auth_header.startswith("Bearer "):
            provided_key = auth_header[7:].strip()
        elif api_key_header:
            provided_key = api_key_header.strip()

        if provided_key != _configured_api_key:
            from starlette.responses import JSONResponse
            return JSONResponse(
                status_code=401,
                content={"detail": "无效的 API Key，请在请求头中提供有效的 Authorization: Bearer <key> 或 X-API-Key: <key>"},
            )

        return await call_next(request)

if _configured_api_key:
    app.add_middleware(ApiKeyAuthMiddleware)
    logger.info("API Key 认证已启用")
else:
    logger.warning("⚠️ 未配置 API Key，所有接口无需认证即可访问（建议生产环境设置 security.api_key）")


# ============ 速率限制中间件 ============
# 从配置读取速率限制参数（默认：每分钟 60 次请求，0 表示不启用）
_rate_limit_rpm = int(MEM0_CONFIG.get("security", {}).get("rate_limit", 60))
_rate_limit_enabled = _rate_limit_rpm > 0

class RateLimitMiddleware(BaseHTTPMiddleware):
    """基于 IP 的滑动窗口速率限制中间件"""

    def __init__(self, app, rpm: int = 60):
        super().__init__(app)
        self.rpm = rpm  # 每分钟最大请求数
        self.window = 60  # 窗口大小（秒）
        self._requests: Dict[str, list] = {}  # IP -> [timestamp, ...]
        self._cleanup_counter = 0

    def _get_client_ip(self, request: Request) -> str:
        """获取客户端真实 IP"""
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            return forwarded.split(",")[0].strip()
        return request.client.host if request.client else "unknown"

    def _cleanup_expired(self):
        """定期清理过期记录，防止内存泄漏"""
        self._cleanup_counter += 1
        if self._cleanup_counter % 100 == 0:  # 每 100 次请求清理一次
            now = time.time()
            expired_ips = [ip for ip, ts_list in self._requests.items()
                          if not ts_list or ts_list[-1] < now - self.window]
            for ip in expired_ips:
                del self._requests[ip]

    async def dispatch(self, request: Request, call_next):
        # OPTIONS 预检请求和健康检查跳过限制
        if request.method == "OPTIONS" or request.url.path == "/":
            return await call_next(request)

        client_ip = self._get_client_ip(request)
        now = time.time()
        window_start = now - self.window

        # 获取该 IP 的请求记录，清除窗口外的旧记录
        if client_ip not in self._requests:
            self._requests[client_ip] = []
        self._requests[client_ip] = [t for t in self._requests[client_ip] if t > window_start]

        # 检查是否超过限制
        if len(self._requests[client_ip]) >= self.rpm:
            from starlette.responses import JSONResponse
            retry_after = int(self._requests[client_ip][0] - window_start) + 1
            return JSONResponse(
                status_code=429,
                content={"detail": f"请求过于频繁，每分钟最多 {self.rpm} 次请求，请稍后重试"},
                headers={"Retry-After": str(retry_after)},
            )

        # 记录本次请求
        self._requests[client_ip].append(now)
        self._cleanup_expired()

        return await call_next(request)

if _rate_limit_enabled:
    app.add_middleware(RateLimitMiddleware, rpm=_rate_limit_rpm)
    logger.info(f"速率限制已启用：每分钟最多 {_rate_limit_rpm} 次请求")
else:
    logger.info("速率限制未启用（rate_limit 为 0）")


# ============ 请求日志中间件 ============

class RequestLogMiddleware(BaseHTTPMiddleware):
    """自动记录前端→后端的业务 API 请求（添加/搜索/删除/更新），不记录 GET/OPTIONS 等"""

    # 不记录的路径前缀（日志查询接口本身、静态资源等）
    # 注意：不能包含 "/"，否则所有路径都会被 startswith("/") 匹配而跳过
    SKIP_PATHS = {"/v1/request-logs", "/v1/access-logs", "/favicon.ico", "/_next"}

    # 精确匹配跳过的路径（如健康检查）
    SKIP_EXACT = {"/"}

    # 只记录这些 HTTP 方法（前端发出的写操作）
    RECORD_METHODS = {"POST", "PUT", "DELETE"}

    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        method = request.method

        # 只记录前端发出的写操作（POST/PUT/DELETE），跳过所有 GET/OPTIONS/HEAD
        # 同时跳过日志查询等非业务路径
        should_record = (
            method in self.RECORD_METHODS
            and path not in self.SKIP_EXACT
            and not any(path.startswith(p) for p in self.SKIP_PATHS)
        )

        if not should_record:
            return await call_next(request)

        start_time = time.time()

        # 读取请求体
        body = ""
        try:
            body_bytes = await request.body()
            body = body_bytes.decode("utf-8", errors="ignore")
        except Exception:
            body = ""

        # 执行请求
        error_msg = ""
        status_code = 500
        try:
            response = await call_next(request)
            status_code = response.status_code
        except Exception as exc:
            error_msg = str(exc)[:500]
            raise
        finally:
            latency_ms = (time.time() - start_time) * 1000
            request_type = _classify_request(method, path)
            user_id = _extract_user_from_request(method, path, body)
            payload_summary = _summarize_payload(method, path, body)
            ts = datetime.now().isoformat()

            _log_request(ts, method, path, request_type, user_id,
                         status_code, latency_ms, payload_summary, error_msg)

        return response


app.add_middleware(RequestLogMiddleware)


# ============ 健康检查 ============

@app.get("/")
async def health_check():
    """健康检查端点"""
    return {"status": "ok", "message": "Mem0 Dashboard API 运行中"}


# ============ 系统配置信息 & 连接测试 ============

def _mask_url(url: str) -> str:
    """对 URL 中的 IP 地址进行脱敏处理，保留协议和端口，隐藏 IP 中间段
    例如: http://9.134.231.238:11434 -> http://101.***.***. 32:11434
          bolt://9.134.231.238:7687 -> bolt://101.***.***. 32:7687
    """
    if not url:
        return url
    import re
    # 匹配 IP 地址（IPv4）
    def _mask_ip(match):
        ip = match.group(0)
        parts = ip.split(".")
        if len(parts) == 4:
            return f"{parts[0]}.***.***.{parts[3]}"
        return ip
    return re.sub(r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}', _mask_ip, url)

@app.get("/v1/config/info")
async def get_config_info():
    """获取当前系统配置信息（实时从 config.yaml 读取，修改配置文件后刷新即可同步）"""
    # 实时读取 config.yaml，而非使用启动时的静态变量
    live_config = load_config_from_yaml() or MEM0_CONFIG

    llm_config = live_config.get("llm", {})
    embedder_config = live_config.get("embedder", {})
    vector_config = live_config.get("vector_store", {})
    graph_config = live_config.get("graph_store", {})

    # 是否为生产环境（生产环境对 URL 做脱敏处理）
    is_prod = os.environ.get("ENV", "development") == "production"

    llm_base_url = llm_config.get("config", {}).get("ollama_base_url", llm_config.get("config", {}).get("openai_base_url", ""))
    embedder_base_url = embedder_config.get("config", {}).get("ollama_base_url", embedder_config.get("config", {}).get("openai_base_url", ""))
    graph_url = graph_config.get("config", {}).get("url", "")

    return {
        "llm": {
            "provider": llm_config.get("provider", "unknown"),
            "model": llm_config.get("config", {}).get("model", "unknown"),
            "base_url": _mask_url(llm_base_url) if is_prod else llm_base_url,
            "temperature": llm_config.get("config", {}).get("temperature", 0.1),
        },
        "embedder": {
            "provider": embedder_config.get("provider", "unknown"),
            "model": embedder_config.get("config", {}).get("model", "unknown"),
            "base_url": _mask_url(embedder_base_url) if is_prod else embedder_base_url,
        },
        "vector_store": {
            "provider": vector_config.get("provider", "unknown"),
            "collection_name": vector_config.get("config", {}).get("collection_name", ""),
            "embedding_model_dims": vector_config.get("config", {}).get("embedding_model_dims", 0),
        },
        "graph_store": {
            "provider": graph_config.get("provider", "unknown"),
            "url": _mask_url(graph_url) if is_prod else graph_url,
        },
    }


@app.get("/v1/config/test-llm")
async def test_llm_connection():
    """测试 LLM 大模型连接（实时从 config.yaml 读取配置）"""
    import requests as sync_requests

    live_config = load_config_from_yaml() or MEM0_CONFIG
    llm_config = live_config.get("llm", {})
    provider = llm_config.get("provider", "unknown")
    config = llm_config.get("config", {})
    model = config.get("model", "unknown")
    base_url = config.get("ollama_base_url", config.get("openai_base_url", ""))

    try:
        if provider == "ollama":
            # 测试 Ollama：调用 /api/tags 获取模型列表，验证目标模型是否存在
            resp = sync_requests.get(f"{base_url}/api/tags", timeout=10)
            resp.raise_for_status()
            models_data = resp.json()
            model_names = [m.get("name", "").split(":")[0] for m in models_data.get("models", [])]
            model_base = model.split(":")[0]
            model_found = model_base in model_names or model in [m.get("name", "") for m in models_data.get("models", [])]

            # 进一步做一次简单的生成测试
            gen_resp = sync_requests.post(
                f"{base_url}/api/generate",
                json={"model": model, "prompt": "hi", "stream": False, "options": {"num_predict": 5}},
                timeout=30,
            )
            gen_resp.raise_for_status()
            gen_text = gen_resp.json().get("response", "")

            return {
                "status": "connected",
                "provider": provider,
                "model": model,
                "base_url": base_url,
                "model_available": model_found,
                "test_response": gen_text[:100] if gen_text else "(空响应)",
                "message": f"LLM 连接成功，模型 {model} {'可用' if model_found else '未在模型列表中找到，但生成测试通过'}",
            }
        else:
            # OpenAI 兼容接口测试
            headers = {}
            api_key = config.get("api_key", "")
            if api_key:
                headers["Authorization"] = f"Bearer {api_key}"
            resp = sync_requests.get(f"{base_url}/models", headers=headers, timeout=10)
            resp.raise_for_status()
            return {
                "status": "connected",
                "provider": provider,
                "model": model,
                "base_url": base_url,
                "model_available": True,
                "message": f"LLM 连接成功（{provider}）",
            }
    except Exception as e:
        logger.warning(f"LLM 连接测试失败: {e}")
        return {
            "status": "error",
            "provider": provider,
            "model": model,
            "base_url": base_url,
            "model_available": False,
            "message": f"连接失败: {str(e)}",
        }


@app.get("/v1/config/test-embedder")
async def test_embedder_connection():
    """测试 Embedder 嵌入模型连接（实时从 config.yaml 读取配置）"""
    import requests as sync_requests

    live_config = load_config_from_yaml() or MEM0_CONFIG
    embedder_config = live_config.get("embedder", {})
    provider = embedder_config.get("provider", "unknown")
    config = embedder_config.get("config", {})
    model = config.get("model", "unknown")
    base_url = config.get("ollama_base_url", config.get("openai_base_url", ""))

    try:
        if provider == "ollama":
            # 测试 Ollama Embedder：发送一个简单的嵌入请求
            resp = sync_requests.post(
                f"{base_url}/api/embeddings",
                json={"model": model, "prompt": "test"},
                timeout=15,
            )
            resp.raise_for_status()
            embedding = resp.json().get("embedding", [])
            dims = len(embedding)

            return {
                "status": "connected",
                "provider": provider,
                "model": model,
                "base_url": base_url,
                "embedding_dims": dims,
                "message": f"Embedder 连接成功，模型 {model}，向量维度 {dims}",
            }
        else:
            # OpenAI 兼容接口测试
            headers = {"Content-Type": "application/json"}
            api_key = config.get("api_key", "")
            if api_key:
                headers["Authorization"] = f"Bearer {api_key}"
            resp = sync_requests.post(
                f"{base_url}/embeddings",
                json={"model": model, "input": "test"},
                headers=headers,
                timeout=15,
            )
            resp.raise_for_status()
            data = resp.json().get("data", [{}])
            dims = len(data[0].get("embedding", [])) if data else 0
            return {
                "status": "connected",
                "provider": provider,
                "model": model,
                "base_url": base_url,
                "embedding_dims": dims,
                "message": f"Embedder 连接成功（{provider}），向量维度 {dims}",
            }
    except Exception as e:
        logger.warning(f"Embedder 连接测试失败: {e}")
        return {
            "status": "error",
            "provider": provider,
            "model": model,
            "base_url": base_url,
            "embedding_dims": 0,
            "message": f"连接失败: {str(e)}",
        }


# ============ 辅助函数：获取所有记忆 ============

def _get_all_memories_raw() -> list:
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


# ============ 记忆 CRUD 接口 ============

@app.post("/v1/memories/")
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
            ai_categories = _auto_categorize_memory(memory_text)
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
                                    per_item_cats = _auto_categorize_memory(memory_content)
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
                                _save_category_snapshot(mid, init_cats)
                            # 记录 ADD 事件到自建历史
                            memory_text = item.get("memory", "") if isinstance(item, dict) else ""
                            _save_change_log(mid, "ADD", memory_text, init_cats)
                    except Exception:
                        pass
        except Exception as e2:
            logger.warning(f"补写 metadata 失败: {e2}")

        return result
    except Exception as e:
        logger.error(f"添加记忆失败: {e}")
        raise HTTPException(status_code=500, detail=_safe_error_detail(e))


class BatchImportItem(BaseModel):
    """批量导入中的单条记忆"""
    content: str = Field(..., max_length=10000)  # 单条内容最大 10000 字符
    user_id: Optional[str] = Field(None, max_length=100)
    metadata: Optional[Dict[str, Any]] = None
    categories: Optional[List[str]] = Field(None, max_length=20)
    state: Optional[str] = Field("active", max_length=20)


class BatchImportRequest(BaseModel):
    """批量导入请求"""
    items: List[BatchImportItem] = Field(..., max_length=100)  # 单次最多导入 100 条
    default_user_id: Optional[str] = Field(None, max_length=100)
    infer: Optional[bool] = False  # 默认原文存储
    auto_categorize: Optional[bool] = True  # 默认 AI 自动分类


class BatchImportResultItem(BaseModel):
    index: int
    success: bool
    id: Optional[str] = None
    memory: Optional[str] = None
    error: Optional[str] = None


class BatchImportResponse(BaseModel):
    total: int
    success: int
    failed: int
    results: List[BatchImportResultItem]


@app.post("/v1/memories/batch")
async def batch_import_memories(request: BatchImportRequest):
    """批量导入记忆 — 一次性接收多条记忆，逐条写入并返回结果汇总"""
    if not request.items:
        raise HTTPException(status_code=400, detail="items 不能为空")

    m = get_memory()
    results: List[BatchImportResultItem] = []
    success_count = 0
    failed_count = 0

    for idx, item in enumerate(request.items):
        try:
            # 确定 user_id：default_user_id 优先 > item.user_id > "default"
            uid = (request.default_user_id or "").strip() or (item.user_id or "").strip() or "default"

            # 合并 metadata
            final_metadata: Dict[str, Any] = dict(item.metadata or {})
            user_selected_categories = False

            if item.categories:
                valid_cats = [c for c in item.categories if c in VALID_CATEGORIES]
                if valid_cats:
                    final_metadata["categories"] = valid_cats
                    user_selected_categories = True

            # 批量导入的记忆统一为 active 状态
            final_metadata["state"] = "active"

            # AI 自动分类
            if not user_selected_categories and request.auto_categorize:
                ai_categories = _auto_categorize_memory(item.content)
                if ai_categories:
                    final_metadata["categories"] = ai_categories

            kwargs: Dict[str, Any] = {"user_id": uid}
            if final_metadata:
                kwargs["metadata"] = final_metadata

            messages = [{"role": "user", "content": item.content}]
            result = m.add(messages=messages, infer=request.infer, **kwargs)

            # 补写 metadata 到 Qdrant（与 add_memory 逻辑一致）
            try:
                added_ids = []
                if isinstance(result, dict) and "results" in result:
                    added_ids = [r for r in result["results"] if r.get("id")]
                elif isinstance(result, list):
                    added_ids = [r for r in result if r.get("id")]

                if added_ids:
                    collection_name = MEM0_CONFIG["vector_store"]["config"]["collection_name"]
                    qdrant_client = m.vector_store.client
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
                                    _save_category_snapshot(mid, init_cats)
                                memory_text = added_item.get("memory", "") if isinstance(added_item, dict) else ""
                                _save_change_log(mid, "ADD", memory_text, init_cats)
                        except Exception:
                            pass
            except Exception:
                pass

            # 取第一条结果的 id
            first_id = None
            first_memory = None
            if isinstance(result, dict) and "results" in result and result["results"]:
                first_id = result["results"][0].get("id")
                first_memory = result["results"][0].get("memory")

            results.append(BatchImportResultItem(
                index=idx, success=True, id=first_id, memory=first_memory
            ))
            success_count += 1

        except Exception as e:
            logger.warning(f"批量导入第 {idx+1} 条失败: {e}")
            results.append(BatchImportResultItem(
                index=idx, success=False, error=str(e)
            ))
            failed_count += 1

    return BatchImportResponse(
        total=len(request.items),
        success=success_count,
        failed=failed_count,
        results=results,
    )


@app.get("/v1/memories/")
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
        all_memories = _get_all_memories_raw()

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


@app.get("/v1/memories/{memory_id}/")
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
        _log_access(memory_id, "view", preview)
        return formatted
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取记忆失败: {e}")
        raise HTTPException(status_code=500, detail=_safe_error_detail(e))


@app.put("/v1/memories/{memory_id}/")
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
                            ai_categories = _auto_categorize_memory(memory_text)
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
                    _save_category_snapshot(memory_id, new_cats)
                    logger.info(f"已更新记忆 {memory_id} 的 metadata: state={current_metadata.get('state')}, categories={new_cats}")
            except Exception as meta_err:
                logger.warning(f"更新 metadata 失败: {meta_err}")

        # 记录 UPDATE 事件到自建历史（真实时间 + 旧/新内容 + 当前标签）
        new_memory_text = request.text or old_memory_text
        # 如果内容没有变化（只改了标签/元数据），old_memory 传 None 避免显示相同的旧/新内容
        effective_old_memory = old_memory_text if (request.text and old_memory_text != new_memory_text) else None
        _save_change_log(memory_id, "UPDATE", new_memory_text, new_cats, effective_old_memory, old_categories)

        return result
    except Exception as e:
        logger.error(f"更新记忆失败: {e}")
        raise HTTPException(status_code=500, detail=_safe_error_detail(e))


@app.delete("/v1/memories/{memory_id}/")
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
            _save_change_log(memory_id, "DELETE", old_memory_text, old_categories)

            logger.info(f"已软删除记忆 {memory_id}")
            return {"message": "记忆已删除"}
        except HTTPException:
            raise
        except Exception as inner_err:
            logger.warning(f"软删除失败，回退到物理删除: {inner_err}")
            m.delete(memory_id=memory_id)
            return {"message": "记忆已删除"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"删除记忆失败: {e}")
        raise HTTPException(status_code=500, detail=_safe_error_detail(e))


@app.delete("/v1/memories/")
async def delete_all_memories(
    user_id: Optional[str] = Query(None),
    confirm: bool = Query(False, description="清空全部记忆时必须传 confirm=true 以防误操作"),
):
    """删除用户的所有记忆（清空全部需要 confirm=true 确认）"""
    try:
        m = get_memory()
        if user_id:
            m.delete_all(user_id=user_id)
            return {"message": f"用户 {user_id} 的所有记忆已删除"}
        else:
            # 无 user_id 时必须显式确认，防止误删全部数据
            if not confirm:
                raise HTTPException(
                    status_code=400,
                    detail="清空全部记忆是危险操作，请传入 confirm=true 参数以确认执行"
                )
            # 复用 Mem0 内部的 Qdrant 客户端清空集合
            try:
                from qdrant_client.models import PointIdsList
                collection_name = MEM0_CONFIG["vector_store"]["config"]["collection_name"]
                qdrant_client = m.vector_store.client
                records, _ = qdrant_client.scroll(
                    collection_name=collection_name,
                    limit=1000,
                    with_payload=False,
                    with_vectors=False,
                )
                if records:
                    ids = [record.id for record in records]
                    qdrant_client.delete(
                        collection_name=collection_name,
                        points_selector=PointIdsList(points=ids),
                    )
                return {"message": "所有记忆已删除"}
            except Exception as qdrant_err:
                logger.error(f"Qdrant 直接删除失败: {qdrant_err}")
                raise HTTPException(status_code=500, detail=_safe_error_detail(qdrant_err))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"删除记忆失败: {e}")
        raise HTTPException(status_code=500, detail=_safe_error_detail(e))


# ============ 搜索接口 ============

def _get_real_states(memory_ids: list) -> dict:
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


@app.post("/v1/memories/search/")
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

        # 统一返回格式并附加 categories/state
        formatted = []
        if isinstance(result, dict) and "results" in result:
            formatted = [format_mem0_result(item) for item in result["results"]]
            # 保留 score 字段
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

        # 从 Qdrant 直接查询每条记忆的真实 state（Mem0 search 返回的 metadata 可能不含 state）
        memory_ids = [item["id"] for item in formatted if item.get("id")]
        real_states = _get_real_states(memory_ids)

        # 用真实 state 替换，并过滤掉已删除的记忆
        for item in formatted:
            mid = item.get("id", "")
            if mid in real_states:
                item["state"] = real_states[mid]
        formatted = [item for item in formatted if item.get("state", "active") != "deleted"]

        return {"results": formatted}
    except Exception as e:
        logger.error(f"搜索记忆失败: {e}")
        raise HTTPException(status_code=500, detail=_safe_error_detail(e))


# ============ 历史记录接口 ============

@app.get("/v1/memories/history/{memory_id}/")
async def get_memory_history(memory_id: str):
    """获取记忆的修改历史（优先使用自建历史，带真实操作时间和标签快照）"""
    try:
        # 优先查自建历史
        change_logs = _get_change_logs(memory_id)
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


# ============ 统计接口 ============

@app.get("/v1/stats/")
async def get_stats():
    """获取统计数据（分类分布、状态分布、每日趋势）"""
    try:
        all_memories = _get_all_memories_raw()

        # 活跃记忆（排除已删除），用于统计 total_memories、total_users、分类分布、每日趋势
        active_memories = [m for m in all_memories if m.get("state", "active") != "deleted"]

        # 基础统计（仅统计活跃记忆）
        total_memories = len(active_memories)
        user_set = set()
        for m in active_memories:
            uid = m.get("user_id")
            if uid:
                user_set.add(uid)
        total_users = len(user_set)

        # 分类分布（仅统计活跃记忆）
        category_distribution = {cat: 0 for cat in VALID_CATEGORIES}
        uncategorized_count = 0
        for m in active_memories:
            cats = m.get("categories") or []
            if not cats:
                uncategorized_count += 1
            else:
                for cat in cats:
                    if cat in category_distribution:
                        category_distribution[cat] += 1

        # 状态分布（统计全部记忆，包含已删除，方便查看各状态数量）
        state_distribution = {s: 0 for s in VALID_STATES}
        for m in all_memories:
            s = m.get("state", "active")
            if s in state_distribution:
                state_distribution[s] += 1

        # 近 30 天每日趋势（仅统计活跃记忆）
        daily_trend = []
        today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        for i in range(29, -1, -1):
            day = today - timedelta(days=i)
            day_str = day.strftime("%Y-%m-%d")
            count = 0
            for m in active_memories:
                created = m.get("created_at")
                if created:
                    try:
                        created_dt = datetime.fromisoformat(str(created).replace("Z", "+00:00"))
                        if created_dt.strftime("%Y-%m-%d") == day_str:
                            count += 1
                    except (ValueError, TypeError):
                        pass
            daily_trend.append({"date": day_str, "count": count})

        return {
            "total_memories": total_memories,
            "total_users": total_users,
            "category_distribution": category_distribution,
            "uncategorized_count": uncategorized_count,
            "state_distribution": state_distribution,
            "daily_trend": daily_trend,
        }
    except Exception as e:
        logger.error(f"获取统计数据失败: {e}")
        raise HTTPException(status_code=500, detail=_safe_error_detail(e))


# ============ 关联记忆接口 ============

@app.get("/v1/memories/{memory_id}/related/")
async def get_related_memories(memory_id: str, limit: int = Query(5, ge=1, le=20)):
    """获取语义相关的记忆（基于当前记忆内容搜索）"""
    try:
        m = get_memory()
        # 先获取当前记忆内容
        current = m.get(memory_id)
        if not current:
            raise HTTPException(status_code=404, detail="记忆不存在")

        memory_text = current.get("memory", "") if isinstance(current, dict) else ""
        if not memory_text:
            return {"results": []}

        # 用当前记忆文本做语义搜索
        search_result = m.search(query=memory_text, limit=limit + 1)

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

        # 从 Qdrant 直接查询每条记忆的真实 state，过滤已删除记忆
        memory_ids = [item["id"] for item in results if item.get("id")]
        real_states = _get_real_states(memory_ids)
        for item in results:
            mid = item.get("id", "")
            if mid in real_states:
                item["state"] = real_states[mid]
        results = [item for item in results if item.get("state", "active") != "deleted"]

        # 截取到 limit 条
        results = results[:limit]

        return {"results": results}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取关联记忆失败: {e}")
        raise HTTPException(status_code=500, detail=_safe_error_detail(e))


# ============ 访问日志接口 ============

@app.get("/v1/access-logs/")
async def get_access_logs_api(
    memory_id: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    """获取访问日志（可按记忆 ID 筛选）"""
    try:
        logs = _get_access_logs(memory_id=memory_id, limit=limit, offset=offset)
        return {"logs": logs, "total": len(logs)}
    except Exception as e:
        logger.error(f"获取访问日志失败: {e}")
        raise HTTPException(status_code=500, detail=_safe_error_detail(e))


@app.get("/v1/memories/{memory_id}/access-logs/")
async def get_memory_access_logs(
    memory_id: str,
    limit: int = Query(10, ge=1, le=100),
):
    """获取单条记忆的访问日志"""
    try:
        logs = _get_access_logs(memory_id=memory_id, limit=limit)
        return {"logs": logs}
    except Exception as e:
        logger.error(f"获取记忆访问日志失败: {e}")
        raise HTTPException(status_code=500, detail=_safe_error_detail(e))


# ============ 请求日志接口 ============

@app.get("/v1/request-logs/")
async def get_request_logs_api(
    request_type: Optional[str] = Query(None, description="请求类型筛选: 添加/搜索/删除/更新"),
    since: Optional[str] = Query(None, description="起始时间 ISO 格式，如 2026-03-27T10:00:00"),
    until: Optional[str] = Query(None, description="结束时间 ISO 格式，如 2026-04-02T23:59:59"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    """获取请求日志"""
    try:
        logs, total = _get_request_logs(request_type=request_type, since=since, until=until, limit=limit, offset=offset)
        return {"logs": logs, "total": total}
    except Exception as e:
        logger.error(f"获取请求日志失败: {e}")
        raise HTTPException(status_code=500, detail=_safe_error_detail(e))


@app.get("/v1/request-logs/stats/")
async def get_request_logs_stats(
    since: Optional[str] = Query(None, description="起始时间 ISO 格式"),
    until: Optional[str] = Query(None, description="结束时间 ISO 格式"),
):
    """获取请求日志统计（按类型分组计数 + 按类型趋势数据，自动根据时间范围切换粒度）"""
    try:
        conn = _get_db_conn()
        conn.row_factory = sqlite3.Row

        where = "WHERE 1=1"
        params: list = []
        if since:
            where += " AND timestamp >= ?"
            params.append(since)
        if until:
            where += " AND timestamp <= ?"
            params.append(until)

        # 按类型分组
        type_rows = conn.execute(
            f"SELECT request_type, COUNT(*) as count FROM request_logs {where} GROUP BY request_type ORDER BY count DESC",
            params,
        ).fetchall()
        type_distribution = {row["request_type"]: row["count"] for row in type_rows}

        # 判断粒度：since 在 24 小时内用 30 分钟粒度，否则按天
        now = datetime.now()
        if since:
            try:
                since_dt = datetime.fromisoformat(since.replace("Z", "+00:00")).replace(tzinfo=None)
            except (ValueError, TypeError):
                since_dt = now - timedelta(days=14)
            hours_diff = (now - since_dt).total_seconds() / 3600
        else:
            hours_diff = 999  # 无 since 视为大范围

        # 小时级粒度（<=24h）：按 1 小时分桶
        if hours_diff <= 24:
            granularity = "hour"
            # 按 1 小时分桶查询
            hourly_rows = conn.execute(
                f"""SELECT
                      STRFTIME('%Y-%m-%d %H:00', timestamp) as slot,
                      request_type, COUNT(*) as count
                    FROM request_logs {where}
                    GROUP BY slot, request_type
                    ORDER BY slot""",
                params,
            ).fetchall()

            slot_map: Dict[str, Dict[str, int]] = {}
            all_types = set()
            for row in hourly_rows:
                s = row["slot"]
                t = row["request_type"]
                all_types.add(t)
                if s not in slot_map:
                    slot_map[s] = {}
                slot_map[s][t] = row["count"]

            # 补全 24 小时时间槽（00:00 ~ 23:00）
            daily_trend = []
            slot_start = since_dt.replace(hour=0, minute=0, second=0, microsecond=0)
            slot_end = slot_start.replace(hour=23, minute=0)
            while slot_start <= slot_end:
                slot_key = slot_start.strftime("%Y-%m-%d %H:%M")
                entry: Dict[str, Any] = {"date": slot_key}
                type_counts = slot_map.get(slot_key.replace(":00", ":00"), {})
                for t in all_types:
                    entry[t] = type_counts.get(t, 0)
                daily_trend.append(entry)
                slot_start += timedelta(hours=1)

        else:
            granularity = "day"
            # 按天分组（原逻辑）
            daily_type_rows = conn.execute(
                f"""SELECT DATE(timestamp) as date, request_type, COUNT(*) as count
                   FROM request_logs {where}
                   GROUP BY DATE(timestamp), request_type
                   ORDER BY date""",
                params,
            ).fetchall()

            daily_type_map: Dict[str, Dict[str, int]] = {}
            all_types = set()
            for row in daily_type_rows:
                d = row["date"]
                t = row["request_type"]
                all_types.add(t)
                if d not in daily_type_map:
                    daily_type_map[d] = {}
                daily_type_map[d][t] = row["count"]

            # 补全缺失日期
            num_days = min(int(hours_diff / 24) + 1, 30)
            daily_trend = []
            for i in range(num_days - 1, -1, -1):
                d = (now - timedelta(days=i)).strftime("%Y-%m-%d")
                entry: Dict[str, Any] = {"date": d}
                type_counts = daily_type_map.get(d, {})
                for t in all_types:
                    entry[t] = type_counts.get(t, 0)
                daily_trend.append(entry)

        # 总请求数
        total = conn.execute(f"SELECT COUNT(*) FROM request_logs {where}", params).fetchone()[0]

        conn.close()
        return {
            "total": total,
            "type_distribution": type_distribution,
            "daily_trend": daily_trend,
            "types": sorted(all_types),
            "granularity": granularity,
        }
    except Exception as e:
        logger.error(f"获取请求日志统计失败: {e}")
        raise HTTPException(status_code=500, detail=_safe_error_detail(e))


# ============ Neo4j 图数据库工具函数 ============

# 全局单例 Neo4j 驱动（延迟初始化，应用关闭时统一清理）
_neo4j_driver_instance = None

def _get_neo4j_driver():
    """获取 Neo4j 驱动全局单例（延迟初始化，复用连接池）"""
    global _neo4j_driver_instance
    if _neo4j_driver_instance is not None:
        return _neo4j_driver_instance
    graph_config = MEM0_CONFIG.get("graph_store", {}).get("config", {})
    if not graph_config:
        return None
    try:
        from neo4j import GraphDatabase
        _neo4j_driver_instance = GraphDatabase.driver(
            graph_config["url"],
            auth=(graph_config["username"], graph_config["password"]),
        )
        logger.info("Neo4j 驱动全局单例已初始化")
        return _neo4j_driver_instance
    except Exception as e:
        logger.warning(f"Neo4j 连接失败: {e}")
        return None

def _close_neo4j_driver():
    """关闭全局 Neo4j 驱动（应用关闭时调用）"""
    global _neo4j_driver_instance
    if _neo4j_driver_instance is not None:
        try:
            _neo4j_driver_instance.close()
            logger.info("Neo4j 驱动已关闭")
        except Exception as e:
            logger.warning(f"关闭 Neo4j 驱动失败: {e}")
        finally:
            _neo4j_driver_instance = None


def _neo4j_query(cypher: str, params: dict = None) -> list:
    """执行 Neo4j Cypher 查询并返回结果列表（复用全局驱动）"""
    driver = _get_neo4j_driver()
    if not driver:
        return []
    try:
        with driver.session() as session:
            result = session.run(cypher, params or {})
            return [record.data() for record in result]
    except Exception as e:
        logger.warning(f"Neo4j 查询失败: {e}")
        return []


# ============ Graph Memory API 端点 ============

@app.get("/v1/graph/stats")
async def get_graph_stats():
    """获取图谱统计信息（实体数、关系数、类型分布）"""
    try:
        # 实体总数
        entity_count_result = _neo4j_query("MATCH (n) RETURN count(n) as count")
        entity_count = entity_count_result[0]["count"] if entity_count_result else 0

        # 关系总数
        relation_count_result = _neo4j_query("MATCH ()-[r]->() RETURN count(r) as count")
        relation_count = relation_count_result[0]["count"] if relation_count_result else 0

        # 关系类型分布
        relation_types_result = _neo4j_query(
            "MATCH ()-[r]->() RETURN type(r) as relation_type, count(r) as count ORDER BY count DESC"
        )
        relation_type_distribution = {
            item["relation_type"]: item["count"] for item in relation_types_result
        }

        # 按用户统计实体数
        user_entity_result = _neo4j_query(
            "MATCH (n) WHERE n.user_id IS NOT NULL RETURN n.user_id as user_id, count(n) as count ORDER BY count DESC LIMIT 20"
        )
        user_entity_distribution = {
            item["user_id"]: item["count"] for item in user_entity_result
        }

        return {
            "entity_count": entity_count,
            "relation_count": relation_count,
            "relation_type_distribution": relation_type_distribution,
            "user_entity_distribution": user_entity_distribution,
        }
    except Exception as e:
        logger.error(f"获取图谱统计失败: {e}")
        raise HTTPException(status_code=500, detail=_safe_error_detail(e))


@app.get("/v1/graph/entities")
async def get_graph_entities(
    user_id: Optional[str] = Query(None, description="按用户ID筛选"),
    search: Optional[str] = Query(None, description="搜索实体名称"),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    """获取实体列表"""
    try:
        where_clauses = []
        params: Dict[str, Any] = {"limit": limit, "offset": offset}

        if user_id:
            where_clauses.append("n.user_id = $user_id")
            params["user_id"] = user_id
        if search:
            where_clauses.append("toLower(n.name) CONTAINS toLower($search)")
            params["search"] = search

        where_str = " WHERE " + " AND ".join(where_clauses) if where_clauses else ""

        # 查询实体及其关系数
        cypher = f"""
            MATCH (n){where_str}
            OPTIONAL MATCH (n)-[r]-()
            RETURN n.name as name, n.user_id as user_id, labels(n) as labels,
                   elementId(n) as element_id, count(r) as relation_count
            ORDER BY relation_count DESC
            SKIP $offset LIMIT $limit
        """
        entities = _neo4j_query(cypher, params)

        # 总数
        count_cypher = f"MATCH (n){where_str} RETURN count(n) as total"
        count_params = {k: v for k, v in params.items() if k not in ("limit", "offset")}
        total_result = _neo4j_query(count_cypher, count_params)
        total = total_result[0]["total"] if total_result else 0

        return {
            "entities": entities,
            "total": total,
            "limit": limit,
            "offset": offset,
        }
    except Exception as e:
        logger.error(f"获取实体列表失败: {e}")
        raise HTTPException(status_code=500, detail=_safe_error_detail(e))


@app.get("/v1/graph/relations")
async def get_graph_relations(
    user_id: Optional[str] = Query(None, description="按用户ID筛选"),
    search: Optional[str] = Query(None, description="搜索关系中的实体名称"),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    """获取关系三元组列表"""
    try:
        where_clauses = []
        params: Dict[str, Any] = {"limit": limit, "offset": offset}

        if user_id:
            where_clauses.append("(a.user_id = $user_id OR b.user_id = $user_id)")
            params["user_id"] = user_id
        if search:
            where_clauses.append(
                "(toLower(a.name) CONTAINS toLower($search) OR toLower(b.name) CONTAINS toLower($search))"
            )
            params["search"] = search

        where_str = " WHERE " + " AND ".join(where_clauses) if where_clauses else ""

        cypher = f"""
            MATCH (a)-[r]->(b){where_str}
            RETURN a.name as source, type(r) as relation, b.name as target,
                   a.user_id as source_user_id, b.user_id as target_user_id,
                   elementId(r) as element_id
            ORDER BY source
            SKIP $offset LIMIT $limit
        """
        relations = _neo4j_query(cypher, params)

        # 总数
        count_cypher = f"MATCH (a)-[r]->(b){where_str} RETURN count(r) as total"
        count_params = {k: v for k, v in params.items() if k not in ("limit", "offset")}
        total_result = _neo4j_query(count_cypher, count_params)
        total = total_result[0]["total"] if total_result else 0

        return {
            "relations": relations,
            "total": total,
            "limit": limit,
            "offset": offset,
        }
    except Exception as e:
        logger.error(f"获取关系列表失败: {e}")
        raise HTTPException(status_code=500, detail=_safe_error_detail(e))


class GraphSearchRequest(BaseModel):
    query: str = Field(..., max_length=500)  # 图谱搜索查询最大 500 字符
    user_id: Optional[str] = Field(None, max_length=100)
    limit: Optional[int] = Field(20, ge=1, le=200)  # 返回数量限制 1-200


@app.post("/v1/graph/search")
async def search_graph(request: GraphSearchRequest):
    """基于图谱的搜索（搜索实体名称和关系）"""
    try:
        params: Dict[str, Any] = {"query": request.query.lower(), "limit": request.limit or 20}
        user_filter = ""
        if request.user_id:
            user_filter = "AND (a.user_id = $user_id OR b.user_id = $user_id)"
            params["user_id"] = request.user_id

        # 搜索包含关键词的实体及其关系
        cypher = f"""
            MATCH (a)-[r]->(b)
            WHERE (toLower(a.name) CONTAINS $query OR toLower(b.name) CONTAINS $query)
            {user_filter}
            RETURN a.name as source, type(r) as relation, b.name as target,
                   a.user_id as source_user_id, b.user_id as target_user_id
            LIMIT $limit
        """
        results = _neo4j_query(cypher, params)

        # 同时搜索孤立实体（没有关系的实体）
        entity_cypher = f"""
            MATCH (n)
            WHERE toLower(n.name) CONTAINS $query
            {"AND n.user_id = $user_id" if request.user_id else ""}
            AND NOT (n)-[]-()
            RETURN n.name as name, n.user_id as user_id, labels(n) as labels
            LIMIT $limit
        """
        isolated_entities = _neo4j_query(entity_cypher, params)

        return {
            "relations": results,
            "isolated_entities": isolated_entities,
            "total": len(results) + len(isolated_entities),
        }
    except Exception as e:
        logger.error(f"图谱搜索失败: {e}")
        raise HTTPException(status_code=500, detail=_safe_error_detail(e))


@app.get("/v1/graph/user/{user_id}")
async def get_user_graph(
    user_id: str,
    limit: int = Query(200, ge=1, le=1000),
):
    """获取指定用户的子图数据（用于可视化）"""
    try:
        # 获取用户的所有实体和关系
        cypher = """
            MATCH (a)-[r]->(b)
            WHERE a.user_id = $user_id OR b.user_id = $user_id
            RETURN a.name as source, a.user_id as source_user_id, labels(a) as source_labels,
                   type(r) as relation,
                   b.name as target, b.user_id as target_user_id, labels(b) as target_labels
            LIMIT $limit
        """
        relations = _neo4j_query(cypher, {"user_id": user_id, "limit": limit})

        # 构建节点和边的数据结构（用于前端力导向图）
        nodes_map: Dict[str, dict] = {}
        links = []

        for rel in relations:
            source_name = rel["source"]
            target_name = rel["target"]

            if source_name not in nodes_map:
                nodes_map[source_name] = {
                    "id": source_name,
                    "name": source_name,
                    "user_id": rel.get("source_user_id"),
                    "labels": rel.get("source_labels", []),
                    "val": 1,
                }
            else:
                nodes_map[source_name]["val"] += 1

            if target_name not in nodes_map:
                nodes_map[target_name] = {
                    "id": target_name,
                    "name": target_name,
                    "user_id": rel.get("target_user_id"),
                    "labels": rel.get("target_labels", []),
                    "val": 1,
                }
            else:
                nodes_map[target_name]["val"] += 1

            links.append({
                "source": source_name,
                "target": target_name,
                "relation": rel["relation"],
            })

        # 也获取孤立实体（有 user_id 但没有关系的实体）
        isolated_cypher = """
            MATCH (n)
            WHERE n.user_id = $user_id AND NOT (n)-[]-()
            RETURN n.name as name, n.user_id as user_id, labels(n) as labels
            LIMIT $limit
        """
        isolated = _neo4j_query(isolated_cypher, {"user_id": user_id, "limit": limit})
        for node in isolated:
            name = node["name"]
            if name not in nodes_map:
                nodes_map[name] = {
                    "id": name,
                    "name": name,
                    "user_id": node.get("user_id"),
                    "labels": node.get("labels", []),
                    "val": 1,
                }

        return {
            "nodes": list(nodes_map.values()),
            "links": links,
            "node_count": len(nodes_map),
            "link_count": len(links),
        }
    except Exception as e:
        logger.error(f"获取用户图谱失败: {e}")
        raise HTTPException(status_code=500, detail=_safe_error_detail(e))


@app.get("/v1/graph/all")
async def get_all_graph(
    limit: int = Query(300, ge=1, le=2000),
):
    """获取全部图谱数据（用于可视化）"""
    try:
        cypher = """
            MATCH (a)-[r]->(b)
            RETURN a.name as source, a.user_id as source_user_id, labels(a) as source_labels,
                   type(r) as relation,
                   b.name as target, b.user_id as target_user_id, labels(b) as target_labels
            LIMIT $limit
        """
        relations = _neo4j_query(cypher, {"limit": limit})

        nodes_map: Dict[str, dict] = {}
        links = []

        for rel in relations:
            source_name = rel["source"]
            target_name = rel["target"]

            if source_name not in nodes_map:
                nodes_map[source_name] = {
                    "id": source_name,
                    "name": source_name,
                    "user_id": rel.get("source_user_id"),
                    "labels": rel.get("source_labels", []),
                    "val": 1,
                }
            else:
                nodes_map[source_name]["val"] += 1

            if target_name not in nodes_map:
                nodes_map[target_name] = {
                    "id": target_name,
                    "name": target_name,
                    "user_id": rel.get("target_user_id"),
                    "labels": rel.get("target_labels", []),
                    "val": 1,
                }
            else:
                nodes_map[target_name]["val"] += 1

            links.append({
                "source": source_name,
                "target": target_name,
                "relation": rel["relation"],
            })

        return {
            "nodes": list(nodes_map.values()),
            "links": links,
            "node_count": len(nodes_map),
            "link_count": len(links),
        }
    except Exception as e:
        logger.error(f"获取全部图谱失败: {e}")
        raise HTTPException(status_code=500, detail=_safe_error_detail(e))


@app.delete("/v1/graph/entities/{entity_name}")
async def delete_graph_entity(entity_name: str, user_id: Optional[str] = Query(None)):
    """删除指定实体及其所有关联关系"""
    try:
        params: Dict[str, Any] = {"name": entity_name}
        user_filter = ""
        if user_id:
            user_filter = "AND n.user_id = $user_id"
            params["user_id"] = user_id

        cypher = f"MATCH (n) WHERE n.name = $name {user_filter} DETACH DELETE n RETURN count(n) as deleted"
        result = _neo4j_query(cypher, params)
        deleted = result[0]["deleted"] if result else 0

        if deleted == 0:
            raise HTTPException(status_code=404, detail="实体不存在")

        return {"message": f"已删除实体 '{entity_name}' 及其关联关系", "deleted": deleted}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"删除实体失败: {e}")
        raise HTTPException(status_code=500, detail=_safe_error_detail(e))


@app.delete("/v1/graph/relations")
async def delete_graph_relation(
    source: str = Query(..., description="源实体名称"),
    relation: str = Query(..., description="关系类型"),
    target: str = Query(..., description="目标实体名称"),
):
    """删除指定关系"""
    try:
        cypher = """
            MATCH (a {name: $source})-[r]->(b {name: $target})
            WHERE type(r) = $relation
            DELETE r
            RETURN count(r) as deleted
        """
        result = _neo4j_query(cypher, {"source": source, "relation": relation, "target": target})
        deleted = result[0]["deleted"] if result else 0

        if deleted == 0:
            raise HTTPException(status_code=404, detail="关系不存在")

        return {"message": f"已删除关系: {source} --[{relation}]--> {target}", "deleted": deleted}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"删除关系失败: {e}")
        raise HTTPException(status_code=500, detail=_safe_error_detail(e))


@app.get("/v1/graph/health")
async def graph_health_check():
    """检查 Neo4j 图数据库连接状态"""
    try:
        driver = _get_neo4j_driver()
        if not driver:
            return {"status": "disconnected", "message": "未配置 graph_store"}
        try:
            with driver.session() as session:
                result = session.run("RETURN 1 as ok")
                result.single()
            return {"status": "connected", "message": "Neo4j 连接正常"}
        except Exception as e:
            return {"status": "error", "message": str(e)}
    except Exception as e:
        return {"status": "error", "message": str(e)}


# ============ 启动入口 ============

if __name__ == "__main__":
    # 默认监听 8080 端口，与前端 .env.local 中配置一致
    port = int(os.environ.get("MEM0_PORT", 8080))
    logger.info(f"启动 Mem0 API 服务，端口: {port}，环境: {'production' if IS_PRODUCTION else 'development'}")

    run_kwargs = {
        "host": "0.0.0.0",
        "port": port,
        "log_level": "info",
    }

    # 开发环境启用热重载，生产环境禁用
    if not IS_PRODUCTION:
        run_kwargs.update({
            "reload": True,
            "reload_includes": ["*.py"],
            "reload_excludes": ["qdrant_data/**", "*.log"],
        })

    uvicorn.run("server:app", **run_kwargs)
