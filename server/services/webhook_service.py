"""Webhook 服务 - 管理 Webhook 配置、触发事件通知
支持通用 HTTP POST 和企业微信群机器人格式。

存储层使用 SQLite（access_logs.db 同库），支持多 Worker（多进程）并发安全读写。
"""

import asyncio
import base64
import hashlib
import hmac
import ipaddress
import json
import logging
import os
import socket
import sqlite3
import threading
from datetime import datetime
from typing import Any, Dict, List, Optional
from urllib.parse import parse_qs, urlparse

import httpx

from server.config import ACCESS_LOG_DB_PATH, MEM0_CONFIG
from server.services.background_tasks import create_background_task

try:
    from cryptography.fernet import Fernet, InvalidToken
except ImportError:  # pragma: no cover - 兼容未安装依赖的旧环境
    Fernet = None  # type: ignore[assignment]

    class InvalidToken(Exception):
        """兼容 cryptography 缺失时的占位异常。"""


logger = logging.getLogger(__name__)

VALID_WEBHOOK_EVENTS = {
    "memory.added",
    "memory.updated",
    "memory.deleted",
    "memory.hard_deleted",
    "memory.searched",
    "user.hard_deleted",
    "memory.batch_imported",
    "memory.batch_deleted",
    "memory.batch_hard_deleted",
}

_SECRET_PREFIX = "enc:v1:"
_THREAD_LOCAL = threading.local()
_CIPHER_CACHE: Optional["Fernet"] = None
_CIPHER_READY = False
_CIPHER_WARNING_EMITTED = False
_BLOCKED_HOSTS = {
    "localhost",
    "localhost.localdomain",
    "metadata",
    "metadata.google.internal",
    "metadata.google.internal.",
}
_BLOCKED_IPS = {
    "169.254.169.254",  # AWS / Azure IMDS
    "100.100.100.200",  # 阿里云 IMDS
    "100.100.100.100",  # 腾讯云部分元数据入口
}


# ============ SQLite 存储层 ============

def _get_db_conn() -> sqlite3.Connection:
    """获取线程本地的 SQLite 连接（复用，WAL 模式）"""
    conn = getattr(_THREAD_LOCAL, "wh_conn", None)
    if conn is not None:
        try:
            conn.execute("SELECT 1")
            return conn
        except Exception:
            try:
                conn.close()
            except Exception:
                pass
            _THREAD_LOCAL.wh_conn = None

    conn = sqlite3.connect(ACCESS_LOG_DB_PATH, check_same_thread=False)
    conn.execute("PRAGMA busy_timeout=5000")
    conn.execute("PRAGMA journal_mode=WAL")
    conn.row_factory = sqlite3.Row
    _THREAD_LOCAL.wh_conn = conn
    return conn


def init_webhook_table() -> None:
    """初始化 Webhook 配置表（应用启动时调用）"""
    conn = _get_db_conn()
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS webhooks (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            url TEXT NOT NULL,
            enabled INTEGER NOT NULL DEFAULT 1,
            events TEXT NOT NULL DEFAULT '[]',
            secret TEXT,
            created_at TEXT NOT NULL,
            last_triggered TEXT,
            last_status TEXT
        )
        """
    )
    conn.commit()
    logger.info("Webhook 配置表已初始化")


# ============ Secret 加密 ============

def _get_secret_cipher() -> Optional["Fernet"]:
    global _CIPHER_CACHE, _CIPHER_READY, _CIPHER_WARNING_EMITTED

    if _CIPHER_READY:
        return _CIPHER_CACHE

    _CIPHER_READY = True
    if Fernet is None:
        if not _CIPHER_WARNING_EMITTED:
            logger.warning("未安装 cryptography，Webhook secret 将暂时无法加密存储")
            _CIPHER_WARNING_EMITTED = True
        return None

    master_secret = str(
        MEM0_CONFIG.get("security", {}).get("webhook_secret_key")
        or os.environ.get("WEBHOOK_SECRET_KEY")
        or MEM0_CONFIG.get("security", {}).get("api_key")
        or ""
    ).strip()
    if not master_secret:
        return None

    key = base64.urlsafe_b64encode(hashlib.sha256(master_secret.encode("utf-8")).digest())
    _CIPHER_CACHE = Fernet(key)
    return _CIPHER_CACHE


def _encrypt_secret(secret: Optional[str]) -> Optional[str]:
    if not secret:
        return None
    if secret.startswith(_SECRET_PREFIX):
        return secret

    cipher = _get_secret_cipher()
    if cipher is None:
        return secret

    token = cipher.encrypt(secret.encode("utf-8")).decode("utf-8")
    return f"{_SECRET_PREFIX}{token}"


def _decrypt_secret(secret: Optional[str]) -> Optional[str]:
    if not secret:
        return None
    if not secret.startswith(_SECRET_PREFIX):
        return secret

    cipher = _get_secret_cipher()
    if cipher is None:
        logger.error("Webhook secret 已加密，但当前环境缺少可用解密密钥")
        return None

    try:
        return cipher.decrypt(secret[len(_SECRET_PREFIX):].encode("utf-8")).decode("utf-8")
    except InvalidToken:
        logger.error("Webhook secret 解密失败：密钥不匹配或密文损坏")
        return None


def migrate_webhook_secrets() -> int:
    """将旧明文 Webhook secret 升级为加密存储。"""
    cipher = _get_secret_cipher()
    if cipher is None:
        logger.info("Webhook secret 加密迁移已跳过：当前无可用加密密钥")
        return 0

    conn = _get_db_conn()
    try:
        rows = conn.execute(
            "SELECT id, secret FROM webhooks WHERE secret IS NOT NULL AND secret != ''"
        ).fetchall()
        migrated = 0
        for row in rows:
            stored_secret = row["secret"]
            if not stored_secret or stored_secret.startswith(_SECRET_PREFIX):
                continue
            conn.execute(
                "UPDATE webhooks SET secret = ? WHERE id = ?",
                (_encrypt_secret(stored_secret), row["id"]),
            )
            migrated += 1
        if migrated:
            conn.commit()
            logger.info(f"已完成 {migrated} 条 Webhook secret 加密迁移")
        return migrated
    except Exception as exc:
        logger.warning(f"Webhook secret 迁移失败（不影响主流程）: {exc}")
        return 0


# ============ 迁移 ============

def _migrate_from_json() -> None:
    """从旧的 webhooks.json 迁移数据到 SQLite（一次性，启动时自动执行）"""
    from pathlib import Path

    json_path = Path(__file__).parent.parent.parent / "webhooks.json"
    if not json_path.exists():
        return

    try:
        data = json.loads(json_path.read_text(encoding="utf-8"))
        if not data:
            return

        conn = _get_db_conn()
        existing = conn.execute("SELECT COUNT(*) FROM webhooks").fetchone()[0]
        if existing > 0:
            logger.info("Webhook SQLite 表已有数据，跳过 JSON 迁移")
            return

        for wh in data:
            conn.execute(
                """
                INSERT OR IGNORE INTO webhooks
                (id, name, url, enabled, events, secret, created_at, last_triggered, last_status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    wh.get("id", ""),
                    wh.get("name", ""),
                    wh.get("url", ""),
                    1 if wh.get("enabled", True) else 0,
                    json.dumps(wh.get("events", []), ensure_ascii=False),
                    _encrypt_secret(wh.get("secret")),
                    wh.get("created_at", ""),
                    wh.get("last_triggered"),
                    wh.get("last_status"),
                ),
            )
        conn.commit()

        backup_path = json_path.with_suffix(".json.bak")
        json_path.rename(backup_path)
        logger.info(
            f"已从 webhooks.json 迁移 {len(data)} 条 Webhook 配置到 SQLite，旧文件已备份为 {backup_path.name}"
        )
    except Exception as exc:
        logger.warning(f"从 webhooks.json 迁移失败（不影响正常使用）: {exc}")


# ============ 工具函数 ============

def _row_to_dict(row: sqlite3.Row) -> dict:
    """将 SQLite Row 转换为 Webhook 字典。"""
    data = dict(row)
    data["enabled"] = bool(data.get("enabled", 1))
    try:
        data["events"] = json.loads(data.get("events", "[]"))
    except (json.JSONDecodeError, TypeError):
        data["events"] = []
    return data


def validate_webhook_events(events: List[str]) -> List[str]:
    """返回非法事件列表。"""
    return [event for event in events if event not in VALID_WEBHOOK_EVENTS]


def _is_wecom_bot(url: str) -> bool:
    """判断是否为企业微信群机器人 URL。"""
    return "qyapi.weixin.qq.com/cgi-bin/webhook/send" in url


def _is_blocked_ip(ip_text: str) -> bool:
    try:
        ip_obj = ipaddress.ip_address(ip_text)
    except ValueError:
        return True

    return (
        ip_text in _BLOCKED_IPS
        or ip_obj.is_private
        or ip_obj.is_loopback
        or ip_obj.is_link_local
        or ip_obj.is_multicast
        or ip_obj.is_reserved
        or ip_obj.is_unspecified
    )


def _resolve_host_ips(hostname: str, port: int) -> List[str]:
    infos = socket.getaddrinfo(hostname, port, type=socket.SOCK_STREAM)
    return sorted({item[4][0] for item in infos if item[4]})


def _validate_target_url(url: str) -> dict:
    """仅做格式、协议和目标主机策略校验，不主动对目标发起请求。"""
    try:
        parsed = urlparse(url)
    except Exception:
        return {"valid": False, "message": "URL 格式不合法"}

    if parsed.scheme not in {"http", "https"}:
        return {"valid": False, "message": "仅支持 http/https 协议"}
    if not parsed.netloc or not parsed.hostname:
        return {"valid": False, "message": "URL 缺少有效主机名"}
    if parsed.username or parsed.password:
        return {"valid": False, "message": "URL 不允许包含用户名或密码"}

    hostname = parsed.hostname.strip().lower().rstrip(".")
    port = parsed.port or (443 if parsed.scheme == "https" else 80)

    if hostname in _BLOCKED_HOSTS or hostname.endswith(".local"):
        return {"valid": False, "message": f"禁止访问主机: {hostname}"}

    if _is_wecom_bot(url):
        qs = parse_qs(parsed.query)
        key_values = qs.get("key", [])
        if not key_values or not key_values[0].strip():
            return {"valid": False, "message": "企业微信 Webhook URL 缺少 key 参数"}

    try:
        ipaddress.ip_address(hostname)
        resolved_ips = [hostname]
    except ValueError:
        try:
            resolved_ips = _resolve_host_ips(hostname, port)
        except socket.gaierror:
            return {"valid": False, "message": f"Webhook 主机无法解析: {hostname}"}
        except Exception as exc:
            return {"valid": False, "message": f"解析 Webhook 主机失败: {exc}"}

    if not resolved_ips:
        return {"valid": False, "message": "Webhook 主机未解析到任何地址"}

    blocked_ips = [ip for ip in resolved_ips if _is_blocked_ip(ip)]
    if blocked_ips:
        return {
            "valid": False,
            "message": f"Webhook 目标地址命中内网/本机/元数据保护策略: {', '.join(blocked_ips)}",
        }

    return {"valid": True, "message": "URL 格式与主机策略校验通过"}


def _assert_webhook_target_allowed(url: str) -> None:
    validation = _validate_target_url(url)
    if not validation["valid"]:
        raise ValueError(validation["message"])


# ============ 存储层（SQLite） ============

def _load_webhooks() -> List[dict]:
    """从 SQLite 加载所有 Webhook 配置。"""
    try:
        conn = _get_db_conn()
        rows = conn.execute("SELECT * FROM webhooks ORDER BY created_at DESC").fetchall()
        return [_row_to_dict(row) for row in rows]
    except Exception as exc:
        logger.error(f"加载 Webhook 配置失败: {exc}")
        return []


# ============ CRUD ============

def list_webhooks() -> List[dict]:
    return _load_webhooks()


def get_webhook(webhook_id: str) -> Optional[dict]:
    try:
        conn = _get_db_conn()
        row = conn.execute("SELECT * FROM webhooks WHERE id = ?", (webhook_id,)).fetchone()
        return _row_to_dict(row) if row else None
    except Exception as exc:
        logger.error(f"获取 Webhook 失败: {exc}")
        return None


def create_webhook(data: dict) -> dict:
    try:
        conn = _get_db_conn()
        created_at = datetime.now().isoformat()
        stored_secret = _encrypt_secret(data.get("secret"))
        record = {
            **data,
            "secret": stored_secret,
            "created_at": created_at,
        }
        conn.execute(
            """
            INSERT INTO webhooks (id, name, url, enabled, events, secret, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                record.get("id", ""),
                record.get("name", ""),
                record.get("url", ""),
                1 if record.get("enabled", True) else 0,
                json.dumps(record.get("events", []), ensure_ascii=False),
                record.get("secret"),
                record["created_at"],
            ),
        )
        conn.commit()
        logger.info(f"Webhook 已创建: {record.get('name')} -> {record.get('url')}")
        return record
    except Exception as exc:
        logger.error(f"创建 Webhook 失败: {exc}")
        raise


def update_webhook(webhook_id: str, data: dict) -> Optional[dict]:
    try:
        conn = _get_db_conn()
        existing = conn.execute("SELECT * FROM webhooks WHERE id = ?", (webhook_id,)).fetchone()
        if not existing:
            return None

        existing_dict = _row_to_dict(existing)
        name = data.get("name", existing_dict["name"])
        url = data.get("url", existing_dict["url"])
        enabled = data.get("enabled", existing_dict["enabled"])
        events = data.get("events", existing_dict["events"])

        if "secret" in data:
            secret = _encrypt_secret(data.get("secret"))
        else:
            secret = existing_dict.get("secret")

        last_triggered = data.get("last_triggered", existing_dict.get("last_triggered"))
        last_status = data.get("last_status", existing_dict.get("last_status"))

        conn.execute(
            """
            UPDATE webhooks SET name=?, url=?, enabled=?, events=?, secret=?,
            last_triggered=?, last_status=? WHERE id=?
            """,
            (
                name,
                url,
                1 if enabled else 0,
                json.dumps(events, ensure_ascii=False),
                secret,
                last_triggered,
                last_status,
                webhook_id,
            ),
        )
        conn.commit()
        logger.info(f"Webhook 已更新: {webhook_id}")
        return get_webhook(webhook_id)
    except Exception as exc:
        logger.error(f"更新 Webhook 失败: {exc}")
        return None


def delete_webhook(webhook_id: str) -> bool:
    try:
        conn = _get_db_conn()
        cursor = conn.execute("DELETE FROM webhooks WHERE id = ?", (webhook_id,))
        conn.commit()
        if cursor.rowcount == 0:
            return False
        logger.info(f"Webhook 已删除: {webhook_id}")
        return True
    except Exception as exc:
        logger.error(f"删除 Webhook 失败: {exc}")
        return False


# ============ URL 校验 ============

async def validate_webhook_url(
    url: str,
    http_client: Optional[httpx.AsyncClient] = None,
) -> dict:
    """验证 Webhook URL，仅做格式和目标策略校验，不主动探测远端服务。"""
    _ = http_client  # 兼容旧调用签名
    return _validate_target_url(url)


# ============ Payload 构建 ============

def _build_wecom_payload(event_type: str, data: dict) -> dict:
    """构建企业微信群机器人消息格式。"""
    memory_text = data.get("memory", "")[:150]
    user_id = data.get("user_id", "") or ""
    memory_id = data.get("memory_id", "")
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    event_config = {
        "memory.added": {"label": "新增记忆", "color": "info"},
        "memory.updated": {"label": "更新记忆", "color": "info"},
    "memory.deleted": {"label": "删除记忆", "color": "warning"},
    "memory.hard_deleted": {"label": "永久删除记忆", "color": "error"},
        "memory.searched": {"label": "语义检索", "color": "info"},
        "user.hard_deleted": {"label": "用户删除", "color": "warning"},
        "memory.batch_imported": {"label": "批量导入", "color": "info"},
    "memory.batch_deleted": {"label": "批量删除", "color": "warning"},
    "memory.batch_hard_deleted": {"label": "批量永久删除", "color": "error"},
    }
    config = event_config.get(event_type, {"label": event_type, "color": "info"})

    lines = [f'<font color="{config["color"]}">**[{config["label"]}]**</font>', ""]
    lines.append(f"**事件：**{config['label']}")
    if user_id:
        lines.append(f'**用户：**<font color="info">{user_id}</font>')

    if memory_id:
        lines.append(f"**记忆ID：**{memory_id}")
    if memory_text:
        display = memory_text if len(memory_text) <= 80 else memory_text[:77] + "..."
        lines.append(f"**内容：**{display}")
    lines.append(f"**时间：**{now_str}")

    return {
        "msgtype": "markdown",
        "markdown": {
            "content": "\n".join(lines),
        },
    }


def _build_generic_payload(event_type: str, data: dict) -> dict:
    """构建通用 Webhook 推送 payload。"""
    return {
        "event": event_type,
        "timestamp": datetime.now().isoformat(),
        "data": data,
    }


def _sign_payload(payload_bytes: bytes, secret: str) -> str:
    """生成 HMAC-SHA256 签名。"""
    return hmac.new(secret.encode("utf-8"), payload_bytes, hashlib.sha256).hexdigest()


# ============ 调度 ============

def schedule_webhook_delivery(
    event_type: str,
    data: dict,
    http_client: Optional[httpx.AsyncClient] = None,
) -> None:
    """将 Webhook 推送注册为可追踪后台任务。"""
    create_background_task(
        trigger_webhooks(event_type, data, http_client),
        name=f"webhook:{event_type}:{datetime.now().strftime('%H%M%S%f')}",
    )


# ============ 触发 ============

async def trigger_webhooks(
    event_type: str,
    data: dict,
    http_client: Optional[httpx.AsyncClient] = None,
) -> None:
    """异步触发所有匹配事件的已启用 Webhook。"""
    webhooks = _load_webhooks()
    matched = [
        webhook
        for webhook in webhooks
        if webhook.get("enabled") and event_type in webhook.get("events", [])
    ]

    if not matched:
        return

    client = http_client or httpx.AsyncClient(timeout=10.0)
    own_client = http_client is None

    try:
        tasks = [_send_webhook(client, webhook, event_type, data) for webhook in matched]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        try:
            conn = _get_db_conn()
            now_iso = datetime.now().isoformat()
            for webhook, result in zip(matched, results):
                status = "success" if not isinstance(result, Exception) else "failed"
                conn.execute(
                    "UPDATE webhooks SET last_triggered=?, last_status=? WHERE id=?",
                    (now_iso, status, webhook.get("id")),
                )
            conn.commit()
        except Exception as exc:
            logger.warning(f"更新 Webhook 触发状态失败: {exc}")

        success_count = sum(1 for result in results if not isinstance(result, Exception))
        logger.info(f"Webhook 触发完成: 事件={event_type}, 匹配={len(matched)}, 成功={success_count}")
    finally:
        if own_client:
            await client.aclose()


async def _send_webhook(
    client: httpx.AsyncClient,
    webhook: dict,
    event_type: str,
    data: dict,
) -> None:
    """发送单个 Webhook 请求。"""
    url = webhook.get("url", "")
    _assert_webhook_target_allowed(url)

    stored_secret = webhook.get("secret")
    secret = _decrypt_secret(stored_secret)

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
        raise RuntimeError(f"HTTP {response.status_code}")

    if _is_wecom_bot(url):
        try:
            resp_json = response.json()
            errcode = resp_json.get("errcode", 0)
            errmsg = resp_json.get("errmsg", "")
            if errcode != 0:
                logger.warning(
                    f"Webhook 企业微信返回错误 [{webhook.get('name')}]: errcode={errcode}, errmsg={errmsg}"
                )
                raise RuntimeError(f"企业微信错误: errcode={errcode}, errmsg={errmsg}")
        except ValueError:
            pass

    logger.info(f"Webhook 推送成功 [{webhook.get('name')}]: {event_type}")


async def test_webhook(webhook_id: str, http_client: Optional[httpx.AsyncClient] = None) -> dict:
    """发送测试 Webhook。"""
    webhook = get_webhook(webhook_id)
    if not webhook:
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
        await _send_webhook(client, webhook, "memory.added", test_data)
        update_webhook(
            webhook_id,
            {
                **webhook,
                "last_triggered": datetime.now().isoformat(),
                "last_status": "success",
            },
        )
        return {"success": True, "message": "测试推送成功"}
    except Exception as exc:
        update_webhook(
            webhook_id,
            {
                **webhook,
                "last_triggered": datetime.now().isoformat(),
                "last_status": "failed",
            },
        )
        return {"success": False, "message": f"测试失败: {exc}"}
    finally:
        if own_client:
            await client.aclose()
