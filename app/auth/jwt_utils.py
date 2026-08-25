"""
JWT 签发与验证工具
"""
import jwt
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from app.config import MEM0_CONFIG

logger = logging.getLogger(__name__)


def _get_jwt_config() -> dict:
    """从配置中获取 JWT 参数"""
    auth_config = MEM0_CONFIG.get("auth", {})
    return {
        "secret": auth_config.get("jwt_secret", "mem0-dashboard-fallback-secret"),
        "access_expire_hours": auth_config.get("access_token_expire_hours", 24),
        "refresh_expire_days": auth_config.get("refresh_token_expire_days", 7),
    }


def create_access_token(user_id: str, tenant_id: str, username: str, role: str) -> str:
    """签发 JWT 访问令牌"""
    cfg = _get_jwt_config()
    now = datetime.now(timezone.utc)
    payload = {
        "sub": user_id,
        "tenant_id": tenant_id,
        "username": username,
        "role": role,
        "type": "access",
        "iat": now,
        "exp": now + timedelta(hours=cfg["access_expire_hours"]),
    }
    return jwt.encode(payload, cfg["secret"], algorithm="HS256")


def create_refresh_token_expiry() -> str:
    """计算刷新令牌过期时间"""
    cfg = _get_jwt_config()
    return (datetime.now(timezone.utc) + timedelta(days=cfg["refresh_expire_days"])).isoformat()


def verify_access_token(token: str) -> Optional[dict]:
    """验证 JWT 访问令牌，返回 payload 或 None"""
    cfg = _get_jwt_config()
    try:
        payload = jwt.decode(token, cfg["secret"], algorithms=["HS256"])
        if payload.get("type") != "access":
            return None
        return payload
    except jwt.ExpiredSignatureError:
        logger.debug("JWT 已过期")
        return None
    except jwt.InvalidTokenError as e:
        logger.debug(f"JWT 无效: {e}")
        return None
