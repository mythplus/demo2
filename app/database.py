"""
Mem0 Dashboard 后端 - 数据库模块（SQLite 日志存储）
"""
import os
import json
import time
import sqlite3
import threading
import logging
import queue as _queue
from typing import Optional
from datetime import datetime

logger = logging.getLogger(__name__)

# ============ 数据库路径 ============
ACCESS_LOG_DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "access_logs.db")

# ============ 线程本地连接池 ============
_thread_local = threading.local()


def _get_db_conn():
    """获取 SQLite 连接（线程本地复用）"""
    conn = getattr(_thread_local, "db_conn", None)
    if conn is not None:
        try:
            conn.execute("SELECT 1")
            return conn
        except Exception:
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
_LOG_FLUSH_INTERVAL = 5
_LOG_FLUSH_BATCH_SIZE = 100
_log_writer_thread: Optional[threading.Thread] = None
_log_writer_running = False


def _log_writer_loop():
    """后台线程：从队列中批量取出日志并写入 SQLite"""
    global _log_writer_running
    while _log_writer_running:
        batch: list = []
        try:
            try:
                first = _log_queue.get(timeout=_LOG_FLUSH_INTERVAL)
                batch.append(first)
            except _queue.Empty:
                continue

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
            conn.execute(item["sql"], item["params"])
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
    remaining: list = []
    while not _log_queue.empty():
        try:
            remaining.append(_log_queue.get_nowait())
        except _queue.Empty:
            break
    if remaining:
        _flush_log_batch(remaining)
        logger.info(f"已 flush 剩余 {len(remaining)} 条日志")


def init_db():
    """初始化数据库（init_access_log_db 的别名，供入口文件统一调用）"""
    init_access_log_db()


def init_access_log_db():
    """初始化访问日志和请求日志数据库"""
    conn = _get_db_conn()
    conn.execute("PRAGMA journal_mode=WAL")

    conn.execute("""
        CREATE TABLE IF NOT EXISTS access_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            memory_id TEXT NOT NULL,
            action TEXT NOT NULL,
            memory_preview TEXT,
            tenant_id TEXT NOT NULL DEFAULT 'default',
            timestamp TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_access_logs_memory_id ON access_logs(memory_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_access_logs_timestamp ON access_logs(timestamp)")
    # 兼容已存在的表：添加 tenant_id 列
    try:
        conn.execute("ALTER TABLE access_logs ADD COLUMN tenant_id TEXT NOT NULL DEFAULT 'default'")
    except Exception:
        pass

    conn.execute("""
        CREATE TABLE IF NOT EXISTS request_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            method TEXT NOT NULL,
            path TEXT NOT NULL,
            request_type TEXT,
            user_id TEXT,
            tenant_id TEXT NOT NULL DEFAULT 'default',
            status_code INTEGER,
            latency_ms REAL,
            payload_summary TEXT,
            error TEXT
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_request_logs_timestamp ON request_logs(timestamp)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_request_logs_type ON request_logs(request_type)")
    try:
        conn.execute("ALTER TABLE request_logs ADD COLUMN tenant_id TEXT NOT NULL DEFAULT 'default'")
    except Exception:
        pass

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
    try:
        conn.execute("ALTER TABLE memory_change_logs ADD COLUMN old_categories TEXT NOT NULL DEFAULT '[]'")
    except Exception:
        pass
    conn.execute("CREATE INDEX IF NOT EXISTS idx_mcl_memory_id ON memory_change_logs(memory_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_mcl_timestamp ON memory_change_logs(timestamp)")

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


# ============ 日志记录函数 ============

def save_category_snapshot(memory_id: str, categories: list, timestamp: str = ""):
    """记录一次标签快照"""
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
    """记录一条修改历史"""
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
    """获取某条记忆的自建修改历史"""
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
    """记录一条访问日志"""
    try:
        _enqueue_log(
            "access_logs",
            "INSERT INTO access_logs (memory_id, action, memory_preview, timestamp) VALUES (?, ?, ?, ?)",
            (memory_id, action, memory_preview[:100] if memory_preview else "", datetime.now().isoformat()),
        )
    except Exception as e:
        logger.warning(f"记录访问日志失败: {e}")


def get_access_logs(memory_id: str = None, limit: int = 50, offset: int = 0) -> tuple:
    """查询访问日志，返回 (logs, total)"""
    try:
        conn = _get_db_conn()
        conn.row_factory = sqlite3.Row
        if memory_id:
            total = conn.execute(
                "SELECT COUNT(*) FROM access_logs WHERE memory_id = ?", (memory_id,)
            ).fetchone()[0]
            rows = conn.execute(
                "SELECT * FROM access_logs WHERE memory_id = ? ORDER BY timestamp DESC LIMIT ? OFFSET ?",
                (memory_id, limit, offset),
            ).fetchall()
        else:
            total = conn.execute("SELECT COUNT(*) FROM access_logs").fetchone()[0]
            rows = conn.execute(
                "SELECT * FROM access_logs ORDER BY timestamp DESC LIMIT ? OFFSET ?",
                (limit, offset),
            ).fetchall()
        return [dict(row) for row in rows], total
    except Exception as e:
        logger.warning(f"查询访问日志失败: {e}")
        return [], 0


def log_request(method: str, path: str, request_type: str,
                status_code: int, latency_ms: float,
                timestamp: str = "", user_id: str = "",
                payload_summary: str = "", error: str = "",
                tenant_id: str = "default"):
    """记录一条请求日志"""
    ts = timestamp or datetime.now().isoformat()
    try:
        _enqueue_log(
            "request_logs",
            """INSERT INTO request_logs
               (timestamp, method, path, request_type, user_id, tenant_id, status_code, latency_ms, payload_summary, error)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (ts, method, path, request_type, user_id, tenant_id, status_code,
             round(latency_ms, 2), payload_summary[:500], error[:500]),
        )
    except Exception as e:
        logger.warning(f"记录请求日志失败: {e}")


async def log_request_async(method: str, path: str, request_type: str,
                            status_code: int, latency_ms: float,
                            error: str = "", user_id: str = "",
                            payload_summary: str = "",
                            tenant_id: str = "default"):
    """异步记录请求日志（供 FastAPI 中间件调用，自动填充 timestamp）"""
    log_request(
        method=method,
        path=path,
        request_type=request_type,
        status_code=status_code,
        latency_ms=latency_ms,
        timestamp=datetime.now().isoformat(),
        user_id=user_id,
        payload_summary=payload_summary,
        error=error or "",
        tenant_id=tenant_id,
    )


def get_request_logs(request_type: str = None, since: str = None, until: str = None,
                     limit: int = 50, offset: int = 0) -> tuple:
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

        total = conn.execute(f"SELECT COUNT(*) FROM request_logs {where}", params).fetchone()[0]

        rows = conn.execute(
            f"SELECT * FROM request_logs {where} ORDER BY timestamp DESC LIMIT ? OFFSET ?",
            params + [limit, offset],
        ).fetchall()
        return [dict(row) for row in rows], total
    except Exception as e:
        logger.warning(f"查询请求日志失败: {e}")
        return [], 0
