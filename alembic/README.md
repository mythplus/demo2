# 数据库迁移（Alembic）

本项目使用 [Alembic](https://alembic.sqlalchemy.org/) 管理 PostgreSQL 记忆元数据的表结构迁移，替代原有 `Base.metadata.create_all(bind=engine)` 裸建表的方式。

## 为什么需要 Alembic

`create_all` 只会创建**不存在**的表，**不会**修改已有表结构。一旦给 `MemoryMeta` 等模型增删字段（例如加 `deleted_at` 软删除列），启动日志不会报任何错误，但新字段永远不会出现在生产库，直到运行时写入才会崩溃。

Alembic 提供：

- 版本化的迁移历史（每次结构变更都有独立 revision）
- 基于 ORM 的 `--autogenerate` 自动生成迁移脚本
- `upgrade` / `downgrade` 双向迁移能力
- 每个环境（dev / staging / prod）通过 `alembic current` 明确当前版本

## 常用命令

在项目根目录执行：

```bash
# 生成新的迁移脚本（根据 ORM 变更自动生成）
alembic revision --autogenerate -m "add deleted_at to memory_meta"

# 执行迁移到最新版本
alembic upgrade head

# 回滚一个版本
alembic downgrade -1

# 查看当前版本
alembic current

# 查看迁移历史
alembic history --verbose
```

## DSN 来源

`alembic/env.py` 从 `server.config.DATABASE_URL` 动态读取连接串，**不在 `alembic.ini` 中硬编码**，与业务代码使用同一套环境变量：

- `DATABASE_URL`（推荐）
- 或 `POSTGRES_HOST` / `POSTGRES_PORT` / `POSTGRES_DB` / `POSTGRES_USER` / `POSTGRES_PASSWORD`

生产环境（`MEM0_ENV=production`）缺失关键变量会在 `config.py` 中 fail fast，迁移也无法启动。

## 首次接入既有生产库

如果生产库已经通过 `create_all` 创建了表（迁移引入前的历史遗留），首次使用 Alembic 时需要"打基线"：

1. 在代码中新增空迁移（或使用自带的 `20260421_0000_0001_initial_baseline.py`），标记为当前 schema 的起点；
2. 在生产库执行 `alembic stamp head`，告知 Alembic「当前数据库版本已经是 head」，**不真正执行 SQL**；
3. 之后再进行的 ORM 变更，通过 `alembic revision --autogenerate` 生成差异迁移，正常走 `alembic upgrade head`。

## 与 `init_db()` 的关系

启动流程调整为：

- **开发环境**：`init_db()` 继续走 `create_all()` 方便快速起服务，同时建议本地也跑 `alembic upgrade head` 保持一致。
- **生产环境**：由部署流水线（蓝盾）在启动前执行 `alembic upgrade head`，服务启动时 `init_db()` 仅做健康检查，不再 `create_all`。

详见 `server/models/database.py` 中 `init_db()` 的实现。
