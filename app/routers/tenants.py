"""
租户管理路由

提供租户 CRUD、用户管理、API Key 管理端点。
仅 admin 角色可访问（认证启用时）。
"""
import logging

from fastapi import APIRouter, Request, HTTPException
from pydantic import BaseModel

from app.tenant_db import (
    create_tenant,
    get_tenant,
    list_tenants,
    update_tenant,
    delete_tenant,
    create_user,
    list_users,
    get_user,
    delete_user,
    update_user,
    create_api_key,
    list_api_keys,
    delete_api_key,
    get_quota_usage,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1/tenants", tags=["租户管理"])


# ============ 请求模型 ============

class CreateTenantRequest(BaseModel):
    name: str
    display_name: str = ""
    plan: str = "free"
    max_memories: int = 10000
    max_api_calls_per_day: int = 5000
    rate_limit_per_minute: int = 120
    rate_limit_per_hour: int = 3600


class UpdateTenantRequest(BaseModel):
    display_name: str | None = None
    status: str | None = None
    plan: str | None = None
    max_memories: int | None = None
    max_api_calls_per_day: int | None = None
    rate_limit_per_minute: int | None = None
    rate_limit_per_hour: int | None = None


class CreateUserRequest(BaseModel):
    username: str
    password: str
    role: str = "member"


class UpdateUserRequest(BaseModel):
    password: str | None = None
    role: str | None = None
    status: str | None = None


class CreateApiKeyRequest(BaseModel):
    name: str


# ============ 权限检查 ============

def _require_admin(request: Request):
    """要求 admin 角色（认证启用时）"""
    user = getattr(request.state, "user", None)
    if not user:
        raise HTTPException(status_code=401, detail="未登录")
    if user.get("role") not in ("admin", "api_key") and user.get("role") != "dev-mode":
        # api_key 角色也允许管理（方便自动化）
        if user.get("role") != "admin":
            raise HTTPException(status_code=403, detail="权限不足，需要管理员角色")


def _is_dev_mode(request: Request) -> bool:
    """是否为开发模式（认证关闭）"""
    user = getattr(request.state, "user", None)
    return user is not None and user.get("user_id") == "dev-mode"


# ============ 租户 CRUD ============

@router.get("")
async def list_all_tenants(request: Request, offset: int = 0, limit: int = 50):
    """列出租户"""
    _require_admin(request)
    tenants, total = list_tenants(offset=offset, limit=limit)
    return {"items": tenants, "total": total, "offset": offset, "limit": limit}


@router.post("")
async def create_new_tenant(request: Request, req: CreateTenantRequest):
    """创建租户"""
    _require_admin(request)
    try:
        tenant = create_tenant(
            name=req.name,
            display_name=req.display_name,
            plan=req.plan,
            max_memories=req.max_memories,
            max_api_calls_per_day=req.max_api_calls_per_day,
            rate_limit_per_minute=req.rate_limit_per_minute,
            rate_limit_per_hour=req.rate_limit_per_hour,
        )
        return tenant
    except Exception as e:
        if "UNIQUE" in str(e):
            raise HTTPException(status_code=409, detail=f"租户名 '{req.name}' 已存在")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{tenant_id}")
async def get_tenant_detail(request: Request, tenant_id: str):
    """获取租户详情"""
    _require_admin(request)
    tenant = get_tenant(tenant_id)
    if not tenant:
        raise HTTPException(status_code=404, detail="租户不存在")
    usage = get_quota_usage(tenant_id)
    return {**tenant, "usage": usage}


@router.put("/{tenant_id}")
async def update_tenant_detail(request: Request, tenant_id: str, req: UpdateTenantRequest):
    """更新租户"""
    _require_admin(request)
    kwargs = {k: v for k, v in req.model_dump().items() if v is not None}
    tenant = update_tenant(tenant_id, **kwargs)
    if not tenant:
        raise HTTPException(status_code=404, detail="租户不存在")
    return tenant


@router.delete("/{tenant_id}")
async def delete_tenant_by_id(request: Request, tenant_id: str):
    """删除租户"""
    _require_admin(request)
    if not get_tenant(tenant_id):
        raise HTTPException(status_code=404, detail="租户不存在")
    delete_tenant(tenant_id)
    return {"detail": "租户已删除"}


# ============ 租户用户管理 ============

@router.get("/{tenant_id}/users")
async def list_tenant_users(request: Request, tenant_id: str):
    """列出租户用户"""
    _require_admin(request)
    if not get_tenant(tenant_id):
        raise HTTPException(status_code=404, detail="租户不存在")
    users = list_users(tenant_id)
    # 不返回密码哈希
    return [{"id": u["id"], "username": u["username"], "role": u["role"],
             "status": u["status"], "created_at": u["created_at"]} for u in users]


@router.post("/{tenant_id}/users")
async def create_tenant_user(request: Request, tenant_id: str, req: CreateUserRequest):
    """创建租户用户"""
    _require_admin(request)
    if not get_tenant(tenant_id):
        raise HTTPException(status_code=404, detail="租户不存在")
    from app.auth.password import hash_password
    try:
        user = create_user(
            tenant_id=tenant_id,
            username=req.username,
            password_hash=hash_password(req.password),
            role=req.role,
        )
        return {"id": user["id"], "username": user["username"], "role": user["role"],
                "status": user["status"], "created_at": user["created_at"]}
    except Exception as e:
        if "UNIQUE" in str(e):
            raise HTTPException(status_code=409, detail=f"用户名 '{req.username}' 已存在")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{tenant_id}/users/{user_id}")
async def delete_tenant_user(request: Request, tenant_id: str, user_id: str):
    """删除租户用户"""
    _require_admin(request)
    delete_user(tenant_id, user_id)
    return {"detail": "用户已删除"}


@router.put("/{tenant_id}/users/{user_id}")
async def update_tenant_user(request: Request, tenant_id: str, user_id: str, req: UpdateUserRequest):
    """更新租户用户"""
    _require_admin(request)
    kwargs = {}
    if req.password:
        from app.auth.password import hash_password
        kwargs["password_hash"] = hash_password(req.password)
    if req.role:
        kwargs["role"] = req.role
    if req.status:
        kwargs["status"] = req.status
    user = update_user(user_id, **kwargs)
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    return {"id": user["id"], "username": user["username"], "role": user["role"],
            "status": user["status"]}


# ============ API Key 管理 ============

@router.get("/{tenant_id}/api-keys")
async def list_tenant_api_keys(request: Request, tenant_id: str):
    """列出 API Key"""
    _require_admin(request)
    if not get_tenant(tenant_id):
        raise HTTPException(status_code=404, detail="租户不存在")
    return list_api_keys(tenant_id)


@router.post("/{tenant_id}/api-keys")
async def create_tenant_api_key(request: Request, tenant_id: str, req: CreateApiKeyRequest):
    """创建 API Key（仅创建时返回完整 key）"""
    _require_admin(request)
    if not get_tenant(tenant_id):
        raise HTTPException(status_code=404, detail="租户不存在")
    return create_api_key(tenant_id, req.name)


@router.delete("/{tenant_id}/api-keys/{key_id}")
async def delete_tenant_api_key(request: Request, tenant_id: str, key_id: str):
    """删除 API Key"""
    _require_admin(request)
    delete_api_key(tenant_id, key_id)
    return {"detail": "API Key 已删除"}
