"""
速率限制中间件 — 基于 SQLite 的跨 Worker 共享滑动窗口

多 Worker（多进程）模式下，每个 Worker 共享同一个 SQLite 数据库文件，
通过 WAL 模式 + busy_timeout 实现并发安全的限流计数。
"""

import time
import sqlite3
import logging
import threading
from collections import defaultdict
from typing import Deque, Dict
from collections import deque
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from server.config import RATE_LIMIT_DB_PATH

logger = logging.getLogger(__name__)


class RateLimitMiddleware(BaseHTTPMiddleware):
    """基于 SQLite 共享存储的滑动窗口速率限制中间件（支持多 Worker）"""

    def __init__(self, app, rpm: int = 60):
        super().__init__(app)
        self.rpm = rpm  # 每分钟最大请求数
        self.window = 60  # 窗口大小（秒）
        self._db_path = RATE_LIMIT_DB_PATH
        self._local = threading.local()
        self._cleanup_lock = threading.Lock()
        self._last_cleanup_at = 0.0

        # 内存 fallback 计数器：当 SQLite 异常时降级到进程级限流，保留基本防护能力
        # 结构：{client_ip: deque([timestamp1, timestamp2, ...])}
        self._fallback_counts: Dict[str, Deque[float]] = defaultdict(deque)
        self._fallback_lock = threading.Lock()
        self._fallback_warn_at = 0.0  # 上次告警时间，避免日志洪水

        self._init_table()


    def _get_conn(self) -> sqlite3.Connection:
        """获取线程本地的 SQLite 连接"""
        conn = getattr(self._local, "conn", None)
        if conn is not None:
            try:
                conn.execute("SELECT 1")
                return conn
            except Exception:
                try:
                    conn.close()
                except Exception:
                    pass
                self._local.conn = None

        conn = sqlite3.connect(self._db_path, check_same_thread=False)
        conn.execute("PRAGMA busy_timeout=3000")
        conn.execute("PRAGMA journal_mode=WAL")
        self._local.conn = conn
        return conn

    def _init_table(self):
        """初始化限流记录表"""
        try:
            conn = self._get_conn()
            conn.execute("""
                CREATE TABLE IF NOT EXISTS rate_limit_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    client_ip TEXT NOT NULL,
                    timestamp REAL NOT NULL
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_rl_ip_ts ON rate_limit_log(client_ip, timestamp)")
            conn.commit()
        except Exception as e:
            logger.warning(f"初始化限流表失败: {e}")

    def _get_client_ip(self, request: Request) -> str:
        """获取客户端真实 IP"""
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            return forwarded.split(",")[0].strip()
        return request.client.host if request.client else "unknown"

    def _cleanup_expired(self, conn: sqlite3.Connection, now: float):
        """清理过期的限流记录（窗口外的旧数据）"""
        if now - self._last_cleanup_at < self.window:
            return
        with self._cleanup_lock:
            if now - self._last_cleanup_at < self.window:
                return
            try:
                cutoff = now - self.window * 2  # 保留 2 倍窗口，减少清理频率
                conn.execute("DELETE FROM rate_limit_log WHERE timestamp < ?", (cutoff,))
                conn.commit()
                self._last_cleanup_at = now
            except sqlite3.OperationalError as e:
                # L6: 多 Worker 并发清理场景下可能产生 "database is locked" 等瞬态错误，
                # 属于预期情况（其他 Worker 已经或正在清理），降级为 debug 日志避免告警洪水。
                # 不更新 _last_cleanup_at，允许下次请求到来时重试清理。
                logger.debug(f"清理限流记录被其他 Worker 抢占或数据库瞬态繁忙（可忽略）: {e}")
                try:
                    conn.rollback()
                except Exception:
                    pass
            except Exception as e:
                logger.warning(f"清理限流记录失败: {e}")
                try:
                    conn.rollback()
                except Exception:
                    pass


    async def dispatch(self, request: Request, call_next):
        # OPTIONS 预检请求和健康检查跳过限制
        if request.method == "OPTIONS" or request.url.path == "/":
            return await call_next(request)

        client_ip = self._get_client_ip(request)
        now = time.time()
        window_start = now - self.window

        try:
            conn = self._get_conn()

            # 查询当前窗口内该 IP 的请求数
            row = conn.execute(
                "SELECT COUNT(*) FROM rate_limit_log WHERE client_ip = ? AND timestamp > ?",
                (client_ip, window_start),
            ).fetchone()
            count = row[0] if row else 0

            # 检查是否超过限制
            if count >= self.rpm:
                # 获取最早的请求时间，计算 Retry-After
                earliest = conn.execute(
                    "SELECT MIN(timestamp) FROM rate_limit_log WHERE client_ip = ? AND timestamp > ?",
                    (client_ip, window_start),
                ).fetchone()
                retry_after = int((earliest[0] - window_start) + 1) if earliest and earliest[0] else 1
                return JSONResponse(
                    status_code=429,
                    content={"detail": f"请求过于频繁，每分钟最多 {self.rpm} 次请求，请稍后重试"},
                    headers={"Retry-After": str(max(retry_after, 1))},
                )

            # 记录本次请求
            conn.execute(
                "INSERT INTO rate_limit_log (client_ip, timestamp) VALUES (?, ?)",
                (client_ip, now),
            )
            conn.commit()

            # 每隔一个窗口周期清理一次过期记录，减少数据库膨胀
            self._cleanup_expired(conn, now)


        except Exception as e:
            # SQLite 异常时降级到进程级内存限流，保留基本防护能力（不完全放行）
            # 注意：多 Worker 模式下降级期间限流精度下降，但仍优于完全放行
            if now - self._fallback_warn_at > 10:  # 每 10s 最多告警一次，避免日志洪水
                logger.warning(f"速率限制 SQLite 异常，降级到内存限流: {e}")
                self._fallback_warn_at = now

            denied = False
            retry_after = 1
            with self._fallback_lock:
                bucket = self._fallback_counts[client_ip]
                # 剔除窗口外的旧时间戳
                while bucket and bucket[0] <= window_start:
                    bucket.popleft()
                if len(bucket) >= self.rpm:
                    denied = True
                    earliest = bucket[0]
                    retry_after = max(int((earliest - window_start) + 1), 1)
                else:
                    bucket.append(now)

                # 顺便清理长时间无活动的 key，避免内存膨胀
                if len(self._fallback_counts) > 10000:
                    stale_keys = [
                        k for k, v in self._fallback_counts.items()
                        if not v or v[-1] <= window_start
                    ]
                    for k in stale_keys:
                        self._fallback_counts.pop(k, None)

            if denied:
                return JSONResponse(
                    status_code=429,
                    content={"detail": f"请求过于频繁（降级限流），每分钟最多 {self.rpm} 次请求，请稍后重试"},
                    headers={"Retry-After": str(retry_after)},
                )

        return await call_next(request)
