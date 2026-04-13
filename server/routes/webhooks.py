"""
Webhook 管理路由 — CRUD + 测试
"""

import logging
from typing import Optional, List
from datetime import datetime

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from server.services import webhook_service, memory_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1/webhooks", tags=["Webhooks"])


# ============ 请求/响应模型 ============

class WebhookCreateRequest(BaseModel):
    id: str = Field(..., max_length=50)
    name: str = Field(..., max_length=100)
    url: str = Field(..., max_length=500)
    enabled: bool = True
    events: List[str] = Field(..., max_length=10)
    secret: Optional[str] = Field(None, max_length=200)


class WebhookUpdateRequest(BaseModel):
    name: Optional[str] = Field(None, max_length=100)
    url: Optional[str] = Field(None, max_length=500)
    enabled: Optional[bool] = None
    events: Optional[List[str]] = Field(None, max_length=10)
    secret: Optional[str] = Field(None, max_length=200)


# ============ 路由 ============

@router.get("/")
async def list_webhooks():
    """获取所有 Webhook 配置"""
    webhooks = webhook_service.list_webhooks()
    # 返回时隐藏 secret 明文
    for wh in webhooks:
        if wh.get("secret"):
            wh["secret"] = "***"
    return {"webhooks": webhooks, "total": len(webhooks)}


@router.get("/{webhook_id}")
async def get_webhook(webhook_id: str):
    """获取单个 Webhook 配置"""
    wh = webhook_service.get_webhook(webhook_id)
    if not wh:
        raise HTTPException(status_code=404, detail="Webhook 不存在")
    if wh.get("secret"):
        wh["secret"] = "***"
    return wh


@router.post("/")
async def create_webhook(request: WebhookCreateRequest):
    """创建 Webhook"""
    # 校验事件类型
    valid_events = {"memory.added", "memory.updated", "memory.deleted", "memory.searched", "user.hard_deleted"}
    invalid = [e for e in request.events if e not in valid_events]
    if invalid:
        raise HTTPException(status_code=400, detail=f"无效的事件类型: {invalid}")

    # 验证 Webhook URL 可用性
    validation = await webhook_service.validate_webhook_url(
        request.url,
        http_client=memory_service.http_client,
    )
    if not validation["valid"]:
        raise HTTPException(status_code=400, detail=f"Webhook URL 验证失败: {validation['message']}，请检查URL的正确性")

    data = request.dict()
    result = webhook_service.create_webhook(data)
    return {"message": "创建成功", "webhook": result}


@router.put("/{webhook_id}")
async def update_webhook(webhook_id: str, request: WebhookUpdateRequest):
    """更新 Webhook"""
    existing = webhook_service.get_webhook(webhook_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Webhook 不存在")

    # 合并更新字段
    update_data = {**existing}
    for key, value in request.dict(exclude_unset=True).items():
        update_data[key] = value

    result = webhook_service.update_webhook(webhook_id, update_data)
    if not result:
        raise HTTPException(status_code=500, detail="更新失败")
    return {"message": "更新成功", "webhook": result}


@router.delete("/{webhook_id}")
async def delete_webhook(webhook_id: str):
    """删除 Webhook"""
    if not webhook_service.delete_webhook(webhook_id):
        raise HTTPException(status_code=404, detail="Webhook 不存在")
    return {"message": "删除成功"}


@router.post("/{webhook_id}/toggle")
async def toggle_webhook(webhook_id: str):
    """启用/禁用 Webhook"""
    existing = webhook_service.get_webhook(webhook_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Webhook 不存在")

    existing["enabled"] = not existing.get("enabled", True)
    result = webhook_service.update_webhook(webhook_id, existing)
    return {"message": "已切换", "enabled": result.get("enabled")}


@router.post("/{webhook_id}/test")
async def test_webhook(webhook_id: str):
    """发送测试 Webhook 推送"""
    result = await webhook_service.test_webhook(
        webhook_id,
        http_client=memory_service.http_client,
    )
    if result["success"]:
        return result
    raise HTTPException(status_code=400, detail=result["message"])
