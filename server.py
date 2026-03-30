"""
Mem0 Dashboard 后端 API 服务
使用 FastAPI 实现，Qdrant 采用本地文件模式（无需额外部署向量数据库）
"""

import os
import json
import time
import logging
import sqlite3
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from pydantic import BaseModel
import uvicorn

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ============ Qdrant 本地文件存储路径 ============
# 使用项目目录下的 qdrant_data 文件夹，基于当前文件位置动态计算
QDRANT_DATA_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "qdrant_data")

# ============ Mem0 配置（方案二：本地文件模式） ============
MEM0_CONFIG = {
    "vector_store": {
        "provider": "qdrant",
        "config": {
            "collection_name": "mem0",
            "embedding_model_dims": 768,
            "path": QDRANT_DATA_PATH,
            "on_disk": True,  # 持久化存储，重启不丢数据
        },
    },
    # LLM 配置（默认使用 OpenAI，需设置 OPENAI_API_KEY 环境变量）
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
    "version": "v1.1",
}

# ============ 分类和状态常量 ============
VALID_CATEGORIES = {
    "personal", "relationships", "preferences", "health", "travel",
    "work", "education", "projects", "ai_ml_technology", "technical_support",
    "finance", "shopping", "legal", "entertainment", "messages",
    "customer_support", "product_feedback", "news", "organization", "goals",
}
VALID_STATES = {"active", "paused", "archived", "deleted"}

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


def _init_access_log_db():
    """初始化访问日志和请求日志数据库"""
    conn = sqlite3.connect(ACCESS_LOG_DB_PATH)
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
    # 标签快照表（记录每次标签变更，用于修改历史展示）
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
        conn = sqlite3.connect(ACCESS_LOG_DB_PATH)
        conn.execute(
            "INSERT INTO category_snapshots (memory_id, categories, timestamp) VALUES (?, ?, ?)",
            (memory_id, cats_json, ts),
        )
        conn.commit()
        conn.close()
    except Exception as e:
        logger.warning(f"记录标签快照失败: {e}")


def _get_category_snapshots(memory_id: str) -> list:
    """获取某条记忆的所有标签快照，按时间正序"""
    try:
        conn = sqlite3.connect(ACCESS_LOG_DB_PATH)
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT categories, timestamp FROM category_snapshots WHERE memory_id = ? ORDER BY timestamp ASC",
            (memory_id,),
        ).fetchall()
        conn.close()
        result = []
        for row in rows:
            try:
                cats = json.loads(row["categories"])
            except (json.JSONDecodeError, TypeError):
                cats = []
            result.append({"categories": cats, "timestamp": row["timestamp"]})
        return result
    except Exception as e:
        logger.warning(f"查询标签快照失败: {e}")
        return []


def _log_access(memory_id: str, action: str, memory_preview: str = ""):
    """记录一条访问日志"""
    try:
        conn = sqlite3.connect(ACCESS_LOG_DB_PATH)
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
        conn = sqlite3.connect(ACCESS_LOG_DB_PATH)
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
        conn = sqlite3.connect(ACCESS_LOG_DB_PATH)
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


def _get_request_logs(request_type: str = None, since: str = None, limit: int = 50, offset: int = 0) -> tuple:
    """查询请求日志，返回 (logs, total)"""
    try:
        conn = sqlite3.connect(ACCESS_LOG_DB_PATH)
        conn.row_factory = sqlite3.Row

        where = "WHERE 1=1"
        params: list = []
        if request_type:
            where += " AND request_type = ?"
            params.append(request_type)
        if since:
            where += " AND timestamp >= ?"
            params.append(since)

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
        "metadata": {k: v for k, v in metadata.items() if k not in ("categories", "state")},
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
        "metadata": {k: v for k, v in metadata.items() if k not in ("categories", "state")},
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
    role: str  # "user" | "assistant" | "system"
    content: str


class AddMemoryRequest(BaseModel):
    messages: List[MemoryMessage]
    user_id: Optional[str] = None
    agent_id: Optional[str] = None
    run_id: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    categories: Optional[List[str]] = None
    state: Optional[str] = "active"
    infer: Optional[bool] = True  # True: AI 自动提取关键记忆（可能拆分为多条）; False: 原文整条存储
    auto_categorize: Optional[bool] = True  # True: 未手动选择标签时由 AI 自动分类


class SearchMemoryRequest(BaseModel):
    query: str
    user_id: Optional[str] = None
    agent_id: Optional[str] = None
    run_id: Optional[str] = None
    limit: Optional[int] = 10


class UpdateMemoryRequest(BaseModel):
    text: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    categories: Optional[List[str]] = None
    state: Optional[str] = None
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
    logger.info("Mem0 Dashboard 后端服务已关闭")


# ============ FastAPI 应用 ============

app = FastAPI(
    title="Mem0 Dashboard API",
    description="Mem0 记忆管理后端服务（Qdrant 本地文件模式）",
    version="1.1.0",
    lifespan=lifespan,
)

# CORS 配置（允许前端跨域访问）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


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


# ============ 辅助函数：获取所有记忆 ============

def _get_all_memories_raw() -> list:
    """获取所有记忆（原始 Qdrant 查询），返回格式化后的列表"""
    m = get_memory()
    try:
        collection_name = MEM0_CONFIG["vector_store"]["config"]["collection_name"]
        qdrant_client = m.vector_store.client
        records, _ = qdrant_client.scroll(
            collection_name=collection_name,
            limit=200,
            with_payload=True,
            with_vectors=False,
        )
        return [format_record(record) for record in records]
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
                    except Exception:
                        pass
        except Exception as e2:
            logger.warning(f"补写 metadata 失败: {e2}")

        return result
    except Exception as e:
        logger.error(f"添加记忆失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/v1/memories/")
async def get_memories(
    user_id: Optional[str] = Query(None),
    categories: Optional[str] = Query(None, description="逗号分隔的分类列表"),
    state: Optional[str] = Query(None, description="记忆状态: active/paused/archived/deleted"),
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
        raise HTTPException(status_code=500, detail=str(e))


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
        raise HTTPException(status_code=500, detail=str(e))


@app.put("/v1/memories/{memory_id}/")
async def update_memory(memory_id: str, request: UpdateMemoryRequest):
    """更新记忆（支持 text、metadata、categories、state 更新）"""
    try:
        m = get_memory()

        # 第一步：如果有文本更新，先通过 Mem0 SDK 更新（这会重写 Qdrant payload）
        if request.text:
            result = m.update(memory_id=memory_id, data=request.text)
        else:
            result = {"message": "metadata updated"}

        # 第二步：在文本更新完成后，再读取最新 payload 并修改 metadata
        # 这样可以确保不会被 m.update() 覆盖
        need_metadata_update = (
            request.categories is not None
            or request.state is not None
            or request.metadata is not None
            or request.auto_categorize
        )
        if need_metadata_update:
            try:
                collection_name = MEM0_CONFIG["vector_store"]["config"]["collection_name"]
                qdrant_client = m.vector_store.client

                # 读取 m.update() 之后的最新 payload
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
                        # 获取当前记忆文本（可能是更新后的新文本）
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

                    # 写回 Qdrant - 只更新 metadata 字段
                    qdrant_client.set_payload(
                        collection_name=collection_name,
                        payload={"metadata": current_metadata},
                        points=[memory_id],
                    )
                    # 标签有变更时记录快照
                    new_cats = current_metadata.get("categories", [])
                    _save_category_snapshot(memory_id, new_cats)
                    logger.info(f"已更新记忆 {memory_id} 的 metadata: state={current_metadata.get('state')}, categories={new_cats}")
            except Exception as meta_err:
                logger.warning(f"更新 metadata 失败: {meta_err}")

        return result
    except Exception as e:
        logger.error(f"更新记忆失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/v1/memories/{memory_id}/")
async def delete_memory_by_id(memory_id: str):
    """删除单条记忆"""
    try:
        m = get_memory()
        m.delete(memory_id=memory_id)
        return {"message": "记忆已删除"}
    except Exception as e:
        logger.error(f"删除记忆失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/v1/memories/")
async def delete_all_memories(user_id: Optional[str] = Query(None)):
    """删除用户的所有记忆"""
    try:
        m = get_memory()
        if user_id:
            m.delete_all(user_id=user_id)
            return {"message": f"用户 {user_id} 的所有记忆已删除"}
        else:
            # 无 user_id 时，复用 Mem0 内部的 Qdrant 客户端清空集合
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
                raise HTTPException(status_code=500, detail=str(qdrant_err))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"删除记忆失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============ 搜索接口 ============

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
        if isinstance(result, dict) and "results" in result:
            formatted = [format_mem0_result(item) for item in result["results"]]
            # 保留 score 字段
            for i, item in enumerate(result["results"]):
                if "score" in item:
                    formatted[i]["score"] = item["score"]
            return {"results": formatted}
        if isinstance(result, list):
            formatted = [format_mem0_result(item) for item in result]
            for i, item in enumerate(result):
                if "score" in item:
                    formatted[i]["score"] = item["score"]
            return {"results": formatted}
        return {"results": result}
    except Exception as e:
        logger.error(f"搜索记忆失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============ 历史记录接口 ============

@app.get("/v1/memories/history/{memory_id}/")
async def get_memory_history(memory_id: str):
    """获取记忆的修改历史（附加对应时间点的 categories 快照）"""
    try:
        m = get_memory()
        result = m.history(memory_id=memory_id)
        history_list = result if isinstance(result, list) else []

        # 获取该记忆的所有标签快照（按时间正序）
        snapshots = _get_category_snapshots(memory_id)

        # 获取当前记忆的 categories 作为兜底
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

        # 为每条历史记录匹配对应时间点的标签快照
        for item in history_list:
            if not isinstance(item, dict):
                continue
            item_time = item.get("created_at", "")
            if snapshots:
                # 找到 <= item_time 的最新快照
                matched_cats = None
                for snap in snapshots:
                    if snap["timestamp"] <= item_time:
                        matched_cats = snap["categories"]
                    else:
                        break
                # 如果没有匹配到（历史早于所有快照），用第一个快照或当前值
                if matched_cats is not None:
                    item["categories"] = matched_cats
                else:
                    # ADD 事件且有快照，用第一个快照（就是初始标签）
                    if item.get("event") == "ADD" and snapshots:
                        item["categories"] = snapshots[0]["categories"]
                    else:
                        item["categories"] = current_categories
            else:
                # 没有快照记录，兜底用当前标签
                item["categories"] = current_categories

        return history_list
    except Exception as e:
        logger.error(f"获取记忆历史失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============ 统计接口 ============

@app.get("/v1/stats/")
async def get_stats():
    """获取统计数据（分类分布、状态分布、每日趋势）"""
    try:
        memories = _get_all_memories_raw()

        # 基础统计
        total_memories = len(memories)
        user_set = set()
        for m in memories:
            uid = m.get("user_id")
            if uid:
                user_set.add(uid)
        total_users = len(user_set)

        # 分类分布
        category_distribution = {cat: 0 for cat in VALID_CATEGORIES}
        for m in memories:
            for cat in (m.get("categories") or []):
                if cat in category_distribution:
                    category_distribution[cat] += 1

        # 状态分布
        state_distribution = {s: 0 for s in VALID_STATES}
        for m in memories:
            s = m.get("state", "active")
            if s in state_distribution:
                state_distribution[s] += 1

        # 近 30 天每日趋势
        daily_trend = []
        today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        for i in range(29, -1, -1):
            day = today - timedelta(days=i)
            day_str = day.strftime("%Y-%m-%d")
            count = 0
            for m in memories:
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
            "state_distribution": state_distribution,
            "daily_trend": daily_trend,
        }
    except Exception as e:
        logger.error(f"获取统计数据失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


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
            if len(results) >= limit:
                break

        return {"results": results}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取关联记忆失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


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
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/v1/memories/{memory_id}/access-logs/")
async def get_memory_access_logs(
    memory_id: str,
    limit: int = Query(20, ge=1, le=100),
):
    """获取单条记忆的访问日志"""
    try:
        logs = _get_access_logs(memory_id=memory_id, limit=limit)
        return {"logs": logs}
    except Exception as e:
        logger.error(f"获取记忆访问日志失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============ 请求日志接口 ============

@app.get("/v1/request-logs/")
async def get_request_logs_api(
    request_type: Optional[str] = Query(None, description="请求类型筛选: 添加/搜索/删除/更新"),
    since: Optional[str] = Query(None, description="起始时间 ISO 格式，如 2026-03-27T10:00:00"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    """获取请求日志"""
    try:
        logs, total = _get_request_logs(request_type=request_type, since=since, limit=limit, offset=offset)
        return {"logs": logs, "total": total}
    except Exception as e:
        logger.error(f"获取请求日志失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/v1/request-logs/stats/")
async def get_request_logs_stats(
    since: Optional[str] = Query(None, description="起始时间 ISO 格式"),
):
    """获取请求日志统计（按类型分组计数 + 按类型每日请求数）"""
    try:
        conn = sqlite3.connect(ACCESS_LOG_DB_PATH)
        conn.row_factory = sqlite3.Row

        where = "WHERE 1=1"
        params: list = []
        if since:
            where += " AND timestamp >= ?"
            params.append(since)

        # 按类型分组
        type_rows = conn.execute(
            f"SELECT request_type, COUNT(*) as count FROM request_logs {where} GROUP BY request_type ORDER BY count DESC",
            params,
        ).fetchall()
        type_distribution = {row["request_type"]: row["count"] for row in type_rows}

        # 按类型+日期分组
        daily_type_rows = conn.execute(
            f"""SELECT DATE(timestamp) as date, request_type, COUNT(*) as count
               FROM request_logs {where}
               GROUP BY DATE(timestamp), request_type
               ORDER BY date""",
            params,
        ).fetchall()

        # 构建 { date: { type: count } } 的结构
        daily_type_map: Dict[str, Dict[str, int]] = {}
        all_types = set()
        for row in daily_type_rows:
            d = row["date"]
            t = row["request_type"]
            all_types.add(t)
            if d not in daily_type_map:
                daily_type_map[d] = {}
            daily_type_map[d][t] = row["count"]

        # 补全缺失日期，生成 [{date, 添加, 搜索, 删除, 更新, ...}] 格式
        daily_trend = []
        for i in range(13, -1, -1):
            d = (datetime.now() - timedelta(days=i)).strftime("%Y-%m-%d")
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
        }
    except Exception as e:
        logger.error(f"获取请求日志统计失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============ 启动入口 ============

if __name__ == "__main__":
    # 默认监听 8080 端口，与前端 .env.local 中配置一致
    port = int(os.environ.get("MEM0_PORT", 8080))
    logger.info(f"启动 Mem0 API 服务，端口: {port}")
    uvicorn.run(
        "server:app",
        host="0.0.0.0",
        port=port,
        reload=True,
        reload_includes=["*.py"],  # 只监控 .py 文件变化
        reload_excludes=["qdrant_data/**", "*.log"],  # 排除 Qdrant 数据目录和日志文件
        log_level="info",
    )
