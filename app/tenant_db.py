"""
Mem0 Dashboard 后端 - 租户元数据库模块

管理租户、用户、API Key、配额用量等元数据，使用独立 SQLite 文件。
"""
import os
import json
import sqlite3
import secrets
import hashlib
import threading
import logging
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)

# ============ 租户元数据库路径 ============
TENANT_DB_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "tenant_meta.db",
)

# ============ 线程本地连接池 ============
_tenant_thread_local = threading.local()


def _get_tenant_db_conn():
    """获取租户元数据库连接（线程本地复用）"""
    conn = getattr(_tenant_thread_local, "tenant_db_conn", None)
    if conn is not None:
        try:
            conn.execute("SELECT 1")
            return conn
        except Exception:
            try:
                conn.close()
            except Exception:
                pass
            _tenant_thread_local.tenant_db_conn = None

    conn = sqlite3.connect(TENANT_DB_PATH, check_same_thread=False)
    conn.execute("PRAGMA busy_timeout=5000")
    conn.execute("PRAGMA journal_mode=WAL")
    conn.row_factory = sqlite3.Row
    _tenant_thread_local.tenant_db_conn = conn
    return conn


# ============ 建表 ============

def init_tenant_db():
    """初始化租户元数据库"""
    conn = _get_tenant_db_conn()

    # 租户表
    conn.execute("""
        CREATE TABLE IF NOT EXISTS tenants (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL UNIQUE,
            display_name TEXT,
            status TEXT NOT NULL DEFAULT 'active',
            plan TEXT NOT NULL DEFAULT 'free',
            max_memories INTEGER NOT NULL DEFAULT 10000,
            max_api_calls_per_day INTEGER NOT NULL DEFAULT 5000,
            rate_limit_per_minute INTEGER NOT NULL DEFAULT 120,
            rate_limit_per_hour INTEGER NOT NULL DEFAULT 3600,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """)

    # 租户用户表
    conn.execute("""
        CREATE TABLE IF NOT EXISTS tenant_users (
            id TEXT PRIMARY KEY,
            tenant_id TEXT NOT NULL,
            username TEXT NOT NULL,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'member',
            status TEXT NOT NULL DEFAULT 'active',
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY (tenant_id) REFERENCES tenants(id),
            UNIQUE(tenant_id, username)
        )
    """)

    # API Key 表
    conn.execute("""
        CREATE TABLE IF NOT EXISTS tenant_api_keys (
            id TEXT PRIMARY KEY,
            tenant_id TEXT NOT NULL,
            name TEXT NOT NULL,
            key_prefix TEXT NOT NULL,
            key_hash TEXT NOT NULL UNIQUE,
            status TEXT NOT NULL DEFAULT 'active',
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            last_used_at TEXT,
            FOREIGN KEY (tenant_id) REFERENCES tenants(id)
        )
    """)

    # 配额用量表
    conn.execute("""
        CREATE TABLE IF NOT EXISTS tenant_quota_usage (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tenant_id TEXT NOT NULL,
            date TEXT NOT NULL,
            memory_count INTEGER NOT NULL DEFAULT 0,
            api_call_count INTEGER NOT NULL DEFAULT 0,
            UNIQUE(tenant_id, date),
            FOREIGN KEY (tenant_id) REFERENCES tenants(id)
        )
    """)

    # 租户配置覆盖表（阶段3使用）
    conn.execute("""
        CREATE TABLE IF NOT EXISTS tenant_configs (
            tenant_id TEXT PRIMARY KEY,
            llm_config TEXT,
            embedder_config TEXT,
            custom_categories TEXT,
            updated_at TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY (tenant_id) REFERENCES tenants(id)
        )
    """)

    # 刷新令牌表
    conn.execute("""
        CREATE TABLE IF NOT EXISTS refresh_tokens (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            tenant_id TEXT NOT NULL,
            token_hash TEXT NOT NULL UNIQUE,
            expires_at TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            revoked TEXT NOT NULL DEFAULT '0'
        )
    """)

    conn.execute("CREATE INDEX IF NOT EXISTS idx_tenant_users_tenant ON tenant_users(tenant_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_api_keys_tenant ON tenant_api_keys(tenant_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_api_keys_hash ON tenant_api_keys(key_hash)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_quota_tenant_date ON tenant_quota_usage(tenant_id, date)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_refresh_tokens_user ON refresh_tokens(user_id)")

    conn.commit()
    logger.info("租户元数据库初始化完成")


# ============ 租户 CRUD ============

def create_tenant(name: str, display_name: str = "", plan: str = "free",
                  max_memories: int = 10000, max_api_calls_per_day: int = 5000,
                  rate_limit_per_minute: int = 120, rate_limit_per_hour: int = 3600) -> dict:
    """创建租户"""
    import uuid
    tenant_id = str(uuid.uuid4())
    conn = _get_tenant_db_conn()
    conn.execute(
        """INSERT INTO tenants (id, name, display_name, plan, max_memories, max_api_calls_per_day,
           rate_limit_per_minute, rate_limit_per_hour)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (tenant_id, name, display_name or name, plan, max_memories,
         max_api_calls_per_day, rate_limit_per_minute, rate_limit_per_hour),
    )
    conn.commit()
    return get_tenant(tenant_id)


def get_tenant(tenant_id: str) -> Optional[dict]:
    """获取租户"""
    conn = _get_tenant_db_conn()
    row = conn.execute("SELECT * FROM tenants WHERE id = ?", (tenant_id,)).fetchone()
    return dict(row) if row else None


def get_tenant_by_name(name: str) -> Optional[dict]:
    """按名称获取租户"""
    conn = _get_tenant_db_conn()
    row = conn.execute("SELECT * FROM tenants WHERE name = ?", (name,)).fetchone()
    return dict(row) if row else None


def list_tenants(offset: int = 0, limit: int = 50) -> tuple:
    """列出租户，返回 (tenants, total)"""
    conn = _get_tenant_db_conn()
    total = conn.execute("SELECT COUNT(*) FROM tenants").fetchone()[0]
    rows = conn.execute(
        "SELECT * FROM tenants ORDER BY created_at DESC LIMIT ? OFFSET ?",
        (limit, offset),
    ).fetchall()
    return [dict(r) for r in rows], total


def update_tenant(tenant_id: str, **kwargs) -> Optional[dict]:
    """更新租户"""
    if not kwargs:
        return get_tenant(tenant_id)
    conn = _get_tenant_db_conn()
    sets = []
    params = []
    for k, v in kwargs.items():
        if k in ("display_name", "status", "plan", "max_memories",
                 "max_api_calls_per_day", "rate_limit_per_minute", "rate_limit_per_hour"):
            sets.append(f"{k} = ?")
            params.append(v)
    if not sets:
        return get_tenant(tenant_id)
    sets.append("updated_at = ?")
    params.append(datetime.now().isoformat())
    params.append(tenant_id)
    conn.execute(f"UPDATE tenants SET {', '.join(sets)} WHERE id = ?", params)
    conn.commit()
    return get_tenant(tenant_id)


def delete_tenant(tenant_id: str):
    """删除租户（级联删除关联数据）"""
    conn = _get_tenant_db_conn()
    conn.execute("DELETE FROM tenant_users WHERE tenant_id = ?", (tenant_id,))
    conn.execute("DELETE FROM tenant_api_keys WHERE tenant_id = ?", (tenant_id,))
    conn.execute("DELETE FROM tenant_quota_usage WHERE tenant_id = ?", (tenant_id,))
    conn.execute("DELETE FROM tenant_configs WHERE tenant_id = ?", (tenant_id,))
    conn.execute("DELETE FROM refresh_tokens WHERE tenant_id = ?", (tenant_id,))
    conn.execute("DELETE FROM tenants WHERE id = ?", (tenant_id,))
    conn.commit()


# ============ 租户用户 CRUD ============

def create_user(tenant_id: str, username: str, password_hash: str,
                role: str = "member") -> dict:
    """创建租户用户"""
    import uuid
    user_id = str(uuid.uuid4())
    conn = _get_tenant_db_conn()
    conn.execute(
        """INSERT INTO tenant_users (id, tenant_id, username, password_hash, role)
           VALUES (?, ?, ?, ?, ?)""",
        (user_id, tenant_id, username, password_hash, role),
    )
    conn.commit()
    return get_user(user_id)


def get_user(user_id: str) -> Optional[dict]:
    """获取用户"""
    conn = _get_tenant_db_conn()
    row = conn.execute("SELECT * FROM tenant_users WHERE id = ?", (user_id,)).fetchone()
    return dict(row) if row else None


def get_user_by_credentials(tenant_id: str, username: str) -> Optional[dict]:
    """按租户+用户名获取用户（用于登录验证）"""
    conn = _get_tenant_db_conn()
    row = conn.execute(
        "SELECT * FROM tenant_users WHERE tenant_id = ? AND username = ?",
        (tenant_id, username),
    ).fetchone()
    return dict(row) if row else None


def list_users(tenant_id: str) -> list:
    """列出租户用户"""
    conn = _get_tenant_db_conn()
    rows = conn.execute(
        "SELECT * FROM tenant_users WHERE tenant_id = ? ORDER BY created_at ASC",
        (tenant_id,),
    ).fetchall()
    return [dict(r) for r in rows]


def delete_user(tenant_id: str, user_id: str):
    """删除用户"""
    conn = _get_tenant_db_conn()
    conn.execute(
        "DELETE FROM tenant_users WHERE id = ? AND tenant_id = ?",
        (user_id, tenant_id),
    )
    conn.commit()


def update_user(user_id: str, **kwargs) -> Optional[dict]:
    """更新用户"""
    if not kwargs:
        return get_user(user_id)
    conn = _get_tenant_db_conn()
    sets = []
    params = []
    for k, v in kwargs.items():
        if k in ("password_hash", "role", "status"):
            sets.append(f"{k} = ?")
            params.append(v)
    if not sets:
        return get_user(user_id)
    sets.append("updated_at = ?")
    params.append(datetime.now().isoformat())
    params.append(user_id)
    conn.execute(f"UPDATE tenant_users SET {', '.join(sets)} WHERE id = ?", params)
    conn.commit()
    return get_user(user_id)


# ============ API Key CRUD ============

def _hash_api_key(raw_key: str) -> str:
    """哈希 API Key"""
    return hashlib.sha256(raw_key.encode()).hexdigest()


def create_api_key(tenant_id: str, name: str) -> dict:
    """生成并存储 API Key，返回含原始 key 的字典（仅此一次可见）"""
    import uuid
    raw_key = f"m0-{secrets.token_urlsafe(32)}"
    key_prefix = raw_key[:12]
    key_hash = _hash_api_key(raw_key)
    key_id = str(uuid.uuid4())
    conn = _get_tenant_db_conn()
    conn.execute(
        """INSERT INTO tenant_api_keys (id, tenant_id, name, key_prefix, key_hash)
           VALUES (?, ?, ?, ?, ?)""",
        (key_id, tenant_id, name, key_prefix, key_hash),
    )
    conn.commit()
    return {
        "id": key_id,
        "tenant_id": tenant_id,
        "name": name,
        "key_prefix": key_prefix,
        "raw_key": raw_key,
        "created_at": datetime.now().isoformat(),
    }


def get_api_key_by_raw(raw_key: str) -> Optional[dict]:
    """通过原始 key 查找（哈希比对）"""
    if not raw_key:
        return None
    key_hash = _hash_api_key(raw_key)
    conn = _get_tenant_db_conn()
    row = conn.execute(
        "SELECT * FROM tenant_api_keys WHERE key_hash = ? AND status = 'active'",
        (key_hash,),
    ).fetchone()
    if row:
        # 更新 last_used_at
        conn.execute(
            "UPDATE tenant_api_keys SET last_used_at = ? WHERE id = ?",
            (datetime.now().isoformat(), row["id"]),
        )
        conn.commit()
    return dict(row) if row else None


def list_api_keys(tenant_id: str) -> list:
    """列出租户 API Key（不含哈希）"""
    conn = _get_tenant_db_conn()
    rows = conn.execute(
        """SELECT id, tenant_id, name, key_prefix, status, created_at, last_used_at
           FROM tenant_api_keys WHERE tenant_id = ? ORDER BY created_at DESC""",
        (tenant_id,),
    ).fetchall()
    return [dict(r) for r in rows]


def delete_api_key(tenant_id: str, key_id: str):
    """删除 API Key"""
    conn = _get_tenant_db_conn()
    conn.execute(
        "DELETE FROM tenant_api_keys WHERE id = ? AND tenant_id = ?",
        (key_id, tenant_id),
    )
    conn.commit()


# ============ 配额用量 ============

def get_quota_usage(tenant_id: str) -> dict:
    """获取租户今日用量 + 总记忆数"""
    conn = _get_tenant_db_conn()
    today = datetime.now().strftime("%Y-%m-%d")
    row = conn.execute(
        "SELECT * FROM tenant_quota_usage WHERE tenant_id = ? AND date = ?",
        (tenant_id, today),
    ).fetchone()
    today_usage = dict(row) if row else {"memory_count": 0, "api_call_count": 0}

    # 总 API 调用数
    total_row = conn.execute(
        "SELECT COALESCE(SUM(api_call_count), 0) as total FROM tenant_quota_usage WHERE tenant_id = ?",
        (tenant_id,),
    ).fetchone()

    return {
        "tenant_id": tenant_id,
        "date": today,
        "today_memory_count": today_usage.get("memory_count", 0),
        "today_api_call_count": today_usage.get("api_call_count", 0),
        "total_api_call_count": total_row["total"] if total_row else 0,
    }


def increment_api_call_count(tenant_id: str):
    """递增 API 调用计数"""
    conn = _get_tenant_db_conn()
    today = datetime.now().strftime("%Y-%m-%d")
    conn.execute(
        """INSERT INTO tenant_quota_usage (tenant_id, date, api_call_count)
           VALUES (?, ?, 1)
           ON CONFLICT(tenant_id, date) DO UPDATE SET api_call_count = api_call_count + 1""",
        (tenant_id, today),
    )
    conn.commit()


def increment_memory_count(tenant_id: str, delta: int = 1):
    """递增记忆计数"""
    conn = _get_tenant_db_conn()
    today = datetime.now().strftime("%Y-%m-%d")
    conn.execute(
        """INSERT INTO tenant_quota_usage (tenant_id, date, memory_count)
           VALUES (?, ?, ?)
           ON CONFLICT(tenant_id, date) DO UPDATE SET memory_count = memory_count + ?""",
        (tenant_id, today, max(delta, 0), max(delta, 0)),
    )
    conn.commit()


# ============ 刷新令牌 ============

def _hash_token(raw_token: str) -> str:
    return hashlib.sha256(raw_token.encode()).hexdigest()


def create_refresh_token(user_id: str, tenant_id: str, expires_at: str) -> str:
    """创建刷新令牌，返回原始 token"""
    raw_token = secrets.token_urlsafe(48)
    token_hash = _hash_token(raw_token)
    import uuid
    conn = _get_tenant_db_conn()
    conn.execute(
        """INSERT INTO refresh_tokens (id, user_id, tenant_id, token_hash, expires_at)
           VALUES (?, ?, ?, ?, ?)""",
        (str(uuid.uuid4()), user_id, tenant_id, token_hash, expires_at),
    )
    conn.commit()
    return raw_token


def verify_refresh_token(raw_token: str) -> Optional[dict]:
    """验证刷新令牌，返回 {user_id, tenant_id} 或 None"""
    if not raw_token:
        return None
    token_hash = _hash_token(raw_token)
    conn = _get_tenant_db_conn()
    row = conn.execute(
        """SELECT * FROM refresh_tokens
           WHERE token_hash = ? AND revoked = '0' AND expires_at > ?""",
        (token_hash, datetime.now().isoformat()),
    ).fetchone()
    if row:
        return {"user_id": row["user_id"], "tenant_id": row["tenant_id"], "token_id": row["id"]}
    return None


def revoke_refresh_token(token_id: str):
    """吊销刷新令牌"""
    conn = _get_tenant_db_conn()
    conn.execute("UPDATE refresh_tokens SET revoked = '1' WHERE id = ?", (token_id,))
    conn.commit()


def revoke_all_user_tokens(user_id: str):
    """吊销用户所有刷新令牌"""
    conn = _get_tenant_db_conn()
    conn.execute("UPDATE refresh_tokens SET revoked = '1' WHERE user_id = ?", (user_id,))
    conn.commit()


# ============ 默认租户初始化 ============

def ensure_default_tenant(admin_username: str, admin_password: str):
    """确保 default 租户和管理员账号存在"""
    from app.auth.password import hash_password

    tenant = get_tenant_by_name("default")
    if not tenant:
        tenant = create_tenant(
            name="default",
            display_name="默认租户",
            plan="enterprise",
            max_memories=999999,
            max_api_calls_per_day=999999,
            rate_limit_per_minute=999,
            rate_limit_per_hour=99999,
        )
        logger.info(f"已创建 default 租户: {tenant['id']}")

    # 检查管理员是否已存在
    admin = get_user_by_credentials(tenant["id"], admin_username)
    if not admin:
        password_hash = hash_password(admin_password)
        create_user(
            tenant_id=tenant["id"],
            username=admin_username,
            password_hash=password_hash,
            role="admin",
        )
        logger.info(f"已创建管理员账号: {admin_username}")
    else:
        logger.info(f"管理员账号已存在: {admin_username}")


# ============ 租户级配置覆盖 ============

def get_tenant_config(tenant_id: str) -> Optional[dict]:
    """获取租户配置覆盖（LLM/Embedder/自定义分类）"""
    conn = _get_tenant_db_conn()
    row = conn.execute(
        "SELECT * FROM tenant_configs WHERE tenant_id = ?",
        (tenant_id,),
    ).fetchone()
    if not row:
        return None
    result = dict(row)
    # 反序列化 JSON 字段
    for field in ("llm_config", "embedder_config", "custom_categories"):
        if result.get(field):
            try:
                result[field] = json.loads(result[field])
            except (json.JSONDecodeError, TypeError):
                pass
    return result


def upsert_tenant_config(tenant_id: str, llm_config: dict = None,
                         embedder_config: dict = None,
                         custom_categories: list = None) -> dict:
    """创建或更新租户配置覆盖"""
    conn = _get_tenant_db_conn()

    # 序列化 JSON 字段
    llm_json = json.dumps(llm_config, ensure_ascii=False) if llm_config is not None else None
    embedder_json = json.dumps(embedder_config, ensure_ascii=False) if embedder_config is not None else None
    categories_json = json.dumps(custom_categories, ensure_ascii=False) if custom_categories is not None else None

    # 检查是否已存在
    existing = conn.execute(
        "SELECT tenant_id FROM tenant_configs WHERE tenant_id = ?",
        (tenant_id,),
    ).fetchone()

    if existing:
        # 动态构建 UPDATE（只更新提供的字段）
        sets = ["updated_at = ?"]
        params = [datetime.now().isoformat()]
        if llm_config is not None:
            sets.append("llm_config = ?")
            params.append(llm_json)
        if embedder_config is not None:
            sets.append("embedder_config = ?")
            params.append(embedder_json)
        if custom_categories is not None:
            sets.append("custom_categories = ?")
            params.append(categories_json)
        params.append(tenant_id)
        conn.execute(
            f"UPDATE tenant_configs SET {', '.join(sets)} WHERE tenant_id = ?",
            params,
        )
    else:
        conn.execute(
            """INSERT INTO tenant_configs (tenant_id, llm_config, embedder_config, custom_categories)
               VALUES (?, ?, ?, ?)""",
            (tenant_id, llm_json, embedder_json, categories_json),
        )

    conn.commit()
    return get_tenant_config(tenant_id)


def delete_tenant_config(tenant_id: str):
    """删除租户配置覆盖（恢复为全局默认）"""
    conn = _get_tenant_db_conn()
    conn.execute("DELETE FROM tenant_configs WHERE tenant_id = ?", (tenant_id,))
    conn.commit()


# ============ 租户级 Memory 实例管理 ============

_tenant_memory_instances: dict = {}  # tenant_id → Memory instance


def get_tenant_memory_config(tenant_id: str) -> dict:
    """
    构建租户级 Mem0 配置：
    1. 以全局 MEM0_CONFIG 为基础
    2. 如果租户有 llm_config / embedder_config 覆盖，则合并替换
    返回完整的 Mem0 配置字典
    """
    from app.config import MEM0_CONFIG

    # 深拷贝全局配置
    import copy
    config = copy.deepcopy(MEM0_CONFIG)

    tenant_cfg = get_tenant_config(tenant_id)
    if not tenant_cfg:
        return config

    # 覆盖 LLM 配置
    if tenant_cfg.get("llm_config"):
        llm_override = tenant_cfg["llm_config"]
        if "provider" in llm_override:
            config["llm"]["provider"] = llm_override["provider"]
        if "config" in llm_override:
            config["llm"]["config"].update(llm_override["config"])

    # 覆盖 Embedder 配置
    if tenant_cfg.get("embedder_config"):
        embedder_override = tenant_cfg["embedder_config"]
        if "provider" in embedder_override:
            config["embedder"]["provider"] = embedder_override["provider"]
        if "config" in embedder_override:
            config["embedder"]["config"].update(embedder_override["config"])

    return config
