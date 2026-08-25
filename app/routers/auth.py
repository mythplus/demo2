"""
认证路由

提供登录、刷新令牌、当前用户信息、登出端点。
"""
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Request, HTTPException
from pydantic import BaseModel

from app.config import MEM0_CONFIG
from app.auth.password import verify_password
from app.auth.jwt_utils import create_access_token, create_refresh_token_expiry, verify_access_token
from app.tenant_db import (
    get_tenant_by_name,
    get_user_by_credentials,
    create_refresh_token,
    verify_refresh_token,
    revoke_refresh_token,
    revoke_all_user_tokens,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1/auth", tags=["认证"])


# ============ 请求模型 ============

class LoginRequest(BaseModel):
    tenant_name: str = "default"
    username: str
    password: str


class RefreshRequest(BaseModel):
    refresh_token: str


# ============ 端点 ============

@router.post("/login")
async def login(req: LoginRequest):
    """登录：返回 access_token + refresh_token"""
    tenant = get_tenant_by_name(req.tenant_name)
    if not tenant:
        raise HTTPException(status_code=404, detail=f"租户 '{req.tenant_name}' 不存在")
    if tenant["status"] != "active":
        raise HTTPException(status_code=403, detail="租户已被禁用")

    user = get_user_by_credentials(tenant["id"], req.username)
    if not user:
        raise HTTPException(status_code=401, detail="用户名或密码错误")
    if user["status"] != "active":
        raise HTTPException(status_code=403, detail="账号已被禁用")

    if not verify_password(req.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="用户名或密码错误")

    access_token = create_access_token(
        user_id=user["id"],
        tenant_id=tenant["id"],
        username=user["username"],
        role=user["role"],
    )
    refresh_expiry = create_refresh_token_expiry()
    refresh_token = create_refresh_token(user["id"], tenant["id"], refresh_expiry)

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "expires_in": MEM0_CONFIG.get("auth", {}).get("access_token_expire_hours", 24) * 3600,
        "user": {
            "user_id": user["id"],
            "username": user["username"],
            "role": user["role"],
            "tenant_id": tenant["id"],
            "tenant_name": tenant["name"],
            "tenant_display_name": tenant["display_name"],
        },
    }


@router.post("/refresh")
async def refresh_token(req: RefreshRequest):
    """刷新访问令牌"""
    token_info = verify_refresh_token(req.refresh_token)
    if not token_info:
        raise HTTPException(status_code=401, detail="刷新令牌无效或已过期")

    # 吊销旧刷新令牌（轮换）
    revoke_refresh_token(token_info["token_id"])

    # 查用户信息
    from app.tenant_db import get_user
    user = get_user(token_info["user_id"])
    if not user or user["status"] != "active":
        raise HTTPException(status_code=403, detail="账号不可用")

    new_access = create_access_token(
        user_id=user["id"],
        tenant_id=user["tenant_id"],
        username=user["username"],
        role=user["role"],
    )
    new_refresh_expiry = create_refresh_token_expiry()
    new_refresh = create_refresh_token(user["id"], user["tenant_id"], new_refresh_expiry)

    return {
        "access_token": new_access,
        "refresh_token": new_refresh,
        "token_type": "bearer",
    }


@router.get("/me")
async def current_user(request: Request):
    """获取当前登录用户信息"""
    user = getattr(request.state, "user", None)
    if not user:
        raise HTTPException(status_code=401, detail="未登录")
    tenant_id = user.get("tenant_id", "")
    from app.tenant_db import get_tenant
    tenant = get_tenant(tenant_id)
    return {
        "user_id": user["user_id"],
        "username": user.get("username", ""),
        "role": user.get("role", "member"),
        "tenant_id": tenant_id,
        "tenant_name": tenant["name"] if tenant else "",
        "tenant_display_name": tenant["display_name"] if tenant else "",
    }


@router.post("/logout")
async def logout(request: Request):
    """登出：吊销当前用户所有刷新令牌"""
    user = getattr(request.state, "user", None)
    if user and user.get("user_id") and user["user_id"] != "dev-mode":
        revoke_all_user_tokens(user["user_id"])
    return {"detail": "已登出"}
