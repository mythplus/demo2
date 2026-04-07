"""
速率限制中间件 — 基于 SQLite 的跨 Worker 共享滑动窗口

多 Worker（多进程）模式下，每个 Worker 共享同一个 SQLite 数据库文件，
通过 WAL 模式 + busy_timeout 实现并发安全的限流计数。
"""

import time
import sqlite3
import logging
import threading
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from server.config import ACCESS_LOG_DB_PATH

logger = logging.getLogger(__name__)


class RateLimitMiddleware(BaseHTTPMiddleware):
    """基于 SQLite 共享存储的滑动窗口速率限制中间件（支持多 Worker）"""

    def __init__(self, app, rpm: int = 60):
        super().__init__(app)
        self.rpm = rpm  # 每分钟最大请求数
        self.window = 60  # 窗口大小（秒）
        self._db_path = ACCESS_LOG_DB_PATH
        self._local = threading.local()
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

    def _cleanup_expired(self, conn: sqlite3.Connection):
        """清理过期的限流记录（窗口外的旧数据）"""
        try:
            cutoff = time.time() - self.window * 2  # 保留 2 倍窗口，减少清理频率
            conn.execute("DELETE FROM rate_limit_log WHERE timestamp < ?", (cutoff,))
            conn.commit()
        except Exception as e:
            logger.warning(f"清理限流记录失败: {e}")

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

            # 每 200 次请求清理一次过期记录（概率性清理，减少 IO）
            if int(now) % 200 == 0:
                self._cleanup_expired(conn)

        except Exception as e:
            # 限流组件异常不应阻塞正常请求，降级放行并记录警告
            logger.warning(f"速率限制检查异常（降级放行）: {e}")

        return await call_next(request)
