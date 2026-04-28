# Mem0 Dashboard — 后端服务

> 基于 [Mem0](https://github.com/mem0ai/mem0) 的记忆管理平台**后端仓库** —— 为 AI 应用提供可审计、可治理的长期记忆 API 基础设施。

提供记忆的**增删改查、语义检索、图谱管理、AI 对话、批量导入导出、Webhook 通知、访问审计**等全链路 RESTful API 能力。

> ⚠️ **前端已拆分为独立仓库**，本仓库仅包含 FastAPI 后端服务。前端项目请参见对应的前端仓库。

## 📋 目录

1. [核心特性](#-核心特性)
2. [系统架构](#️-系统架构)
3. [目录结构](#-目录结构)
4. [快速开始](#-快速开始)
   - [本地开发](#方式一本地开发推荐日常开发)
   - [Docker 部署](#方式二docker-部署推荐生产)
5. [配置说明](#️-配置说明)
6. [API 接口](#-api-接口)
7. [安全机制](#-安全机制)
8. [测试](#-测试)
9. [常见问题](#-常见问题)

---

## ✨ 核心特性

| 模块 | 能力 | 说明 |
|------|------|------|
| 🧠 **记忆管理** | 增删改查 / 批量操作 / 分类标签 / 修改历史 | AI 自动分类（20 个分类）、软删除、审计日志 |
| 🔍 **语义检索** | 向量相似度搜索 / 关联记忆推荐 | 基于 Qdrant + nomic-embed-text |
| 💬 **Playground** | AI 对话 + 记忆增强 / SSE 流式输出 | 流式 API 端点，支持前端对接 |
| 🕸️ **图谱记忆** | 实体与关系管理 / 图谱搜索 | Neo4j 图数据库 |
| 📊 **统计接口** | 统计概览 / 趋势数据 / 分类分布 | 记忆/用户/请求三维统计 API |
| 📥 **数据导入导出** | JSON / CSV 双向流转 / 筛选导出 | 支持用户/分类/时间多维筛选 |
| 🪝 **Webhook** | 7 种事件通知 / 企业微信机器人 / Fernet 加密 | 防 SSRF、自动重试、签名验证 |
| 📝 **审计日志** | 访问日志 / 请求日志 / 变更历史 / 速率限制 | PostgreSQL 统一存储，小时/天双粒度统计 |
| 🔐 **认证与安全** | API Key / CORS / 速率限制 / 生产强制鉴权 | 生产环境禁止无鉴权启动 |

---

## 🏗️ 系统架构

```
┌─────────────────────────────────────────────────────────────────┐
│              前端应用（独立仓库）/ 其他 API 消费者                  │
└──────────────────────────┬──────────────────────────────────────┘
                           │ HTTPS / HTTP
                 ┌─────────▼─────────┐
                 │  Nginx 反向代理    │  ← SSL 终止 + API 代理
                 │  (生产环境)        │
                 └─────────┬─────────┘
                           │
                  ┌────────▼────────┐
                  │  FastAPI 后端    │
                  │  (Port 8080)    │
                  │                 │
                  │ • 中间件链：     │
                  │   Auth/Rate/Log │
                  │ • 8 个路由模块   │
                  │ • 异步任务队列   │
                  │                 │
                  └────────┬────────┘
                           │
     ┌─────────────────┬───┴───────────────┬──────────────────────┐
     │                 │                   │                      │
┌────▼──────┐   ┌──────▼──────┐   ┌───────▼───────┐    ┌────────▼───────┐
│ Qdrant    │   │   Ollama    │   │  PostgreSQL   │    │     Neo4j      │
│ (远程)    │   │  LLM + Emb  │   │  (元数据+日志) │    │  (Graph Mem)   │
│ 向量存储  │   │ qwen2.5:7b  │   │  Alembic 迁移 │    │   5.15 + APOC  │
│           │   │ nomic-embed │   │               │    │                │
└───────────┘   └─────────────┘   └───────────────┘    └────────────────┘
                                  ┌───────────────┐
                                  │    SQLite     │
                                  │ (访问日志/限流) │
                                  └───────────────┘
```

### 核心数据流

```mermaid
graph LR
    A[API 请求] --> B[FastAPI 中间件链<br/>Auth/Rate/Log]
    B --> C[Mem0 SDK]
    C --> D[Ollama LLM<br/>提取事实]
    D --> E[Ollama Embedder<br/>向量化]
    E --> F[Qdrant 远程<br/>向量存储]
    C --> G[PostgreSQL<br/>元数据+变更日志]
    C --> H[Neo4j<br/>实体关系]
    F & G & H --> I[API 响应]
```

---

## 📁 目录结构

```
demo2/
├── server/                       # 后端 FastAPI 服务
│   ├── app.py                    # FastAPI 应用组装（中间件、路由注册、生命周期）
│   ├── main.py                   # 启动入口（uvicorn 配置）
│   ├── config.py                 # 配置加载（YAML + 环境变量替换 + 分类定义）
│   ├── middleware/               # 中间件
│   │   ├── auth.py               # API Key 认证（Bearer / X-API-Key）
│   │   ├── rate_limit.py         # 速率限制（SQLite 计数器）
│   │   ├── request_id.py         # 请求 ID 追踪
│   │   └── request_log.py        # 请求日志记录
│   ├── models/                   # ORM 数据模型
│   │   ├── database.py           # SQLAlchemy 引擎 + 会话（PostgreSQL）
│   │   ├── models.py             # MemoryMeta / Category
│   │   └── schemas.py            # Pydantic 请求/响应模型
│   ├── routes/                   # 8 个路由模块（46 个端点）
│   │   ├── memories.py           # 记忆 CRUD + 批量操作
│   │   ├── search.py             # 语义检索 + 关联记忆
│   │   ├── stats.py              # 统计概览
│   │   ├── logs.py               # 访问/请求日志
│   │   ├── graph.py              # 图谱实体/关系管理
│   │   ├── playground.py         # AI 对话（流式 SSE）
│   │   ├── webhooks.py           # Webhook 管理
│   │   └── health.py             # 健康检查 + 配置信息 + 服务测试
│   ├── services/                 # 业务服务层
│   │   ├── memory_service.py     # Mem0 SDK 封装 + 向量检索 + 分类归一化
│   │   ├── meta_service.py       # PostgreSQL 关系库聚合查询
│   │   ├── graph_service.py      # Neo4j 连接池
│   │   ├── log_service.py        # 日志异步写入队列 + 变更历史
│   │   ├── webhook_service.py    # Webhook 派发 + Fernet 加密
│   │   └── background_tasks.py   # 后台任务管理
│   ├── utils/                    # 公共工具
│   │   └── datetime_utils.py     # UTC/北京时间转换工具
│   └── scripts/
│       └── migrate_to_relational_db.py  # 数据迁移脚本
│
├── tests/                        # 后端测试（pytest）
│   ├── conftest.py
│   ├── test_memories_crud.py
│   ├── test_memories_search.py
│   ├── test_graph.py
│   ├── test_middleware.py
│   ├── test_access_logs.py
│   ├── test_request_logs.py
│   ├── test_stats.py
│   ├── test_health.py
│   └── test_config.py
│
├── nginx/
│   ├── nginx.conf                # Nginx 反代配置（HTTPS + API Key 注入）
│   └── ssl/                      # SSL 证书目录
│
├── alembic/                      # 数据库迁移（Alembic）
│   ├── env.py                    # 迁移环境配置
│   ├── versions/                 # 迁移版本脚本
│   └── README.md                 # 迁移使用说明
│
├── .ci/                          # CI/CD 流水线配置
│   └── stream.yml                # 蓝盾流水线配置
│
├── access_logs.db                # SQLite 访问日志（轻量级，独立于 PG）
├── rate_limit.db                 # SQLite 速率限制
├── alembic.ini                   # Alembic 配置
├── config.yaml / .example        # 主配置文件
├── .env / .env.example           # 环境变量
├── docker-compose.yml            # Docker 部署（开发）
├── docker-compose.prod.yml       # Docker 生产部署
├── Dockerfile                    # 后端镜像
├── requirements.txt              # Python 依赖
├── requirements-dev.txt          # 开发依赖（pytest 等）
├── server.py                     # 开发入口
├── start_server.bat              # Windows 后端启动脚本
└── pytest.ini                    # pytest 配置
```

---

## 🚀 快速开始

### 前置依赖

| 组件 | 版本 | 用途 |
|------|------|------|
| **Python** | 3.10+ | 后端运行时 |
| **PostgreSQL** | 14+ | 元数据 + 变更日志存储 |
| **Ollama** | 最新版 | LLM + Embedder 推理服务 |
| **Qdrant** | 1.7+ | 向量数据库（远程模式） |
| **Neo4j** | 5.x | 图谱数据库（可选，Docker 自动启动） |

**首次安装 Ollama 后拉取模型**：

```bash
ollama pull qwen2.5:7b
ollama pull nomic-embed-text
```

---

### 方式一：本地开发（推荐日常开发）

#### 1. 克隆项目并安装依赖

```bash
git clone <repo-url> demo2 && cd demo2

# 创建虚拟环境并安装依赖
python -m venv .venv
.\.venv\Scripts\activate              # Windows
# source .venv/bin/activate           # Linux / macOS
pip install -r requirements.txt
```

#### 2. 准备配置文件

```bash
copy .env.example .env                # Windows
copy config.yaml.example config.yaml
# 编辑 .env，填入 OLLAMA_BASE_URL / NEO4J_PASSWORD / MEM0_API_KEY
```

#### 3. 启动服务

**方案 A：一键启动（Windows）**

```bash
.\.venv\Scripts\activate
.\start_server.bat
```

**方案 B：手动启动**

```bash
# 启动后端（端口 8080）
python -m uvicorn server.app:app --host 0.0.0.0 --port 8080 --reload
```

#### 4. 访问

- API 文档：http://localhost:8080/docs
- 健康检查：http://localhost:8080/

---

### 方式二：Docker 部署（推荐生产）

#### 1. 配置环境变量

```bash
cp .env.example .env
cp config.yaml.example config.yaml
# 编辑 .env：设置 MEM0_API_KEY、NEO4J_PASSWORD、CORS_ORIGINS
```

#### 2. 生成 SSL 自签名证书（仅用于本地测试）

```bash
cd nginx/ssl
bash generate-cert.sh           # 生成 server.crt / server.key
cd ../..
```

#### 3. 启动

```bash
docker-compose up -d
```

会启动以下容器：

| 服务 | 端口 | 说明 |
|------|------|------|
| `mem0-nginx` | 80 / 443 | HTTPS 终止 + API 反代 |
| `mem0-backend` | 8080（内网） | FastAPI |
| `mem0-neo4j` | 7474 / 7687（内网） | 图数据库 |

#### 4. 访问

- https://localhost（接受自签证书）

#### 5. 常用命令

```bash
docker-compose logs -f backend     # 查看后端日志
docker-compose restart backend     # 重启后端
docker-compose down                # 停止全部
docker-compose down -v             # 停止并清除数据卷
```

---

## ⚙️ 配置说明

配置采用**三层体系**，优先级：`环境变量 > .env > config.yaml`

### 1. `.env` 环境变量

| 变量 | 说明 | 示例 |
|------|------|------|
| `OLLAMA_BASE_URL` | Ollama 服务地址 | `http://localhost:11434` |
| `OLLAMA_MODEL` | LLM 模型 | `qwen2.5:7b` |
| `EMBED_MODEL` | 嵌入模型 | `nomic-embed-text` |
| `DATABASE_URL` | PostgreSQL 完整连接串（优先级最高） | `postgresql://user:pass@host:5432/mem0` |
| `POSTGRES_HOST` | PG 主机 | `localhost` |
| `POSTGRES_PORT` | PG 端口 | `5432` |
| `POSTGRES_USER` | PG 用户名 | `postgres` |
| `POSTGRES_PASSWORD` | PG 密码（**生产必填**） | `your_password` |
| `POSTGRES_DB` | PG 数据库名 | `mem0` |
| `QDRANT_HOST` | Qdrant 远程地址 | `localhost` |
| `QDRANT_PORT` | Qdrant 端口 | `6333` |
| `QDRANT_API_KEY` | Qdrant API Key（可选） | `your_qdrant_key` |
| `NEO4J_URL` | Neo4j 连接 | `bolt://localhost:7687` |
| `NEO4J_USER` / `NEO4J_PASSWORD` | Neo4j 凭据 | `neo4j` / `your_password` |
| `MEM0_API_KEY` | **API 认证密钥（生产必填）** | `mem0-xxx-yyy` |
| `WEBHOOK_SECRET_KEY` | Webhook secret 加密密钥（可选） | `base64-fernet-key` |
| `CORS_ORIGINS` | CORS 白名单 | `http://localhost:3000` |
| `MEM0_PORT` | 后端端口 | `8080` |
| `MEM0_ENV` | 环境模式 | `development` / `production` |
| `MEM0_WORKERS` | 生产 Worker 数 | `2` |

### 2. `config.yaml` 主配置

支持 `${ENV_VAR}` 语法引用环境变量：

```yaml
llm:
  provider: "ollama"
  config:
    model: "qwen2.5:7b"
    ollama_base_url: "${OLLAMA_BASE_URL}"
    temperature: 0.1
    max_tokens: 8192

embedder:
  provider: "ollama"
  config:
    model: "nomic-embed-text"
    ollama_base_url: "${OLLAMA_BASE_URL}"

vector_store:
  provider: "qdrant"
  config:
    collection_name: "mem0"
    embedding_model_dims: 768
    host: "${QDRANT_HOST}"
    port: ${QDRANT_PORT}
    api_key: "${QDRANT_API_KEY}"

graph_store:
  provider: "neo4j"
  config:
    url: "${NEO4J_URL}"
    username: "${NEO4J_USER}"
    password: "${NEO4J_PASSWORD}"

security:
  api_key: "${MEM0_API_KEY}"
  webhook_secret_key: "${WEBHOOK_SECRET_KEY}"
  cors_origins: "${CORS_ORIGINS}"
  rate_limit: 60              # 每分钟请求数，0 表示不限
```

### 3. 前端配置（独立仓库）

前端已拆分为独立仓库，请参见前端仓库的 `.env.local` 配置说明。关键配置项：

```env
NEXT_PUBLIC_MEM0_API_URL=http://localhost:8080
NEXT_PUBLIC_MEM0_API_KEY=mem0-xxx-yyy        # 必须与后端一致
```

> ⚠️ **生产环境** 建议不设置 `NEXT_PUBLIC_MEM0_API_URL`，由前端同源走 Nginx 反代，由 Nginx 注入 API Key，**不向浏览器暴露密钥**。

---

## 🎯 API 能力概览

> 以下为后端提供的核心 API 能力，前端 UI 请参见前端独立仓库。

### 1️⃣ 记忆 CRUD

- 添加记忆（AI 自动分类，20 个分类）
- 批量导入 / 批量删除
- 多维筛选：搜索 / 用户 / 分类 / 日期 / 排序
- 编辑：支持重新分类、内容修改
- 修改历史对比
- 软删除 + 硬删除用户

### 2️⃣ 语义检索

- 向量相似度搜索 + 相关度分数
- 用户范围限定
- 关联记忆推荐

### 3️⃣ Playground — AI 对话

- SSE 流式输出端点
- 记忆增强：对话前自动检索 Top-K 相关记忆作为上下文
- 自动学习：对话后提取关键信息存入记忆库

### 4️⃣ 图谱记忆

- 实体/关系 CRUD
- 按用户、关系类型、关键词筛选
- 关系类型分布统计

### 5️⃣ 统计与日志

- 全局统计：记忆总数 / 用户总数 / 今日新增
- 请求日志：按类型分类（添加/搜索/更新/删除/对话）
- 访问日志：单条记忆级别审计
- 趋势数据：支持小时/天双粒度

### 6️⃣ 数据导入导出

- 导出：JSON（完整备份） / CSV（Excel 可读）
- 分页导出：每次拉取 200 条，避免大数据量超时
- 筛选导出：用户 + 时间范围
- 导入：支持两种 JSON 格式（标准导出 / 简单数组）

### 7️⃣ Webhooks

- 7 种事件：记忆 ADD/UPDATE/DELETE/SEARCH、用户硬删除、批量导入/删除
- 支持企业微信群机器人 URL
- Fernet 加密存储 Secret
- SSRF 防护 + 一键测试

### 8️⃣ 系统与健康

- 测试 LLM / Embedder 连接
- 查看完整配置信息（脱敏处理）
- 深度健康检查（Ollama / Qdrant / Neo4j / PostgreSQL）

---

## 📡 API 接口

**共 46 个 RESTful 端点**，按模块划分：

### 记忆管理（15 个）

| 方法 | 路径 | 说明 |
|------|------|------|
| `POST` | `/v1/memories/` | 添加记忆（AI 分类） |
| `POST` | `/v1/memories/batch` | 批量导入 |
| `POST` | `/v1/memories/batch-import-notify` | 批量导入完成通知 |
| `POST` | `/v1/memories/batch-delete` | 批量删除 |
| `GET` | `/v1/memories/` | 列表（筛选 + 分页） |
| `GET` | `/v1/memories/ids/` | ID 列表 |
| `GET` | `/v1/memories/users/` | 用户汇总 |
| `GET` | `/v1/memories/summary/` | 首页摘要 |
| `GET` | `/v1/memories/{id}/` | 单条详情 |
| `PUT` | `/v1/memories/{id}/` | 更新（内容/分类/AI 重分类） |
| `DELETE` | `/v1/memories/{id}/` | 删除单条 |
| `DELETE` | `/v1/memories/` | 清空用户记忆 |
| `DELETE` | `/v1/memories/user/{user_id}/hard-delete` | 硬删除用户 |
| `GET` | `/v1/memories/history/{id}/` | 修改历史 |
| `POST` | `/v1/memories/migrate-to-db/` | 迁移到关系库 |

### 语义检索（2 个）

| 方法 | 路径 | 说明 |
|------|------|------|
| `POST` | `/v1/memories/search/` | 语义搜索 |
| `GET` | `/v1/memories/{id}/related/` | 关联记忆 |

### 统计与日志（5 个）

| 方法 | 路径 | 说明 |
|------|------|------|
| `GET` | `/v1/stats/` | 全局统计 |
| `GET` | `/v1/access-logs/` | 访问日志 |
| `GET` | `/v1/memories/{id}/access-logs/` | 单条记忆访问日志 |
| `GET` | `/v1/request-logs/` | 请求日志 |
| `GET` | `/v1/request-logs/stats/` | 请求日志统计 |

### 图谱记忆（10 个）

| 方法 | 路径 | 说明 |
|------|------|------|
| `GET` | `/v1/graph/stats` | 图谱统计 |
| `GET` | `/v1/graph/entities` | 实体列表 |
| `GET` | `/v1/graph/relations` | 关系列表 |
| `GET` | `/v1/graph/user/{id}` | 用户子图 |
| `GET` | `/v1/graph/all` | 全量图谱 |
| `GET` | `/v1/graph/health` | 图谱健康 |
| `POST` | `/v1/graph/search` | 图谱搜索 |
| `DELETE` | `/v1/graph/entities/{name}` | 删除实体 |
| `DELETE` | `/v1/graph/relations` | 删除关系 |
| `DELETE` | `/v1/graph/user/{id}` | 删除用户子图 |

### Playground（2 个）

| 方法 | 路径 | 说明 |
|------|------|------|
| `POST` | `/v1/playground/chat` | 非流式对话 |
| `POST` | `/v1/playground/chat/stream` | 流式对话（SSE） |

### Webhooks（7 个）

| 方法 | 路径 | 说明 |
|------|------|------|
| `GET` | `/v1/webhooks/` | 列表 |
| `GET` | `/v1/webhooks/{id}` | 详情 |
| `POST` | `/v1/webhooks/` | 创建 |
| `PUT` | `/v1/webhooks/{id}` | 更新 |
| `DELETE` | `/v1/webhooks/{id}` | 删除 |
| `POST` | `/v1/webhooks/{id}/toggle` | 启用/禁用 |
| `POST` | `/v1/webhooks/{id}/test` | 测试触发 |

### 系统与健康（5 个）

| 方法 | 路径 | 说明 |
|------|------|------|
| `GET` | `/` | 健康检查（免认证） |
| `GET` | `/v1/config/info` | 配置信息（脱敏） |
| `GET` | `/v1/config/test-llm` | 测试 LLM |
| `GET` | `/v1/config/test-embedder` | 测试 Embedder |
| `GET` | `/v1/health/deep` | 深度健康检查 |

**交互式 Swagger 文档**：启动后访问 http://localhost:8080/docs

---

## 🔐 安全机制

### 1. 认证

- **API Key**：支持 `Authorization: Bearer <key>` 或 `X-API-Key: <key>`
- **生产强制**：`MEM0_ENV=production` 时必须设置 `MEM0_API_KEY`，否则拒绝启动
- **免认证路径**：`/`、`/docs`、`/redoc`、`/openapi.json`
- **恒定时间比较**：`hmac.compare_digest` 防定时攻击

### 2. CORS

- 白名单模式：`cors_origins` 配置允许来源
- `"*"` 通配仅开发环境可用

### 3. 速率限制

- 基于 SQLite 滑动窗口（默认 60 req/min）
- 按 IP 独立计数
- 配置项：`security.rate_limit`

### 4. Webhook 安全

- **Fernet 对称加密**存储 Secret
- **SSRF 防护**：
  - 拦截私有 IP、回环、链路本地、多播、保留地址
  - 阻断云元数据地址（AWS / GCP / Azure）
- **URL 校验**：仅 HTTP/HTTPS，长度限制
- **企业微信**：自动识别 qyapi.weixin.qq.com 做 URL 校验

### 5. 其他

- 生产环境错误信息**脱敏**（不暴露堆栈）
- 请求日志**异步队列写入**，不阻塞主链路
- 参数校验：Pydantic 模型 + 长度限制
- SQL 注入防护：SQLAlchemy ORM 参数化查询

### 6. 数据库连接串（P0-1）

- **禁止硬编码真实 IP / 密码**：`server/config.py` 的 `_build_database_url()` 默认值仅为 `localhost` + 空密码，只适用于本地开发。
- **生产 fail fast**：当 `MEM0_ENV=production` 时，若 `DATABASE_URL` 与 `POSTGRES_PASSWORD` 均未配置，服务启动时直接 `RuntimeError`，禁止静默连上非预期的环境。
- **必要时豁免**：生产确实需要连本机 PG，可显式设置 `POSTGRES_HOST=localhost` + `MEM0_ALLOW_LOCAL_PG=1` 双开关。
- **密钥轮换**：本仓库历史中若曾提交过明文密码，默认视为**已泄漏**，必须在 PG 侧立即轮换。
- **.env 管理**：`.env` 已通过 `.gitignore` 排除；若需团队共享，请走七彩石等配置中心注入环境变量，不要提交到 git。

### 7. 数据库迁移（P0-2）

- **`create_all` 只建不改**：新增 / 修改字段时 `init_db()` 不会触发 `ALTER`，旧表会缺字段直到运行时崩溃。
- **方案**：引入 [Alembic](https://alembic.sqlalchemy.org/) 管理迁移，详见 [`alembic/README.md`](./alembic/README.md)。
- **生产行为**：`init_db()` 在 `MEM0_ENV=production` 下**不再 create_all**，仅做 schema 健康检查；迁移由部署流水线（蓝盾）显式执行 `alembic upgrade head`。
- **开发行为**：继续走 `create_all` 快速起服务，但**任何 ORM 列变更都要同步生成迁移脚本**：

  ```bash
  alembic revision --autogenerate -m "add deleted_at to memory_meta"
  alembic upgrade head
  ```

- **首次接入既有生产库**：执行 `alembic stamp head` 打基线，再进行后续增量迁移。

---

## 🧪 测试

```bash
# 运行全部测试
pytest

# 运行特定模块
pytest tests/test_memories_crud.py -v

# 覆盖率报告
pytest --cov=server --cov-report=html
```

**测试覆盖模块**：CRUD / 搜索 / 图谱 / 中间件 / 访问日志 / 请求日志 / 统计 / 健康检查 / 配置

---

## ❓ 常见问题

<details>
<summary><strong>Q1: 启动后前端提示 "无法获取配置信息"？</strong></summary>

检查：
1. 后端是否在 8080 端口运行：`curl http://localhost:8080/`
2. 前端 `.env.local` 中的 `NEXT_PUBLIC_MEM0_API_KEY` 是否与后端 `.env` 中的 `MEM0_API_KEY` 一致
3. CORS 白名单是否包含前端地址（后端 `.env` 中的 `CORS_ORIGINS`）

</details>

<details>
<summary><strong>Q2: 添加记忆时超时或失败？</strong></summary>

- Ollama 是否运行：`ollama list`
- 模型是否已拉取：`ollama pull qwen2.5:7b && ollama pull nomic-embed-text`
- Neo4j 是否可连接（若启用 `graph_store`）

</details>

<details>
<summary><strong>Q3: Docker 中后端无法访问宿主机 Ollama？</strong></summary>

在 `.env` 中设置：`OLLAMA_BASE_URL=http://host.docker.internal:11434`
（Linux 下需额外在 `docker-compose.yml` 添加 `extra_hosts`）

</details>

<details>
<summary><strong>Q4: 导出的 CSV 中分类和时间显示英文？</strong></summary>

已在最新版修复：
- 分类自动映射为中文（如 `shopping` → `购物`）
- 时间转换为北京时间（UTC+8）`YYYY-MM-DD HH:mm:ss` 格式
- JSON 导出保持原始格式以支持无损重新导入

</details>

<details>
<summary><strong>Q5: 如何重置全部数据？</strong></summary>

```bash
# 本地开发
# 1. 清理 PostgreSQL 数据（连接到 PG 后执行）
#    DROP SCHEMA public CASCADE; CREATE SCHEMA public;
#    然后重新运行 alembic upgrade head
# 2. 清理本地 SQLite 文件
rm access_logs.db* rate_limit.db*

# Docker
docker-compose down -v
```

</details>

---

## 📝 技术栈

- **Web 框架**：FastAPI 0.135 + Uvicorn 0.42
- **记忆引擎**：Mem0 1.0.7
- **向量存储**：Qdrant 1.17（远程模式）
- **图数据库**：Neo4j 6.1 + langchain-neo4j 0.9
- **LLM 推理**：Ollama 0.6 + LiteLLM 1.82
- **LangGraph**：1.1+（Agent 编排）
- **ORM**：SQLAlchemy 2.0 + PostgreSQL + Alembic 迁移
- **配置**：PyYAML 6.0 + python-dotenv 1.2
- **加密**：cryptography 45.0
- **测试**：pytest 9
- **部署**：Docker Compose v3.8 + Nginx 1.25 (Alpine)

---

## 📄 License

本项目基于 MIT License 开源。

---

## 🔗 相关链接

- [Mem0 官方文档](https://docs.mem0.ai/)
- [Qdrant 文档](https://qdrant.tech/documentation/)
- [Neo4j 文档](https://neo4j.com/docs/)
- [Ollama](https://ollama.com/)
- [FastAPI](https://fastapi.tiangolo.com/)
