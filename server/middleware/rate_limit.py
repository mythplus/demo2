"""
速率限制中间件 — 基于 IP 的滑动窗口
"""

import time
import logging
from typing import Dict
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

logger = logging.getLogger(__name__)


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
