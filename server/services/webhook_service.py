"""Webhook 服务 - 管理 Webhook 配置、触发事件通知
支持通用 HTTP POST 和企业微信群机器人格式

存储层使用 SQLite（access_logs.db 同库），支持多 Worker（多进程）并发安全读写。
"""

import json
import hmac
import hashlib
import logging
import sqlite3
import asyncio
import threading
from typing import Optional, List, Dict, Any
from datetime import datetime

import httpx

from server.config import ACCESS_LOG_DB_PATH

logger = logging.getLogger(__name__)

# ============ SQLite 存储层 ============

_thread_local = threading.local()

def _get_db_conn() -> sqlite3.Connection:
    """获取线程本地的 SQLite 连接（复用，WAL 模式）"""
    conn = getattr(_thread_local, "wh_conn", None)
    if conn is not None:
        try:
            conn.execute("SELECT 1")
            return conn
        except Exception:
            try:
                conn.close()
            except Exception:
                pass
            _thread_local.wh_conn = None

    conn = sqlite3.connect(ACCESS_LOG_DB_PATH, check_same_thread=False)
    conn.execute("PRAGMA busy_timeout=5000")
    conn.execute("PRAGMA journal_mode=WAL")
    conn.row_factory = sqlite3.Row
    _thread_local.wh_conn = conn
    return conn


def init_webhook_table():
    """初始化 Webhook 配置表（应用启动时调用）"""
    conn = _get_db_conn()
    conn.execute("""
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
    """)
    conn.commit()
    logger.info("Webhook 配置表已初始化")


def _migrate_from_json():
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
        # 检查是否已有数据（避免重复迁移）
        existing = conn.execute("SELECT COUNT(*) FROM webhooks").fetchone()[0]
        if existing > 0:
            logger.info("Webhook SQLite 表已有数据，跳过 JSON 迁移")
            return
        for wh in data:
            conn.execute(
                """INSERT OR IGNORE INTO webhooks (id, name, url, enabled, events, secret, created_at, last_triggered, last_status)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    wh.get("id", ""),
                    wh.get("name", ""),
                    wh.get("url", ""),
                    1 if wh.get("enabled", True) else 0,
                    json.dumps(wh.get("events", []), ensure_ascii=False),
                    wh.get("secret"),
                    wh.get("created_at", ""),
                    wh.get("last_triggered"),
                    wh.get("last_status"),
                ),
            )
        conn.commit()
        # 迁移成功后重命名旧文件
        backup_path = json_path.with_suffix(".json.bak")
        json_path.rename(backup_path)
        logger.info(f"已从 webhooks.json 迁移 {len(data)} 条 Webhook 配置到 SQLite，旧文件已备份为 {backup_path.name}")
    except Exception as e:
        logger.warning(f"从 webhooks.json 迁移失败（不影响正常使用）: {e}")


def _row_to_dict(row: sqlite3.Row) -> dict:
    """将 SQLite Row 转换为 Webhook 字典"""
    d = dict(row)
    d["enabled"] = bool(d.get("enabled", 1))
    try:
        d["events"] = json.loads(d.get("events", "[]"))
    except (json.JSONDecodeError, TypeError):
        d["events"] = []
    return d


# ============ 存储层（SQLite） ============

def _load_webhooks() -> List[dict]:
    """从 SQLite 加载所有 Webhook 配置"""
    try:
        conn = _get_db_conn()
        rows = conn.execute("SELECT * FROM webhooks ORDER BY created_at DESC").fetchall()
        return [_row_to_dict(row) for row in rows]
    except Exception as e:
        logger.error(f"加载 Webhook 配置失败: {e}")
        return []


# ============ CRUD ============

def list_webhooks() -> List[dict]:
    return _load_webhooks()


def get_webhook(webhook_id: str) -> Optional[dict]:
    try:
        conn = _get_db_conn()
        row = conn.execute("SELECT * FROM webhooks WHERE id = ?", (webhook_id,)).fetchone()
        return _row_to_dict(row) if row else None
    except Exception as e:
        logger.error(f"获取 Webhook 失败: {e}")
        return None


def create_webhook(data: dict) -> dict:
    try:
        conn = _get_db_conn()
        data["created_at"] = datetime.now().isoformat()
        conn.execute(
            """INSERT INTO webhooks (id, name, url, enabled, events, secret, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                data.get("id", ""),
                data.get("name", ""),
                data.get("url", ""),
                1 if data.get("enabled", True) else 0,
                json.dumps(data.get("events", []), ensure_ascii=False),
                data.get("secret"),
                data["created_at"],
            ),
        )
        conn.commit()
        logger.info(f"Webhook 已创建: {data.get('name')} -> {data.get('url')}")
        return data
    except Exception as e:
        logger.error(f"创建 Webhook 失败: {e}")
        raise


def update_webhook(webhook_id: str, data: dict) -> Optional[dict]:
    try:
        conn = _get_db_conn()
        existing = conn.execute("SELECT * FROM webhooks WHERE id = ?", (webhook_id,)).fetchone()
        if not existing:
            return None
        existing_dict = _row_to_dict(existing)

        # 合并字段：保留不可变字段和运行时字段
        name = data.get("name", existing_dict["name"])
        url = data.get("url", existing_dict["url"])
        enabled = data.get("enabled", existing_dict["enabled"])
        events = data.get("events", existing_dict["events"])
        secret = data.get("secret", existing_dict.get("secret"))
        last_triggered = data.get("last_triggered", existing_dict.get("last_triggered"))
        last_status = data.get("last_status", existing_dict.get("last_status"))

        conn.execute(
            """UPDATE webhooks SET name=?, url=?, enabled=?, events=?, secret=?,
               last_triggered=?, last_status=? WHERE id=?""",
            (
                name, url,
                1 if enabled else 0,
                json.dumps(events, ensure_ascii=False),
                secret, last_triggered, last_status,
                webhook_id,
            ),
        )
        conn.commit()
        logger.info(f"Webhook 已更新: {webhook_id}")
        # 返回更新后的完整数据
        return get_webhook(webhook_id)
    except Exception as e:
        logger.error(f"更新 Webhook 失败: {e}")
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
    except Exception as e:
        logger.error(f"删除 Webhook 失败: {e}")
        return False


# ============ URL 验证 ============

async def validate_webhook_url(
    url: str,
    http_client: Optional[httpx.AsyncClient] = None,
) -> dict:
    """
    验证 Webhook URL 是否可用：
    - 企业微信 URL：检查 key 参数非空，并发送测试消息验证连通性
    - 通用 URL：发送 POST 请求验证可达性
    返回 {"valid": True/False, "message": "..."}
    """
    # 1. 基本格式校验
    try:
        from urllib.parse import urlparse, parse_qs
        parsed = urlparse(url)
        if not parsed.scheme or not parsed.netloc:
            return {"valid": False, "message": "URL 格式不合法"}
    except Exception:
        return {"valid": False, "message": "URL 格式不合法"}

    # 2. 企业微信 URL 特殊校验
    if _is_wecom_bot(url):
        qs = parse_qs(parsed.query)
        key_values = qs.get("key", [])
        if not key_values or not key_values[0].strip():
            return {"valid": False, "message": "企业微信 Webhook URL 缺少 key 参数"}

    # 3. 实际发送验证请求
    client = http_client or httpx.AsyncClient(timeout=10.0)
    own_client = http_client is None

    try:
        test_wh = {"url": url, "name": "验证测试"}
        test_data = {
            "memory_id": "validate_test",
            "memory": "Webhook 连通性验证（此消息用于验证 URL 是否可用，可忽略）",
            "user_id": "test",
            "event": "test",
        }
        await _send_webhook(client, test_wh, "memory.added", test_data)
        return {"valid": True, "message": "验证通过"}
    except Exception as e:
        err_msg = str(e)
        if "企业微信错误" in err_msg:
            return {"valid": False, "message": f"企业微信返回错误: {err_msg}"}
        return {"valid": False, "message": f"URL 不可达或响应异常: {err_msg}"}
    finally:
        if own_client:
            await client.aclose()


# ============ 企业微信检测 ============

def _is_wecom_bot(url: str) -> bool:
    """判断是否为企业微信群机器人 URL"""
    return "qyapi.weixin.qq.com/cgi-bin/webhook/send" in url


def _build_wecom_payload(event_type: str, data: dict) -> dict:
    """构建企业微信群机器人消息格式 — 结构化键值对风格"""
    memory_text = data.get("memory", "")[:150]
    user_id = data.get("user_id", "") or ""
    memory_id = data.get("memory_id", "")
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # 事件配置
    event_config = {
        "memory.added":          {"label": "新增记忆", "color": "info"},
        "memory.updated":        {"label": "更新记忆", "color": "info"},
        "memory.deleted":        {"label": "删除记忆", "color": "warning"},
        "memory.searched":       {"label": "语义检索", "color": "info"},
        "user.hard_deleted":     {"label": "用户删除", "color": "warning"},
        "memory.batch_imported": {"label": "批量导入", "color": "info"},
        "memory.batch_deleted":  {"label": "批量删除", "color": "warning"},
    }
    cfg = event_config.get(event_type, {"label": event_type, "color": "info"})

    lines = []

    # 标题行
    lines.append(f'<font color="{cfg["color"]}">**[{cfg["label"]}]**</font>')
    lines.append("")  # 空行分隔

    # 事件类型
    lines.append(f'**事件：**{cfg["label"]}')

    # 用户
    if user_id:
        lines.append(f'**用户：**<font color="info">{user_id}</font>')

    # 记忆ID
    if memory_id:
        lines.append(f'**记忆ID：**{memory_id}')

    # 内容
    if memory_text:
        display = memory_text if len(memory_text) <= 80 else memory_text[:77] + "..."
        lines.append(f'**内容：**{display}')

    # 时间
    lines.append(f'**时间：**{now_str}')

    return {
        "msgtype": "markdown",
        "markdown": {
            "content": "\n".join(lines),
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

    try:
        tasks = [_send_webhook(client, wh, event_type, data) for wh in matched]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # 更新触发状态（直接写 SQLite，无需全量读写）
        try:
            conn = _get_db_conn()
            now_iso = datetime.now().isoformat()
            for wh, result in zip(matched, results):
                status = "success" if not isinstance(result, Exception) else "failed"
                conn.execute(
                    "UPDATE webhooks SET last_triggered=?, last_status=? WHERE id=?",
                    (now_iso, status, wh.get("id")),
                )
            conn.commit()
        except Exception as e:
            logger.warning(f"更新 Webhook 触发状态失败: {e}")

        success_count = sum(1 for r in results if not isinstance(r, Exception))
        logger.info(f"Webhook 触发完成: 事件={event_type}, 匹配={len(matched)}, 成功={success_count}")
    finally:
        if own_client:
            await client.aclose()


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
            except ValueError:
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
