"""
API Key 认证中间件
"""

import logging
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

logger = logging.getLogger(__name__)


class ApiKeyAuthMiddleware(BaseHTTPMiddleware):
    """API Key 认证中间件：如果配置了 api_key，则所有非健康检查请求都需要携带有效的 API Key"""

    # 免认证的路径（健康检查、OPTIONS 预检请求）
    SKIP_PATHS = {"/", "/docs", "/redoc", "/openapi.json"}

    def __init__(self, app, api_key: str = ""):
        super().__init__(app)
        self.api_key = api_key

    async def dispatch(self, request: Request, call_next):
        # 如果未配置 API Key，跳过认证
        if not self.api_key:
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

        if provided_key != self.api_key:
            return JSONResponse(
                status_code=401,
                content={"detail": "无效的 API Key，请在请求头中提供有效的 Authorization: Bearer <key> 或 X-API-Key: <key>"},
            )

        return await call_next(request)
