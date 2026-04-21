"""Alembic 迁移环境入口。

关键行为：
- sqlalchemy.url 从 server.config.DATABASE_URL 动态注入，不在 alembic.ini 中硬编码。
- target_metadata 指向 server.models.database.Base.metadata，支持 --autogenerate。
- 支持 online 和 offline 两种模式。
"""

from __future__ import annotations

import os
import sys
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

# 保证 `server.*` 可被 import（alembic 在项目根目录执行）
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from server.config import DATABASE_URL  # noqa: E402
from server.models.database import Base  # noqa: E402
from server.models import models as _models  # noqa: E402, F401  确保模型被注册到 Base.metadata

# Alembic Config 对象
config = context.config

# 动态注入 DSN，避免写死在 alembic.ini
config.set_main_option("sqlalchemy.url", DATABASE_URL)

# 配置日志
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# 目标元数据（供 --autogenerate 扫描）
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Offline 模式：生成 SQL 文本而非真正执行。"""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        compare_server_default=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Online 模式：通过 Engine 执行迁移。"""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
            compare_server_default=True,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
