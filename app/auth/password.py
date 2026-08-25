"""
密码哈希工具（bcrypt）
"""
import bcrypt
import logging

logger = logging.getLogger(__name__)


def hash_password(plain_password: str) -> str:
    """哈希密码"""
    salt = bcrypt.gensalt(rounds=12)
    hashed = bcrypt.hashpw(plain_password.encode("utf-8"), salt)
    return hashed.decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """验证密码"""
    try:
        return bcrypt.checkpw(
            plain_password.encode("utf-8"),
            hashed_password.encode("utf-8"),
        )
    except Exception as e:
        logger.warning(f"密码验证失败: {e}")
        return False
