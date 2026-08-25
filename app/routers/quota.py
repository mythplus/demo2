"""
配额用量查询路由

让租户管理员和用户能查看当前用量情况。
"""
import logging

from fastapi import APIRouter, Request, HTTPException

from app.tenant_db import get_tenant, get_quota_usage
from app.middleware.rate_limiter import check_rate_limit

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1/quota", tags=["配额管理"])


@router.get("/usage")
async def get_current_usage(request: Request):
    """获取当前租户的配额用量"""
    tenant_id = getattr(request.state, "tenant_id", None)
    if not tenant_id:
        raise HTTPException(status_code=400, detail="无法确定租户")

    tenant = get_tenant(tenant_id)
    if not tenant:
        raise HTTPException(status_code=404, detail="租户不存在")

    usage = get_quota_usage(tenant_id)

    return {
        **usage,
        "limits": {
            "max_memories": tenant.get("max_memories", 10000),
            "max_api_calls_per_day": tenant.get("max_api_calls_per_day", 5000),
            "rate_limit_per_minute": tenant.get("rate_limit_per_minute", 120),
            "rate_limit_per_hour": tenant.get("rate_limit_per_hour", 3600),
            "plan": tenant.get("plan", "free"),
        },
        "rate_limit_status": {
            "enabled": True,
        },
    }


@router.get("/check")
async def check_current_rate_limit(request: Request):
    """检查当前租户的速率限制状态（不消耗配额）"""
    tenant_id = getattr(request.state, "tenant_id", None)
    if not tenant_id:
        raise HTTPException(status_code=400, detail="无法确定租户")

    allowed, reason = check_rate_limit(tenant_id)
    return {
        "allowed": allowed,
        "reason": reason,
        "tenant_id": tenant_id,
    }
