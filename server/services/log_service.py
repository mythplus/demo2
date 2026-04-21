"""
日志服务 — PostgreSQL 访问日志、请求日志、修改历史、批量写入队列
"""

import json
import logging
import time
import threading
import queue as _queue
from collections import OrderedDict
from typing import Optional
from datetime import datetime, timezone

import psycopg2
import psycopg2.extras
import psycopg2.pool

from server.config import (
    DATABASE_URL, IS_PRODUCTION,
    ACCESS_DEDUP_SECONDS, ACCESS_DEDUP_MAX_ENTRIES,
)

logger = logging.getLogger(__name__)

# ============ PostgreSQL 连接池 ============
_pg_pool: Optional[psycopg2.pool.ThreadedConnectionPool] = None
_pool_lock = threading.Lock()


def _get_pool() -> psycopg2.pool.ThreadedConnectionPool:
    """获取 PostgreSQL 连接池（单例，线程安全）"""
    global _pg_pool
    if _pg_pool is not None:
        return _pg_pool
    with _pool_lock:
        if _pg_pool is None:
            _pg_pool = psycopg2.pool.ThreadedConnectionPool(
                minconn=2,
                maxconn=20,
                dsn=DATABASE_URL,
            )
            logger.info("PostgreSQL 日志连接池已创建")
    return _pg_pool


def _get_db_conn():
    """从连接池获取一个 PostgreSQL 连接"""
    return _get_pool().getconn()


def _release_conn(conn):
    """将连接归还连接池"""
    try:
        _get_pool().putconn(conn)
    except Exception:
        pass


# ============ 异步日志批量写入队列 ============
_log_queue: _queue.Queue = _queue.Queue(maxsize=10000)
_LOG_FLUSH_INTERVAL = 5  # 每 5 秒 flush 一次
_LOG_FLUSH_BATCH_SIZE = 100  # 每批最多写入 100 条
_log_writer_thread: Optional[threading.Thread] = None
_log_writer_running = False
_dropped_log_count = 0
# B2 P1-8：追踪序列化写入失败（穷尽重试后仍失败的批次）和丢失的记录数，
# 方便 /health 或 /stats 接口暴露错误暲线，不再静默吞掉写入异常。
_flush_failed_batches = 0
_flush_failed_entries = 0
_last_flush_error: Optional[str] = None
_metrics_lock = threading.Lock()


def get_log_writer_metrics() -> dict:
    """日志写入线程运行指标快照，供 /health 等接口暴露。

    Fields:
        queue_size: 当前等待写入的日志条数
        dropped: 因队列满丢弃的日志条数（自进程启动以来累计）
        failed_batches: 重试后仍写入失败的批次数
        failed_entries: 因写入失败丢失的记录数（failed_batches 所包含的条数总和）
        last_error: 最新一次写入失败的错误摘要，无则为 None
        running: 后台线程是否存活
    """
    with _metrics_lock:
        return {
            "queue_size": _log_queue.qsize(),
            "dropped": _dropped_log_count,
            "failed_batches": _flush_failed_batches,
            "failed_entries": _flush_failed_entries,
            "last_error": _last_flush_error,
            "running": bool(_log_writer_running and _log_writer_thread and _log_writer_thread.is_alive()),
        }


def _record_flush_failure(batch_size: int, err: Exception) -> None:
    """记录一次死信 flush 失败（在所有重试都耗尽后调用）。"""
    global _flush_failed_batches, _flush_failed_entries, _last_flush_error
    with _metrics_lock:
        _flush_failed_batches += 1
        _flush_failed_entries += batch_size
        _last_flush_error = f"{type(err).__name__}: {err}"[:500]


def _log_writer_loop():
    """后台线程：从队列中批量取出日志并写入 PostgreSQL"""
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


_FLUSH_MAX_RETRIES = 3
_FLUSH_RETRY_BASE_DELAY = 0.5


def _flush_log_batch(batch: list, raise_on_failure: bool = False):
    """将一批日志写入 PostgreSQL（单次事务，带指数退避重试）"""
    conn = None
    for attempt in range(1, _FLUSH_MAX_RETRIES + 1):
        try:
            conn = _get_db_conn()
            with conn.cursor() as cur:
                for item in batch:
                    cur.execute(item["sql"], item["params"])
            conn.commit()
            return
        except psycopg2.OperationalError as e:
            try:
                if conn is not None:
                    conn.rollback()
            except Exception:
                pass
            if attempt < _FLUSH_MAX_RETRIES:
                delay = _FLUSH_RETRY_BASE_DELAY * (2 ** (attempt - 1))
                logger.warning(f"PostgreSQL 写入失败，第 {attempt} 次重试（{delay:.1f}s 后）: {e}")
                time.sleep(delay)
                # 归还损坏连接，重新获取
                if conn is not None:
                    try:
                        _get_pool().putconn(conn, close=True)
                    except Exception:
                        pass
                    conn = None
            else:
                logger.error(
                    f"批量写入日志失败 ({len(batch)} 条，第 {attempt} 次尝试)：{e}",
                    exc_info=True,
                )
                _record_flush_failure(len(batch), e)
                if raise_on_failure:
                    raise
                return
        except Exception as e:
            try:
                if conn is not None:
                    conn.rollback()
            except Exception:
                pass
            logger.error(f"批量写入日志失败 ({len(batch)} 条): {e}", exc_info=True)
            _record_flush_failure(len(batch), e)
            if raise_on_failure:
                raise
            return
        finally:
            if conn is not None:
                _release_conn(conn)
                conn = None


def _enqueue_log(table: str, sql: str, params: tuple):
    """将一条日志投递到写入队列（非阻塞）"""
    global _dropped_log_count
    try:
        _log_queue.put_nowait({"table": table, "sql": sql, "params": params})
    except _queue.Full:
        _dropped_log_count += 1
        logger.warning(f"日志队列已满，累计丢弃 {_dropped_log_count} 条日志")


def start_log_writer():
    """启动后台日志写入线程"""
    global _log_writer_thread, _log_writer_running
    if _log_writer_thread is not None and _log_writer_thread.is_alive():
        return
    _log_writer_running = True
    _log_writer_thread = threading.Thread(target=_log_writer_loop, daemon=True, name="log-writer")
    _log_writer_thread.start()
    logger.info("后台日志写入线程已启动")


# ============ 日志自动清理（保留 30 天） ============

_LOG_RETENTION_DAYS = 30
_cleanup_thread: Optional[threading.Thread] = None
_cleanup_running = False
_cleanup_stop_event = threading.Event()


def cleanup_old_logs():
    """清理超过 _LOG_RETENTION_DAYS 天的日志记录（所有日志表统一清理）"""
    conn = None
    try:
        from datetime import timedelta
        cutoff = (datetime.now(timezone.utc) - timedelta(days=_LOG_RETENTION_DAYS)).isoformat()
        conn = _get_db_conn()

        tables_and_cols = [
            ("request_logs", "timestamp"),
            ("access_logs", "timestamp"),
            ("memory_change_logs", "timestamp"),
            ("category_snapshots", "timestamp"),
        ]

        total_deleted = 0
        with conn.cursor() as cur:
            for table, col in tables_and_cols:
                try:
                    cur.execute(f"DELETE FROM {table} WHERE {col} < %s", (cutoff,))
                    deleted = cur.rowcount
                    total_deleted += deleted
                    if deleted > 0:
                        logger.info(f"日志清理: {table} 删除 {deleted} 条（>{_LOG_RETENTION_DAYS}天）")
                except Exception as e:
                    logger.warning(f"清理 {table} 失败: {e}")

        conn.commit()

        if total_deleted > 0:
            logger.info(f"日志清理完成，共删除 {total_deleted} 条过期记录")
        else:
            logger.info("日志清理：无过期记录")
    except Exception as e:
        logger.warning(f"日志清理任务异常: {e}")
        if conn is not None:
            try:
                conn.rollback()
            except Exception:
                pass
    finally:
        if conn is not None:
            _release_conn(conn)


def _daily_cleanup_loop():
    """后台线程：每天执行一次日志清理"""
    while _cleanup_running:
        stopped = _cleanup_stop_event.wait(timeout=24 * 3600)
        if stopped or not _cleanup_running:
            return
        cleanup_old_logs()


def start_log_cleanup():
    """启动日志清理：立即清理一次 + 启动每日定时清理线程"""
    global _cleanup_thread, _cleanup_running
    cleanup_old_logs()
    if _cleanup_thread is None or not _cleanup_thread.is_alive():
        _cleanup_running = True
        _cleanup_stop_event.clear()
        _cleanup_thread = threading.Thread(target=_daily_cleanup_loop, daemon=True, name="log-cleanup")
        _cleanup_thread.start()
        logger.info(f"日志自动清理已启用（保留 {_LOG_RETENTION_DAYS} 天，每日执行）")


def stop_log_writer():
    """停止后台日志写入线程，并 flush 剩余日志"""
    global _log_writer_running, _cleanup_running
    _log_writer_running = False
    _cleanup_running = False
    _cleanup_stop_event.set()
    if _log_writer_thread is not None:
        _log_writer_thread.join(timeout=10)
    if _cleanup_thread is not None:
        _cleanup_thread.join(timeout=5)
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
    """初始化访问日志和请求日志相关表（PostgreSQL）

    B2 P0-2 整改：
    - 开发/测试环境：仍走 CREATE TABLE IF NOT EXISTS 快速起服。
    - 生产环境（MEM0_ENV=production）：**禁止**自动建表，改为“schema 健康检查”，
      确保必要的日志表（access_logs / request_logs / memory_change_logs / category_snapshots）
      已由 `alembic upgrade head` 建立，避免运行时绕过迁移干预 schema。
    """
    required_tables = ("access_logs", "request_logs", "memory_change_logs", "category_snapshots")

    conn = None
    try:
        conn = _get_db_conn()

        if IS_PRODUCTION:
            with conn.cursor() as cur:
                cur.execute(
                    """SELECT table_name FROM information_schema.tables
                       WHERE table_schema = current_schema() AND table_name = ANY(%s)""",
                    (list(required_tables),),
                )
                existing = {row[0] for row in cur.fetchall()}
            missing = [name for name in required_tables if name not in existing]
            if missing:
                raise RuntimeError(
                    "生产环境日志表缺失: "
                    + ", ".join(missing)
                    + "。请先执行 `alembic upgrade head` 再启动服务。"
                )
            logger.info("生产环境：日志表 schema 健康检查通过，迁移由流水线管理（alembic upgrade head）")
            return

        # 开发/测试：裸建表 + 建索引，保持快速迭代体验
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS access_logs (
                    id SERIAL PRIMARY KEY,
                    memory_id TEXT NOT NULL,
                    action TEXT NOT NULL,
                    memory_preview TEXT,
                    timestamp TEXT NOT NULL DEFAULT (NOW() AT TIME ZONE 'UTC')::TEXT
                )
            """)
            cur.execute("CREATE INDEX IF NOT EXISTS idx_access_logs_memory_id ON access_logs(memory_id)")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_access_logs_timestamp ON access_logs(timestamp)")

            cur.execute("""
                CREATE TABLE IF NOT EXISTS request_logs (
                    id SERIAL PRIMARY KEY,
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
            cur.execute("CREATE INDEX IF NOT EXISTS idx_request_logs_timestamp ON request_logs(timestamp)")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_request_logs_type ON request_logs(request_type)")

            cur.execute("""
                CREATE TABLE IF NOT EXISTS memory_change_logs (
                    id SERIAL PRIMARY KEY,
                    memory_id TEXT NOT NULL,
                    event TEXT NOT NULL,
                    old_memory TEXT,
                    new_memory TEXT,
                    categories TEXT NOT NULL DEFAULT '[]',
                    old_categories TEXT NOT NULL DEFAULT '[]',
                    timestamp TEXT NOT NULL
                )
            """)
            cur.execute("CREATE INDEX IF NOT EXISTS idx_mcl_memory_id ON memory_change_logs(memory_id)")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_mcl_timestamp ON memory_change_logs(timestamp)")

            cur.execute("""
                CREATE TABLE IF NOT EXISTS category_snapshots (
                    id SERIAL PRIMARY KEY,
                    memory_id TEXT NOT NULL,
                    categories TEXT NOT NULL DEFAULT '[]',
                    timestamp TEXT NOT NULL
                )
            """)
            cur.execute("CREATE INDEX IF NOT EXISTS idx_cat_snap_memory_id ON category_snapshots(memory_id)")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_cat_snap_timestamp ON category_snapshots(timestamp)")

        conn.commit()
    finally:
        if conn is not None:
            _release_conn(conn)


# ============ 访问日志 ============

def save_category_snapshot(memory_id: str, categories: list, timestamp: str = "", strict: bool = False):
    """记录一次标签快照（默认异步队列投递；strict=True 时同步写入并抛出异常）"""
    try:
        ts = timestamp or datetime.now(timezone.utc).isoformat()
        cats_json = json.dumps(categories, ensure_ascii=False)
        if strict:
            _flush_log_batch([
                {
                    "table": "category_snapshots",
                    "sql": "INSERT INTO category_snapshots (memory_id, categories, timestamp) VALUES (%s, %s, %s)",
                    "params": (memory_id, cats_json, ts),
                }
            ], raise_on_failure=True)
            return

        _enqueue_log(
            "category_snapshots",
            "INSERT INTO category_snapshots (memory_id, categories, timestamp) VALUES (%s, %s, %s)",
            (memory_id, cats_json, ts),
        )
    except Exception as e:
        logger.warning(f"记录标签快照失败: {e}")
        if strict:
            raise


def save_change_log(memory_id: str, event: str, new_memory: str,
                    categories: list, old_memory: str = None,
                    old_categories: list = None, strict: bool = False,
                    timestamp: str = ""):
    """记录一条修改历史（默认异步队列投递；strict=True 时同步写入并抛出异常）"""
    try:
        ts = timestamp or datetime.now(timezone.utc).isoformat()
        cats_json = json.dumps(categories, ensure_ascii=False)
        old_cats_json = json.dumps(old_categories or [], ensure_ascii=False)
        sql = """INSERT INTO memory_change_logs
               (memory_id, event, old_memory, new_memory, categories, old_categories, timestamp)
               VALUES (%s, %s, %s, %s, %s, %s, %s)"""
        params = (memory_id, event, old_memory or "", new_memory, cats_json, old_cats_json, ts)

        if strict:
            _flush_log_batch([
                {
                    "table": "memory_change_logs",
                    "sql": sql,
                    "params": params,
                }
            ], raise_on_failure=True)
            return

        _enqueue_log("memory_change_logs", sql, params)
    except Exception as e:
        logger.warning(f"记录修改历史失败: {e}")
        if strict:
            raise


def save_memory_audit_snapshot(memory_id: str, event: str, new_memory: str,
                              categories: list, old_memory: str = None,
                              old_categories: list = None, timestamp: str = ""):
    """同步记录标签快照和修改历史，任一失败即抛错，保证审计链路原子性。"""
    ts = timestamp or datetime.now(timezone.utc).isoformat()
    cats_json = json.dumps(categories, ensure_ascii=False)
    old_cats_json = json.dumps(old_categories or [], ensure_ascii=False)
    _flush_log_batch([
        {
            "table": "category_snapshots",
            "sql": "INSERT INTO category_snapshots (memory_id, categories, timestamp) VALUES (%s, %s, %s)",
            "params": (memory_id, cats_json, ts),
        },
        {
            "table": "memory_change_logs",
            "sql": """INSERT INTO memory_change_logs
               (memory_id, event, old_memory, new_memory, categories, old_categories, timestamp)
               VALUES (%s, %s, %s, %s, %s, %s, %s)""",
            "params": (memory_id, event, old_memory or "", new_memory, cats_json, old_cats_json, ts),
        },
    ], raise_on_failure=True)


def get_change_logs(memory_id: str) -> list:
    """获取某条记忆的自建修改历史（时间正序）"""
    conn = None
    try:
        conn = _get_db_conn()
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """SELECT event, old_memory, new_memory, categories, old_categories, timestamp
                   FROM memory_change_logs WHERE memory_id = %s ORDER BY timestamp ASC""",
                (memory_id,),
            )
            rows = cur.fetchall()
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
    finally:
        if conn is not None:
            _release_conn(conn)


# 访问日志去重缓存（B2 P1-3：换为 OrderedDict 方便按插入顺序清理，并修正“先写后清理”导致的上限失控问题）
_access_dedup_cache: "OrderedDict[str, float]" = OrderedDict()
_access_dedup_lock = threading.Lock()
# 逻辑上绑定到 config.ACCESS_DEDUP_SECONDS，保留此别名兼容旧测试导入。
_ACCESS_DEDUP_SECONDS = ACCESS_DEDUP_SECONDS


def _purge_expired_dedup(now: float) -> None:
    """按插入顺序清除已过期的 dedup 条目（需在持锁环境调用）。"""
    cutoff = now - _ACCESS_DEDUP_SECONDS
    while _access_dedup_cache:
        _, ts = next(iter(_access_dedup_cache.items()))
        if ts >= cutoff:
            break
        _access_dedup_cache.popitem(last=False)


def log_access(memory_id: str, action: str, memory_preview: str = ""):
    """记录一条访问日志（异步队列投递，非阻塞，短时间内去重）"""
    try:
        now = time.time()
        dedup_key = f"{memory_id}:{action}"

        with _access_dedup_lock:
            last_time = _access_dedup_cache.get(dedup_key)
            if last_time is not None and (now - last_time) < _ACCESS_DEDUP_SECONDS:
                # 命中去重窗口：更新顺序为最近使用后直接返回，不写入新日志
                _access_dedup_cache.move_to_end(dedup_key)
                return

            # P1-3 修正：先清理再插入，并以“插入顺序”代替 O(n) 遭历
            _access_dedup_cache[dedup_key] = now
            _access_dedup_cache.move_to_end(dedup_key)

            if len(_access_dedup_cache) > ACCESS_DEDUP_MAX_ENTRIES:
                _purge_expired_dedup(now)
                # 若清理后仍超过硬上限（代表在去重窗口内出现高并发独立 key），强制删除最早的条目
                while len(_access_dedup_cache) > ACCESS_DEDUP_MAX_ENTRIES:
                    _access_dedup_cache.popitem(last=False)

        _enqueue_log(
            "access_logs",
            "INSERT INTO access_logs (memory_id, action, memory_preview, timestamp) VALUES (%s, %s, %s, %s)",
            (memory_id, action, memory_preview[:100] if memory_preview else "", datetime.now(timezone.utc).isoformat()),
        )
    except Exception as e:
        logger.warning(f"记录访问日志失败: {e}")


def get_access_logs(memory_id: str = None, limit: int = 50, offset: int = 0) -> list:
    """查询访问日志"""
    conn = None
    try:
        conn = _get_db_conn()
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            if memory_id:
                cur.execute(
                    "SELECT * FROM access_logs WHERE memory_id = %s ORDER BY timestamp DESC LIMIT %s OFFSET %s",
                    (memory_id, limit, offset),
                )
            else:
                cur.execute(
                    "SELECT * FROM access_logs ORDER BY timestamp DESC LIMIT %s OFFSET %s",
                    (limit, offset),
                )
            return [dict(row) for row in cur.fetchall()]
    except Exception as e:
        logger.warning(f"查询访问日志失败: {e}")
        return []
    finally:
        if conn is not None:
            _release_conn(conn)


# ============ 请求日志工具函数 ============

_PATH_TYPE_MAP = {
    ("POST", "/v1/memories/"): "添加",
    ("POST", "/v1/memories/search/"): "搜索",
    ("DELETE",): "删除",
    ("PUT",): "更新",
    ("GET", "/v1/memories/"): "获取全部",
    ("GET", "/v1/stats/"): "统计",
}


def classify_request(method: str, path: str) -> str:
    """根据 HTTP 方法和路径推断请求类型"""
    if method == "POST" and "/search" in path:
        return "搜索"
    if method == "POST" and "/playground" in path:
        return "对话"
    if method == "POST" and "/memories" in path:
        return "添加"
    if method == "PUT":
        return "更新"
    if method == "DELETE":
        return "删除"
    return method


def extract_user_from_request(method: str, path: str, body: str) -> str:
    """尝试从请求中提取 user_id"""
    if "user_id=" in path:
        for part in path.split("?")[1].split("&") if "?" in path else []:
            if part.startswith("user_id="):
                return part.split("=", 1)[1]
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
        if "?" in path:
            return path.split("?", 1)[1][:200]
        return ""
    try:
        data = json.loads(body)
        if isinstance(data, dict):
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
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)""",
            (timestamp, method, path, request_type, user_id, status_code,
             round(latency_ms, 2), payload_summary[:500], error[:500]),
        )
    except Exception as e:
        logger.warning(f"记录请求日志失败: {e}")


def get_request_logs(request_type: str = None, since: str = None, until: str = None, limit: int = 50, offset: int = 0) -> tuple:
    """查询请求日志，返回 (logs, total)"""
    conn = None
    try:
        conn = _get_db_conn()

        where = "WHERE 1=1"
        params: list = []
        if request_type:
            where += " AND request_type = %s"
            params.append(request_type)
        if since:
            where += " AND timestamp >= %s"
            params.append(since)
        if until:
            where += " AND timestamp <= %s"
            params.append(until)

        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(f"SELECT COUNT(*) FROM request_logs {where}", params)
            total = cur.fetchone()["count"]

            cur.execute(
                f"SELECT * FROM request_logs {where} ORDER BY timestamp DESC LIMIT %s OFFSET %s",
                params + [limit, offset],
            )
            rows = [dict(row) for row in cur.fetchall()]
        return rows, total
    except Exception as e:
        logger.warning(f"查询请求日志失败: {e}")
        return [], 0
    finally:
        if conn is not None:
            _release_conn(conn)
