"""
认证中间件

解析 JWT 或 API Key，注入 request.state.user / request.state.tenant_id。
当 auth.enabled = false 时跳过认证，注入 default 租户上下文。
"""
import logging
from datetime import datetime

from fastapi import Request
from fastapi.responses import JSONResponse

from app.config import MEM0_CONFIG
from app.auth.jwt_utils import verify_access_token
from app.tenant_db import (
    get_api_key_by_raw,
    get_tenant,
    get_user,
    increment_api_call_count,
)

logger = logging.getLogger(__name__)

# 认证白名单路径（不需要认证）
PUBLIC_PATHS = {
    "/",
    "/docs",
    "/redoc",
    "/openapi.json",
    "/v1/health",
    "/v1/health/",
    "/v1/auth/login",
    "/v1/auth/refresh",
}

# 公共前缀（以这些开头的路径也不需要认证）
PUBLIC_PREFIXES = ("/docs", "/redoc")


def _is_public_path(path: str) -> bool:
    """判断是否为公开路径"""
    if path in PUBLIC_PATHS:
        return True
    for prefix in PUBLIC_PREFIXES:
        if path.startswith(prefix):
            return True
    return False


def _is_auth_enabled() -> bool:
    """检查认证是否启用"""
    return MEM0_CONFIG.get("auth", {}).get("enabled", False)


async def auth_middleware(request: Request, call_next):
    """认证中间件"""
    # 公开路径直接放行
    if _is_public_path(request.url.path):
        return await call_next(request)

    # 认证未启用：注入 default 租户上下文
    if not _is_auth_enabled():
        default_tenant = get_tenant_by_name_safe("default")
        if default_tenant:
            request.state.tenant_id = default_tenant["id"]
            request.state.user = {
                "user_id": "dev-mode",
                "username": "developer",
                "role": "admin",
                "tenant_id": default_tenant["id"],
            }
        else:
            request.state.tenant_id = "default"
            request.state.user = None
        return await call_next(request)

    # --- 认证已启用：尝试 JWT ---
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        token = auth_header[7:]
        payload = verify_access_token(token)
        if payload:
            request.state.user = {
                "user_id": payload["sub"],
                "username": payload.get("username", ""),
                "role": payload.get("role", "member"),
                "tenant_id": payload["tenant_id"],
            }
            request.state.tenant_id = payload["tenant_id"]
            # 异步递增 API 调用计数
            try:
                increment_api_call_count(payload["tenant_id"])
            except Exception:
                pass
            return await call_next(request)
        return JSONResponse(
            status_code=401,
            content={"detail": "令牌无效或已过期，请重新登录"},
        )

    # --- 尝试 API Key ---
    api_key = request.headers.get("X-API-Key", "")
    if api_key:
        key_record = get_api_key_by_raw(api_key)
        if key_record:
            tenant = get_tenant(key_record["tenant_id"])
            if tenant and tenant["status"] == "active":
                request.state.user = {
                    "user_id": f"apikey:{key_record['id']}",
                    "username": key_record["name"],
                    "role": "api_key",
                    "tenant_id": key_record["tenant_id"],
                }
                request.state.tenant_id = key_record["tenant_id"]
                try:
                    increment_api_call_count(key_record["tenant_id"])
                except Exception:
                    pass
                return await call_next(request)
        return JSONResponse(
            status_code=401,
            content={"detail": "API Key 无效"},
        )

    # 无认证信息
    return JSONResponse(
        status_code=401,
        content={"detail": "未提供认证信息，请登录或提供 API Key"},
    )


def get_tenant_by_name_safe(name: str):
    """安全获取租户（异常时返回 None）"""
    try:
        from app.tenant_db import get_tenant_by_name
        return get_tenant_by_name(name)
    except Exception:
        return None
