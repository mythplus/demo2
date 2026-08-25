"""
租户配置管理路由

提供租户级 LLM/Embedder 配置覆盖的读写端点。
仅 admin 角色可访问。
"""
import logging

from fastapi import APIRouter, Request, HTTPException
from pydantic import BaseModel

from app.tenant_db import (
    get_tenant,
    get_tenant_config,
    upsert_tenant_config,
    delete_tenant_config,
)
from app.memory_engine import invalidate_tenant_memory

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1/tenants", tags=["租户配置"])


# ============ 请求模型 ============

class LlmConfigOverride(BaseModel):
    provider: str | None = None
    config: dict | None = None


class EmbedderConfigOverride(BaseModel):
    provider: str | None = None
    config: dict | None = None


class TenantConfigRequest(BaseModel):
    llm_config: LlmConfigOverride | None = None
    embedder_config: EmbedderConfigOverride | None = None
    custom_categories: list[str] | None = None


# ============ 权限检查 ============

def _require_admin(request: Request):
    """要求 admin 角色"""
    user = getattr(request.state, "user", None)
    if not user:
        raise HTTPException(status_code=401, detail="未登录")
    if user.get("role") not in ("admin",):
        if user.get("user_id") != "dev-mode":
            raise HTTPException(status_code=403, detail="权限不足，需要管理员角色")


# ============ 端点 ============

@router.get("/{tenant_id}/config")
async def get_tenant_config_detail(request: Request, tenant_id: str):
    """获取租户配置覆盖"""
    _require_admin(request)
    if not get_tenant(tenant_id):
        raise HTTPException(status_code=404, detail="租户不存在")
    cfg = get_tenant_config(tenant_id)
    return cfg or {
        "tenant_id": tenant_id,
        "llm_config": None,
        "embedder_config": None,
        "custom_categories": None,
    }


@router.put("/{tenant_id}/config")
async def update_tenant_config_detail(request: Request, tenant_id: str, req: TenantConfigRequest):
    """创建或更新租户配置覆盖"""
    _require_admin(request)
    if not get_tenant(tenant_id):
        raise HTTPException(status_code=404, detail="租户不存在")

    # 构建 dict 参数
    llm_config = None
    if req.llm_config:
        llm_config = {}
        if req.llm_config.provider:
            llm_config["provider"] = req.llm_config.provider
        if req.llm_config.config:
            llm_config["config"] = req.llm_config.config

    embedder_config = None
    if req.embedder_config:
        embedder_config = {}
        if req.embedder_config.provider:
            embedder_config["provider"] = req.embedder_config.provider
        if req.embedder_config.config:
            embedder_config["config"] = req.embedder_config.config

    result = upsert_tenant_config(
        tenant_id=tenant_id,
        llm_config=llm_config,
        embedder_config=embedder_config,
        custom_categories=req.custom_categories,
    )

    # 清除租户 Memory 实例缓存，使新配置生效
    invalidate_tenant_memory(tenant_id)

    return result


@router.delete("/{tenant_id}/config")
async def delete_tenant_config_detail(request: Request, tenant_id: str):
    """删除租户配置覆盖（恢复为全局默认）"""
    _require_admin(request)
    if not get_tenant(tenant_id):
        raise HTTPException(status_code=404, detail="租户不存在")
    delete_tenant_config(tenant_id)
    invalidate_tenant_memory(tenant_id)
    return {"detail": "租户配置已重置为全局默认"}


@router.get("/{tenant_id}/config/effective")
async def get_effective_config(request: Request, tenant_id: str):
    """获取租户最终生效的完整配置（全局 + 覆盖合并后）"""
    _require_admin(request)
    if not get_tenant(tenant_id):
        raise HTTPException(status_code=404, detail="租户不存在")

    from app.tenant_db import get_tenant_memory_config
    effective = get_tenant_memory_config(tenant_id)
    # 隐藏敏感信息
    if "graph_store" in effective:
        gs = effective.get("graph_store", {}).get("config", {})
        if "password" in gs:
            gs["password"] = "***"
    return effective
