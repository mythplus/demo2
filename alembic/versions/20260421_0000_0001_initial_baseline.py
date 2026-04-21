"""initial baseline

首个迁移脚本。用于给既有生产库打基线——结构已经通过历史 `create_all` 创建完成，
所以 upgrade/downgrade 均为空操作。后续的 ORM 变更通过 `alembic revision --autogenerate`
生成差异迁移即可正常执行。

全新环境：执行 `alembic upgrade head` 会依次执行此脚本 + 后续所有差异迁移；
已有数据库：执行一次 `alembic stamp head` 将当前状态登记为 head，再进行后续增量迁移。

Revision ID: 0001
Revises:
Create Date: 2026-04-21 00:00:00.000000
"""
from typing import Sequence, Union

# revision identifiers, used by Alembic.
revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 基线迁移，不做任何结构变更。
    # 真实的表结构由 server/models/models.py 的 ORM 定义 + create_all / 人工迁移维护。
    pass


def downgrade() -> None:
    pass
