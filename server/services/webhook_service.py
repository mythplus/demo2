"""
Webhook 服务 — 管理 Webhook 配置、触发事件通知
支持通用 HTTP POST 和企业微信群机器人格式
"""

import json
import hmac
import hashlib
import logging
import asyncio
from typing import Optional, List, Dict, Any
from pathlib import Path
from datetime import datetime

import httpx

logger = logging.getLogger(__name__)

# Webhook 配置文件路径（与 access_logs.db 同级）
WEBHOOK_CONFIG_PATH = Path(__file__).parent.parent.parent / "webhooks.json"


# ============ 数据模型 ============

class WebhookItem:
    def __init__(self, data: dict):
        self.id: str = data.get("id", "")
        self.name: str = data.get("name", "")
        self.url: str = data.get("url", "")
        self.enabled: bool = data.get("enabled", True)
        self.events: List[str] = data.get("events", [])
        self.secret: Optional[str] = data.get("secret")
        self.created_at: str = data.get("created_at", "")
        self.last_triggered: Optional[str] = data.get("last_triggered")
        self.last_status: Optional[str] = data.get("last_status")

    def to_dict(self) -> dict:
        d = {
            "id": self.id,
            "name": self.name,
            "url": self.url,
            "enabled": self.enabled,
            "events": self.events,
            "created_at": self.created_at,
        }
        if self.secret:
            d["secret"] = self.secret
        if self.last_triggered:
            d["last_triggered"] = self.last_triggered
        if self.last_status:
            d["last_status"] = self.last_status
        return d


# ============ 存储层 ============

def _load_webhooks() -> List[dict]:
    """从 JSON 文件加载 Webhook 配置"""
    if not WEBHOOK_CONFIG_PATH.exists():
        return []
    try:
        return json.loads(WEBHOOK_CONFIG_PATH.read_text(encoding="utf-8"))
    except Exception as e:
        logger.error(f"加载 Webhook 配置失败: {e}")
        return []


def _save_webhooks(webhooks: List[dict]):
    """保存 Webhook 配置到 JSON 文件"""
    try:
        WEBHOOK_CONFIG_PATH.write_text(
            json.dumps(webhooks, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    except Exception as e:
        logger.error(f"保存 Webhook 配置失败: {e}")


# ============ CRUD ============

def list_webhooks() -> List[dict]:
    return _load_webhooks()


def get_webhook(webhook_id: str) -> Optional[dict]:
    for wh in _load_webhooks():
        if wh.get("id") == webhook_id:
            return wh
    return None


def create_webhook(data: dict) -> dict:
    webhooks = _load_webhooks()
    data["created_at"] = datetime.now().isoformat()
    webhooks.append(data)
    _save_webhooks(webhooks)
    logger.info(f"Webhook 已创建: {data.get('name')} -> {data.get('url')}")
    return data


def update_webhook(webhook_id: str, data: dict) -> Optional[dict]:
    webhooks = _load_webhooks()
    for i, wh in enumerate(webhooks):
        if wh.get("id") == webhook_id:
            # 保留不可变字段
            data["id"] = webhook_id
            data["created_at"] = wh.get("created_at", "")
            # 保留运行时字段
            if "last_triggered" not in data:
                data["last_triggered"] = wh.get("last_triggered")
            if "last_status" not in data:
                data["last_status"] = wh.get("last_status")
            webhooks[i] = data
            _save_webhooks(webhooks)
            logger.info(f"Webhook 已更新: {webhook_id}")
            return data
    return None


def delete_webhook(webhook_id: str) -> bool:
    webhooks = _load_webhooks()
    filtered = [wh for wh in webhooks if wh.get("id") != webhook_id]
    if len(filtered) == len(webhooks):
        return False
    _save_webhooks(filtered)
    logger.info(f"Webhook 已删除: {webhook_id}")
    return True


# ============ 企业微信检测 ============

def _is_wecom_bot(url: str) -> bool:
    """判断是否为企业微信群机器人 URL"""
    return "qyapi.weixin.qq.com/cgi-bin/webhook/send" in url


def _build_wecom_payload(event_type: str, data: dict) -> dict:
    """构建企业微信群机器人消息格式"""
    # 提取关键信息
    memory_text = data.get("memory", "")[:200]
    user_id = data.get("user_id", "未知用户")
    memory_id = data.get("memory_id", "")[:12]

    event_labels = {
        "memory.added": "📝 新增记忆",
        "memory.updated": "✏️ 更新记忆",
        "memory.deleted": "🗑️ 删除记忆",
        "memory.searched": "🔍 语义检索",
    }
    title = event_labels.get(event_type, f"📌 {event_type}")

    content_lines = [
        f"**{title}**",
        f"> 用户: {user_id}",
    ]
    if memory_id:
        content_lines.append(f"> ID: `{memory_id}`")
    if memory_text:
        content_lines.append(f"> 内容: {memory_text}")
    content_lines.append(f"> 时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    return {
        "msgtype": "markdown",
        "markdown": {
            "content": "\n".join(content_lines),
        },
    }


def _build_generic_payload(event_type: str, data: dict) -> dict:
    """构建通用 Webhook 推送 payload"""
    return {
        "event": event_type,
        "timestamp": datetime.now().isoformat(),
        "data": data,
    }


def _sign_payload(payload_bytes: bytes, secret: str) -> str:
    """生成 HMAC-SHA256 签名"""
    return hmac.new(secret.encode("utf-8"), payload_bytes, hashlib.sha256).hexdigest()


# ============ 触发 ============

async def trigger_webhooks(
    event_type: str,
    data: dict,
    http_client: Optional[httpx.AsyncClient] = None,
):
    """
    异步触发所有匹配事件的已启用 Webhook
    在后台执行，不阻塞主请求
    """
    webhooks = _load_webhooks()
    matched = [
        wh for wh in webhooks
        if wh.get("enabled") and event_type in wh.get("events", [])
    ]

    if not matched:
        return

    client = http_client or httpx.AsyncClient(timeout=10.0)
    own_client = http_client is None

    tasks = [_send_webhook(client, wh, event_type, data) for wh in matched]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    # 更新触发状态
    all_webhooks = _load_webhooks()
    for wh, result in zip(matched, results):
        for i, stored in enumerate(all_webhooks):
            if stored.get("id") == wh.get("id"):
                all_webhooks[i]["last_triggered"] = datetime.now().isoformat()
                all_webhooks[i]["last_status"] = "success" if not isinstance(result, Exception) else "failed"
                break
    _save_webhooks(all_webhooks)

    if own_client:
        await client.aclose()

    success_count = sum(1 for r in results if not isinstance(r, Exception))
    logger.info(f"Webhook 触发完成: 事件={event_type}, 匹配={len(matched)}, 成功={success_count}")


async def _send_webhook(
    client: httpx.AsyncClient,
    webhook: dict,
    event_type: str,
    data: dict,
):
    """发送单个 Webhook 请求"""
    url = webhook.get("url", "")
    secret = webhook.get("secret")

    try:
        # 根据 URL 类型构建不同的 payload
        if _is_wecom_bot(url):
            payload = _build_wecom_payload(event_type, data)
        else:
            payload = _build_generic_payload(event_type, data)

        payload_bytes = json.dumps(payload, ensure_ascii=False).encode("utf-8")

        headers: Dict[str, str] = {"Content-Type": "application/json"}
        if secret and not _is_wecom_bot(url):
            headers["X-Webhook-Signature"] = _sign_payload(payload_bytes, secret)
            headers["X-Webhook-Event"] = event_type

        response = await client.post(url, content=payload_bytes, headers=headers)

        if response.status_code >= 400:
            logger.warning(
                f"Webhook 推送失败 [{webhook.get('name')}]: HTTP {response.status_code} - {response.text[:200]}"
            )
            raise Exception(f"HTTP {response.status_code}")

        # 企业微信 API 返回 HTTP 200 但 errcode != 0 时也视为失败
        if _is_wecom_bot(url):
            try:
                resp_json = response.json()
                errcode = resp_json.get("errcode", 0)
                errmsg = resp_json.get("errmsg", "")
                if errcode != 0:
                    logger.warning(
                        f"Webhook 企业微信返回错误 [{webhook.get('name')}]: errcode={errcode}, errmsg={errmsg}"
                    )
                    raise Exception(f"企业微信错误: errcode={errcode}, errmsg={errmsg}")
            except (ValueError, KeyError):
                pass  # 非 JSON 响应，忽略

        logger.info(f"Webhook 推送成功 [{webhook.get('name')}]: {event_type}")

    except Exception as e:
        logger.error(f"Webhook 推送异常 [{webhook.get('name')}]: {e}")
        raise


async def test_webhook(webhook_id: str, http_client: Optional[httpx.AsyncClient] = None) -> dict:
    """发送测试 Webhook"""
    wh = get_webhook(webhook_id)
    if not wh:
        return {"success": False, "message": "Webhook 不存在"}

    test_data = {
        "memory_id": "test_123456",
        "memory": "这是一条测试记忆，用于验证 Webhook 连通性。",
        "user_id": "test_user",
        "event": "test",
    }

    client = http_client or httpx.AsyncClient(timeout=10.0)
    own_client = http_client is None

    try:
        await _send_webhook(client, wh, "memory.added", test_data)
        # 更新状态
        update_webhook(webhook_id, {
            **wh,
            "last_triggered": datetime.now().isoformat(),
            "last_status": "success",
        })
        return {"success": True, "message": "测试推送成功"}
    except Exception as e:
        update_webhook(webhook_id, {
            **wh,
            "last_triggered": datetime.now().isoformat(),
            "last_status": "failed",
        })
        return {"success": False, "message": f"测试失败: {str(e)}"}
    finally:
        if own_client:
            await client.aclose()
