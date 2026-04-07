"""
日志服务 — SQLite 访问日志、请求日志、修改历史、批量写入队列
"""

import json
import logging
import sqlite3
import threading
import queue as _queue
from typing import Optional
from datetime import datetime

from server.config import ACCESS_LOG_DB_PATH

logger = logging.getLogger(__name__)

# ============ SQLite 线程本地连接池 ============
_thread_local = threading.local()


def _get_db_conn():
    """获取 SQLite 连接（线程本地复用，自动设置 busy_timeout 和 WAL 模式）"""
    conn = getattr(_thread_local, "db_conn", None)
    if conn is not None:
        try:
            conn.execute("SELECT 1")  # 检测连接是否仍然有效
            return conn
        except Exception:
            # 连接已失效，重新创建
            try:
                conn.close()
            except Exception:
                pass
            _thread_local.db_conn = None

    conn = sqlite3.connect(ACCESS_LOG_DB_PATH, check_same_thread=False)
    conn.execute("PRAGMA busy_timeout=5000")
    conn.execute("PRAGMA journal_mode=WAL")
    _thread_local.db_conn = conn
    return conn


# ============ 异步日志批量写入队列 ============
_log_queue: _queue.Queue = _queue.Queue(maxsize=10000)
_LOG_FLUSH_INTERVAL = 5  # 每 5 秒 flush 一次
_LOG_FLUSH_BATCH_SIZE = 100  # 每批最多写入 100 条
_log_writer_thread: Optional[threading.Thread] = None
_log_writer_running = False


def _log_writer_loop():
    """后台线程：从队列中批量取出日志并写入 SQLite"""
    global _log_writer_running
    while _log_writer_running:
        batch: list = []
        try:
            # 阻塞等待第一条，最多等 _LOG_FLUSH_INTERVAL 秒
            try:
                first = _log_queue.get(timeout=_LOG_FLUSH_INTERVAL)
                batch.append(first)
            except _queue.Empty:
                continue

            # 非阻塞地尽量多取
            while len(batch) < _LOG_FLUSH_BATCH_SIZE:
                try:
                    batch.append(_log_queue.get_nowait())
                except _queue.Empty:
                    break

            if batch:
                _flush_log_batch(batch)
        except Exception as e:
            logger.warning(f"日志写入线程异常: {e}")


def _flush_log_batch(batch: list):
    """将一批日志写入 SQLite（单次事务）"""
    try:
        conn = _get_db_conn()
        for item in batch:
            table = item["table"]
            sql = item["sql"]
            params = item["params"]
            conn.execute(sql, params)
        conn.commit()
    except Exception as e:
        logger.warning(f"批量写入日志失败 ({len(batch)} 条): {e}")


def _enqueue_log(table: str, sql: str, params: tuple):
    """将一条日志投递到写入队列（非阻塞）"""
    try:
        _log_queue.put_nowait({"table": table, "sql": sql, "params": params})
    except _queue.Full:
        logger.warning("日志队列已满，丢弃一条日志")


def start_log_writer():
    """启动后台日志写入线程"""
    global _log_writer_thread, _log_writer_running
    if _log_writer_thread is not None and _log_writer_thread.is_alive():
        return
    _log_writer_running = True
    _log_writer_thread = threading.Thread(target=_log_writer_loop, daemon=True, name="log-writer")
    _log_writer_thread.start()
    logger.info("后台日志写入线程已启动")


def stop_log_writer():
    """停止后台日志写入线程，并 flush 剩余日志"""
    global _log_writer_running
    _log_writer_running = False
    if _log_writer_thread is not None:
        _log_writer_thread.join(timeout=10)
    # flush 队列中剩余的日志
    remaining: list = []
    while not _log_queue.empty():
        try:
            remaining.append(_log_queue.get_nowait())
        except _queue.Empty:
            break
    if remaining:
        _flush_log_batch(remaining)
        logger.info(f"已 flush 剩余 {len(remaining)} 条日志")


def init_access_log_db():
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


# ============ 访问日志 ============

def save_category_snapshot(memory_id: str, categories: list, timestamp: str = ""):
    """记录一次标签快照（异步队列投递，非阻塞）"""
    try:
        ts = timestamp or datetime.now().isoformat()
        cats_json = json.dumps(categories, ensure_ascii=False)
        _enqueue_log(
            "category_snapshots",
            "INSERT INTO category_snapshots (memory_id, categories, timestamp) VALUES (?, ?, ?)",
            (memory_id, cats_json, ts),
        )
    except Exception as e:
        logger.warning(f"记录标签快照失败: {e}")


def save_change_log(memory_id: str, event: str, new_memory: str,
                    categories: list, old_memory: str = None,
                    old_categories: list = None):
    """记录一条修改历史（异步队列投递，非阻塞）"""
    try:
        ts = datetime.now().isoformat()
        cats_json = json.dumps(categories, ensure_ascii=False)
        old_cats_json = json.dumps(old_categories or [], ensure_ascii=False)
        _enqueue_log(
            "memory_change_logs",
            """INSERT INTO memory_change_logs
               (memory_id, event, old_memory, new_memory, categories, old_categories, timestamp)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (memory_id, event, old_memory or "", new_memory, cats_json, old_cats_json, ts),
        )
    except Exception as e:
        logger.warning(f"记录修改历史失败: {e}")


def get_change_logs(memory_id: str) -> list:
    """获取某条记忆的自建修改历史（时间正序）"""
    try:
        conn = _get_db_conn()
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            """SELECT event, old_memory, new_memory, categories, old_categories, timestamp
               FROM memory_change_logs WHERE memory_id = ? ORDER BY timestamp ASC""",
            (memory_id,),
        ).fetchall()
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


def log_access(memory_id: str, action: str, memory_preview: str = ""):
    """记录一条访问日志（异步队列投递，非阻塞）"""
    try:
        _enqueue_log(
            "access_logs",
            "INSERT INTO access_logs (memory_id, action, memory_preview, timestamp) VALUES (?, ?, ?, ?)",
            (memory_id, action, memory_preview[:100] if memory_preview else "", datetime.now().isoformat()),
        )
    except Exception as e:
        logger.warning(f"记录访问日志失败: {e}")


def get_access_logs(memory_id: str = None, limit: int = 50, offset: int = 0) -> list:
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


def classify_request(method: str, path: str) -> str:
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


def extract_user_from_request(method: str, path: str, body: str) -> str:
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


def summarize_payload(method: str, path: str, body: str) -> str:
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


def log_request(timestamp: str, method: str, path: str, request_type: str,
                user_id: str, status_code: int, latency_ms: float,
                payload_summary: str, error: str = ""):
    """记录一条请求日志（异步队列投递，非阻塞）"""
    try:
        _enqueue_log(
            "request_logs",
            """INSERT INTO request_logs
               (timestamp, method, path, request_type, user_id, status_code, latency_ms, payload_summary, error)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (timestamp, method, path, request_type, user_id, status_code,
             round(latency_ms, 2), payload_summary[:500], error[:500]),
        )
    except Exception as e:
        logger.warning(f"记录请求日志失败: {e}")


def get_request_logs(request_type: str = None, since: str = None, until: str = None, limit: int = 50, offset: int = 0) -> tuple:
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
        return [dict(row) for row in rows], total
    except Exception as e:
        logger.warning(f"查询请求日志失败: {e}")
        return [], 0
