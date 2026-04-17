# 🧠 Mem0 Dashboard — 记忆管理可视化平台

> 基于 [Mem0](https://github.com/mem0ai/mem0) 构建的**全功能记忆管理可视化平台**，集成向量记忆 + 图谱记忆双引擎，支持记忆的增删改查、AI 智能分类、语义搜索、知识图谱可视化、AI 记忆增强对话（Playground）、Webhook 事件推送、数据导入导出、请求日志监控等功能。

---

## ✨ 核心功能

| 功能模块 | 说明 |
|---------|------|
| 📊 **仪表盘** | 记忆总量、用户数、分类分布图表、状态分布、近 30 天趋势 |
| 🧠 **记忆管理** | 完整 CRUD，支持 20 种分类标签、3 种状态（活跃/暂停/已删除）、AI 自动分类、批量导入 |
| 🔍 **语义搜索** | 基于向量嵌入的语义相似度搜索，支持按用户筛选 |
| 👥 **用户管理** | 用户列表、记忆数统计、用户详情页、按用户删除记忆 |
| 📋 **请求日志** | 全量 API 请求记录、类型分布统计、延迟监控、趋势图表 |
| 🕸️ **图谱记忆** | Neo4j 知识图谱可视化（力导向图）、实体/关系管理、图谱搜索 |
| 🤖 **Playground** | AI 记忆增强对话调试，基于 LangGraph 状态图，支持流式/非流式输出 |
| 🔔 **Webhook 管理** | Webhook 事件推送配置（CRUD + 测试），支持企业微信群机器人，secret 加密存储 |
| 📦 **数据导出** | 记忆数据 JSON 导出，支持按用户/分类/状态筛选 |
| ⚙️ **系统设置** | 后端连接状态检测、配置信息展示、深度健康检查 |

---

## 📋 系统架构

```
本地电脑 (Windows) / Docker 容器                     云服务器 (Linux + GPU)
┌──────────────────────────────────────────┐       ┌──────────────────────────────────┐
│                                          │       │  Ollama 服务 (:11434)            │
│  Next.js 前端 (:3000)                    │       │  ├── qwen2.5:7b (LLM)           │
│  ├── 仪表盘（统计图表）                    │       │  └── nomic-embed-text (嵌入模型)  │
│  ├── 记忆管理（CRUD + 批量导入）           │       └──────────────────────────────────┘
│  ├── 语义搜索                             │                       ▲
│  ├── 用户管理                             │                       │ HTTP
│  ├── 请求日志                             │       ┌──────────────────────────────────┐
│  ├── 图谱记忆（力导向图可视化）             │       │  Neo4j 图数据库 (:7687)          │
│  ├── Playground（AI 记忆增强对话）         │       │  └── 知识图谱存储                 │
│  ├── Webhook 管理                        │       └──────────────────────────────────┘
│  ├── 数据导出                             │                       ▲
│  └── 系统设置                             │                       │
│           ↓                              │                       │
│  Nginx 反向代理 (:80/:443)  ←── Docker ──│── HTTP/Bolt ──────────┘
│           ↓                              │
│  FastAPI 后端 (:8080)                    │
│  ├── Mem0 记忆引擎（向量记忆）             │
│  ├── Qdrant 向量数据库（本地文件模式）      │
│  ├── Neo4j Driver（图谱记忆）             │
│  ├── LangGraph 状态图（Playground 对话）   │
│  ├── Webhook 事件推送引擎                 │
│  ├── SQLAlchemy ORM（记忆元数据）          │
│  └── SQLite（访问日志 + 请求日志 + 历史）  │
└──────────────────────────────────────────┘
```

### 目录结构

```
demo2/
├── server.py                  # 启动入口（向后兼容，实际代码在 server/ 包中）
├── server/                    # 后端 Python 包（模块化架构）
│   ├── __init__.py                # 包入口 & 向后兼容导出层
│   ├── app.py                     # FastAPI 应用组装（生命周期、中间件、路由注册）
│   ├── config.py                  # 配置中心（加载 config.yaml + .env 环境变量替换）
│   ├── main.py                    # uvicorn 启动入口（开发/生产模式）
│   ├── middleware/                # 中间件
│   │   ├── auth.py                    # API Key 认证（Bearer Token）
│   │   ├── rate_limit.py              # 速率限制
│   │   └── request_log.py             # 请求日志记录
│   ├── models/                    # 数据模型
│   │   ├── database.py                # SQLAlchemy 数据库初始化（记忆元数据库）
│   │   ├── models.py                  # ORM 模型定义（MemoryMeta 等）
│   │   └── schemas.py                 # Pydantic 请求/响应模型
│   ├── routes/                    # API 路由
│   │   ├── graph.py                   # 图谱记忆接口
│   │   ├── health.py                  # 健康检查 + 配置信息 + 连接测试
│   │   ├── logs.py                    # 日志查询接口
│   │   ├── memories.py                # 记忆 CRUD 接口
│   │   ├── playground.py              # Playground AI 对话接口（LangGraph）
│   │   ├── search.py                  # 语义搜索接口
│   │   ├── stats.py                   # 统计接口
│   │   └── webhooks.py                # Webhook 管理接口
│   ├── scripts/                   # 脚本工具
│   │   └── migrate_to_relational_db.py    # Qdrant → 关系库迁移脚本
│   └── services/                  # 业务逻辑层
│       ├── background_tasks.py        # 后台任务托管（优雅关闭时等待完成）
│       ├── graph_service.py           # Neo4j 图谱服务
│       ├── log_service.py             # 日志服务（SQLite）
│       ├── memory_service.py          # 记忆服务（Mem0 + Qdrant）
│       ├── meta_service.py            # 记忆元数据服务（SQLAlchemy ORM）
│       └── webhook_service.py         # Webhook 服务（加密存储 + 事件推送）
├── config.yaml                # 后端配置文件（支持 ${ENV_VAR} 环境变量替换）
├── config.yaml.example        # 配置文件模板
├── .env                       # 环境变量文件（本地开发 + Docker 部署共用）
├── .env.example               # 环境变量模板
├── requirements.txt           # Python 依赖清单（含版本锁定）
├── Dockerfile                 # 后端 Docker 镜像（多阶段构建）
├── docker-compose.yml         # Docker Compose 一键部署（后端 + 前端 + Nginx + Neo4j）
├── nginx/                     # Nginx 反向代理配置
│   ├── nginx.conf                 # HTTPS 终止 + API 转发 + 静态资源缓存
│   └── ssl/                       # SSL 证书目录
├── start_server.bat           # 后端一键启动脚本 (Windows)
├── tests/                     # 后端测试
├── access_logs.db             # SQLite 数据库（访问日志、请求日志）
├── memory_meta.db             # SQLite 数据库（记忆元数据，SQLAlchemy 管理）
├── qdrant_data/               # Qdrant 向量数据库本地存储（自动生成）
├── .venv/                     # Python 虚拟环境
├── README.md                  # 本文档
└── mem0-dashboard/            # Next.js 前端项目
    ├── .env.local             # 前端环境变量
    ├── .env.example           # 前端环境变量模板
    ├── Dockerfile             # 前端 Docker 镜像（多阶段构建）
    ├── package.json           # 前端依赖
    ├── next.config.js         # Next.js 配置（含 API 代理 & webpack 缓存修复）
    └── src/
        ├── app/               # 页面路由
        │   ├── page.tsx           # 仪表盘（首页）
        │   ├── memories/          # 记忆管理页
        │   ├── memory/[id]/       # 记忆详情页
        │   ├── search/            # 语义搜索页
        │   ├── users/             # 用户管理页
        │   ├── users/[userId]/    # 用户详情页
        │   ├── requests/          # 请求日志页
        │   ├── graph-memory/      # 图谱记忆页
        │   ├── playground/        # Playground AI 对话页
        │   ├── webhooks/          # Webhook 管理页
        │   ├── data-transfer/     # 数据导出页
        │   └── settings/          # 系统设置页
        ├── components/        # UI 组件
        │   ├── layout/            # 布局（侧边栏、顶栏）
        │   ├── memories/          # 记忆相关组件（表格、筛选、编辑、导入等）
        │   ├── dashboard/         # 仪表盘图表组件
        │   ├── graph/             # 图谱可视化组件（力导向图）
        │   ├── shared/            # 共享组件（访问日志、关联记忆、用户选择器）
        │   └── ui/                # 基础 UI 组件（Radix UI 封装）
        ├── hooks/             # 自定义 Hooks
        ├── lib/               # 工具库
        │   ├── api/               # API 客户端 & 类型定义
        │   ├── constants.ts       # 分类/状态常量（20 种分类 + 3 种状态）
        │   └── utils.ts           # 工具函数
        ├── store/             # Zustand 状态管理
        │   ├── ui-store.ts        # UI 状态（侧边栏、面板等）
        │   └── preferences-store.ts   # 用户偏好设置
        └── types/             # TypeScript 类型声明
```

---

## 🔧 环境要求

| 依赖项 | 版本要求 | 说明 |
|--------|---------|------|
| **Python** | ≥ 3.10 | 后端运行环境 |
| **Node.js** | ≥ 18 | 前端运行环境 |
| **npm** 或 **Bun** | 最新版 | 前端包管理器 |
| **Ollama** | 最新版 | 部署在云服务器，提供 LLM 和 Embedding 服务 |
| **Neo4j** | ≥ 5.x（可选） | 部署在云服务器，提供图谱记忆存储 |
| **Docker** + **Docker Compose** | 最新版（可选） | 一键部署全部服务 |

### 云服务器要求

- 一台带 **NVIDIA GPU** 的 Linux 服务器（推荐 Tesla T4 16GB 或以上）
- 已安装 **Ollama** 并拉取以下模型：
  - `qwen2.5:7b` — LLM 模型（约 4.7GB）
  - `nomic-embed-text` — 嵌入模型（约 274MB）
- Ollama 服务监听 `0.0.0.0:11434`，防火墙已放行
- （可选）已安装 **Neo4j** 并监听 `bolt://0.0.0.0:7687`，用于图谱记忆功能

---

## 🚀 快速启动

### 方式一：本地开发

#### 1. 克隆项目 & 创建虚拟环境

```powershell
cd d:\Users\V_grhe\Desktop\ai-demo\demo2

# 创建 Python 虚拟环境
python -m venv .venv

# 激活虚拟环境
.\.venv\Scripts\Activate.ps1
```

#### 2. 安装后端依赖

```powershell
pip install -r requirements.txt
```

#### 3. 配置环境变量

复制环境变量模板并填入实际值：

```powershell
copy .env.example .env
```

编辑 `.env`：

```env
# Ollama 服务地址
OLLAMA_BASE_URL=http://<你的云服务器IP>:11434

# Neo4j 图数据库
NEO4J_URL=bolt://<你的云服务器IP>:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=<你的Neo4j密码>

# API 认证密钥（可选，为空则不启用认证）
MEM0_API_KEY=

# CORS 允许的来源
CORS_ORIGINS=http://localhost:3000,http://127.0.0.1:3000
```

#### 4. 配置后端

复制配置模板（配置文件通过 `${ENV_VAR}` 语法引用 `.env` 中的环境变量）：

```powershell
copy config.yaml.example config.yaml
```

> 💡 `config.yaml` 中的 `${OLLAMA_BASE_URL}`、`${NEO4J_URL}` 等占位符会自动从 `.env` 文件读取，通常无需手动修改 `config.yaml`。

#### 5. 启动后端服务

```powershell
# 方式一：直接运行
python server.py

# 方式二：使用启动脚本
.\start_server.bat
```

启动成功后会看到：

```
INFO:server:Mem0 Dashboard 后端服务启动中...
INFO:server:Qdrant 存储模式: 本地文件模式 (on_disk)
INFO:     Uvicorn running on http://0.0.0.0:8080
```

验证：

```powershell
curl http://localhost:8080/
# 返回: {"status":"ok","message":"Mem0 Dashboard API 运行中"}
```

#### 6. 安装前端依赖

> ⚠️ 前端命令必须在 `mem0-dashboard` 子目录下执行！

```powershell
cd mem0-dashboard
npm install
```

#### 7. 配置前端环境变量

确认 `mem0-dashboard/.env.local` 文件：

```env
# 后端 API 地址
NEXT_PUBLIC_MEM0_API_URL=http://localhost:8080

# API Key 认证密钥（需与后端 .env 中 MEM0_API_KEY 保持一致）
# 如果后端未配置 api_key，此项留空即可
NEXT_PUBLIC_MEM0_API_KEY=
```

#### 8. 启动前端服务

```powershell
npm run dev
```

启动成功后访问：**http://localhost:3000** 🎉

---

### 方式二：Docker Compose 一键部署

适用于生产环境或快速体验，一条命令启动全部服务（后端 + 前端 + Nginx + Neo4j）。

#### 1. 准备配置文件

```bash
# 复制环境变量模板
cp .env.example .env

# 复制后端配置模板
cp config.yaml.example config.yaml
```

编辑 `.env`，填入实际值（特别是 `OLLAMA_BASE_URL` 和 `MEM0_API_KEY`）。

> ⚠️ **生产环境必须设置 `MEM0_API_KEY`**，否则后端将拒绝启动。

#### 2. 生成 SSL 证书

```bash
# 使用自签名证书（开发/测试）
cd nginx/ssl
openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
  -keyout key.pem -out cert.pem \
  -subj "/CN=localhost"
cd ../..
```

#### 3. 启动服务

```bash
docker-compose up -d
```

#### 4. 访问

- **HTTPS 入口**：`https://localhost`（Nginx 反向代理）
- **HTTP 自动跳转**：`http://localhost` → `https://localhost`

#### 5. 查看日志

```bash
# 查看所有服务日志
docker-compose logs -f

# 查看单个服务
docker-compose logs -f backend
```

#### 6. 停止服务

```bash
docker-compose down
```

---

## 📡 API 接口一览

后端共提供 **35+ 个 RESTful API** 端点：

### 记忆管理（8 个）

| 方法 | 路径 | 说明 |
|------|------|------|
| `POST` | `/v1/memories/` | 添加记忆（支持 AI 自动分类） |
| `POST` | `/v1/memories/batch` | 批量导入记忆 |
| `GET` | `/v1/memories/` | 获取记忆列表（支持多维筛选 + 分页） |
| `GET` | `/v1/memories/{id}/` | 获取单条记忆详情 |
| `PUT` | `/v1/memories/{id}/` | 更新记忆（内容/分类/状态） |
| `DELETE` | `/v1/memories/{id}/` | 删除单条记忆 |
| `DELETE` | `/v1/memories/` | 删除用户全部记忆（同步清理关系库） |
| `GET` | `/v1/memories/{id}/related/` | 获取语义关联记忆 |

### 搜索 & 历史（3 个）

| 方法 | 路径 | 说明 |
|------|------|------|
| `POST` | `/v1/memories/search/` | 语义搜索记忆 |
| `GET` | `/v1/memories/history/{id}/` | 获取记忆修改历史 |
| `GET` | `/v1/memories/{id}/summary` | 获取记忆摘要信息 |

### 统计 & 日志（5 个）

| 方法 | 路径 | 说明 |
|------|------|------|
| `GET` | `/v1/stats/` | 全局统计（分类/状态分布、趋势） |
| `GET` | `/v1/access-logs/` | 全局访问日志 |
| `GET` | `/v1/memories/{id}/access-logs/` | 单条记忆访问日志 |
| `GET` | `/v1/request-logs/` | 请求日志列表 |
| `GET` | `/v1/request-logs/stats/` | 请求日志统计 |

### 图谱记忆（9 个）

| 方法 | 路径 | 说明 |
|------|------|------|
| `GET` | `/v1/graph/stats` | 图谱统计信息 |
| `GET` | `/v1/graph/entities` | 实体列表（支持搜索/筛选） |
| `GET` | `/v1/graph/relations` | 关系三元组列表 |
| `POST` | `/v1/graph/search` | 图谱搜索 |
| `GET` | `/v1/graph/user/{user_id}` | 用户子图数据（可视化） |
| `GET` | `/v1/graph/all` | 全量图谱数据（可视化） |
| `DELETE` | `/v1/graph/entities/{name}` | 删除实体及关联关系 |
| `DELETE` | `/v1/graph/relations` | 删除指定关系 |
| `GET` | `/v1/graph/health` | Neo4j 连接健康检查 |

### Playground AI 对话（2 个）

| 方法 | 路径 | 说明 |
|------|------|------|
| `POST` | `/v1/playground/chat` | 非流式对话（LangGraph 全流程） |
| `POST` | `/v1/playground/chat/stream` | 流式对话（SSE，混合 LangGraph + 手动流式） |

### Webhook 管理（7 个）

| 方法 | 路径 | 说明 |
|------|------|------|
| `GET` | `/v1/webhooks/` | 获取所有 Webhook 配置 |
| `GET` | `/v1/webhooks/{id}` | 获取单个 Webhook 配置 |
| `POST` | `/v1/webhooks/` | 创建 Webhook（含 URL 安全校验） |
| `PUT` | `/v1/webhooks/{id}` | 更新 Webhook |
| `DELETE` | `/v1/webhooks/{id}` | 删除 Webhook |
| `POST` | `/v1/webhooks/{id}/toggle` | 启用/禁用 Webhook |
| `POST` | `/v1/webhooks/{id}/test` | 发送测试推送 |

### 系统 & 健康检查（5 个）

| 方法 | 路径 | 说明 |
|------|------|------|
| `GET` | `/` | API 健康检查 |
| `GET` | `/v1/health/deep` | 深度健康检查（Qdrant + Ollama + Neo4j） |
| `GET` | `/v1/config/info` | 获取系统配置信息 |
| `GET` | `/v1/config/test-llm` | 测试 LLM 连接 |
| `GET` | `/v1/config/test-embedder` | 测试 Embedder 连接 |

---

## 🏷️ 记忆分类体系

系统内置 **20 种记忆分类**，支持手动选择和 AI 自动分类：

| 分类 | 标签 | 说明 |
|------|------|------|
| `personal` | 个人 | 家庭、朋友、家居、爱好、生活方式 |
| `relationships` | 关系 | 社交网络、伴侣、同事 |
| `preferences` | 偏好 | 喜好、厌恶、习惯 |
| `health` | 健康 | 体能、心理健康、饮食、睡眠 |
| `travel` | 旅行 | 旅行计划、通勤、行程 |
| `work` | 工作 | 职位、公司、项目、晋升 |
| `education` | 教育 | 课程、学位、证书、技能 |
| `finance` | 财务 | 收入、支出、投资、账单 |
| `projects` | 项目 | 待办事项、里程碑、截止日期 |
| `ai_ml_technology` | AI/技术 | 基础设施、算法、工具、研究 |
| `technical_support` | 技术支持 | Bug 报告、错误日志、修复 |
| `shopping` | 购物 | 购买、愿望清单、退货 |
| `legal` | 法律 | 合同、政策、法规、隐私 |
| `entertainment` | 娱乐 | 电影、音乐、游戏、书籍 |
| `messages` | 消息 | 邮件、短信、提醒、通知 |
| `customer_support` | 客户支持 | 工单、咨询、解决方案 |
| `product_feedback` | 产品反馈 | 评分、Bug 报告、功能请求 |
| `news` | 新闻 | 文章、头条、热门话题 |
| `organization` | 组织 | 会议、预约、日历 |
| `goals` | 目标 | 目标、KPI、长期规划 |

记忆状态：`active`（活跃）、`paused`（暂停）、`deleted`（已删除）

---

## 🔒 安全特性

| 特性 | 说明 |
|------|------|
| **API Key 认证** | 支持 Bearer Token 认证，生产环境强制启用 |
| **Webhook Secret 加密** | Webhook secret 使用 Fernet 对称加密存储，不再明文保存 |
| **URL 安全校验** | Webhook URL 创建/更新时校验目标主机，防止 SSRF 攻击 |
| **CORS 配置** | 可配置允许的跨域来源，生产环境建议限制为实际域名 |
| **速率限制** | 可配置每分钟最大请求数，防止滥用 |
| **HTTPS 终止** | Nginx 反向代理提供 SSL/TLS 加密 |
| **生产环境脱敏** | 生产环境下 IP 地址、错误详情自动脱敏 |
| **非 root 运行** | Docker 容器内以非 root 用户运行服务 |

---

## ⚙️ 配置说明

### 环境变量（`.env`）

| 变量名 | 默认值 | 说明 |
|--------|--------|------|
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Ollama 服务地址 |
| `OLLAMA_MODEL` | `qwen2.5:7b` | LLM 模型名称 |
| `EMBED_MODEL` | `nomic-embed-text` | 嵌入模型名称 |
| `NEO4J_URL` | `bolt://localhost:7687` | Neo4j 连接地址 |
| `NEO4J_USER` | `neo4j` | Neo4j 用户名 |
| `NEO4J_PASSWORD` | — | Neo4j 密码 |
| `MEM0_API_KEY` | `""` | API 认证密钥（生产环境必须设置） |
| `WEBHOOK_SECRET_KEY` | — | Webhook secret 加密密钥（可选，未设置时回退使用 api_key 派生） |
| `CORS_ORIGINS` | `*` | 允许的 CORS 来源（逗号分隔） |
| `MEM0_PORT` | `8080` | 后端监听端口 |
| `MEM0_ENV` | `development` | 运行环境（`production` / `development`） |
| `MEM0_WORKERS` | `2` | 生产环境 Worker 数量 |
| `HTTP_PORT` | `80` | Docker Nginx HTTP 端口 |
| `HTTPS_PORT` | `443` | Docker Nginx HTTPS 端口 |

### 后端配置（`config.yaml`）

配置文件支持 `${ENV_VAR}` 语法引用环境变量，适合生产环境部署。

| 配置项 | 说明 |
|--------|------|
| `llm.provider` | LLM 提供商（`ollama` / `openai`） |
| `llm.config.model` | LLM 模型名称 |
| `llm.config.ollama_base_url` | Ollama 服务地址 |
| `embedder.provider` | 嵌入模型提供商 |
| `embedder.config.model` | 嵌入模型名称 |
| `vector_store.config.embedding_model_dims` | 嵌入向量维度（需与模型匹配，默认 768） |
| `graph_store.config.url` | Neo4j 连接地址 |
| `security.api_key` | API Key 认证密钥 |
| `security.webhook_secret_key` | Webhook secret 加密密钥 |
| `security.cors_origins` | CORS 允许来源 |
| `security.rate_limit` | 每分钟最大请求数（0 为不限制） |

### 前端配置（`mem0-dashboard/.env.local`）

| 配置项 | 默认值 | 说明 |
|--------|--------|------|
| `NEXT_PUBLIC_MEM0_API_URL` | `http://localhost:8080` | 后端 API 地址 |
| `NEXT_PUBLIC_MEM0_API_KEY` | `""` | API Key（需与后端保持一致） |

> 💡 **生产环境（Docker 部署）**：前端通过 Nginx 同源反向代理访问后端，`NEXT_PUBLIC_MEM0_API_URL` 留空即可，无需将 API Key 暴露到浏览器。Nginx 会自动注入 `X-API-Key` 请求头。

---

## 🛑 停止服务

在各终端中按 `Ctrl + C` 优雅退出。后端会自动等待后台任务（如 Playground 记忆存储）完成后再关闭。

端口被占用时排查：

```powershell
# 查看端口占用
netstat -ano | findstr "8080"
netstat -ano | findstr "3000"

# 强制结束进程
taskkill /PID <PID> /F
```

---

## ❓ 常见问题

### 1. 页面显示"无法连接到 Mem0 API Server"

- 检查后端是否启动：访问 `http://localhost:8080/`
- 检查端口是否被占用：`netstat -ano | findstr "8080"`
- 首次加载时后端可能还在初始化，等几秒后刷新

### 2. 后端启动报 `OpenAIError: The api_key client option must be set`

`config.yaml` 中的 LLM/Embedder 配置仍在使用 OpenAI 提供商，请确认已正确配置为 `ollama`。

### 3. 生产环境启动报 `RuntimeError: 生产环境必须配置 security.api_key`

生产环境（`MEM0_ENV=production`）强制要求设置 API Key。请在 `.env` 文件中设置 `MEM0_API_KEY`。

### 4. 添加记忆时响应很慢

- 检查 Ollama 服务：`curl http://<云服务器IP>:11434/api/tags`
- 确认本地能访问云服务器 11434 端口
- Ollama 首次加载模型到 GPU 需要几秒，后续请求会快很多

### 5. 图谱记忆页面显示"Neo4j 未连接"

- 确认 `.env` 中 `NEO4J_URL`、`NEO4J_PASSWORD` 配置正确
- 检查 Neo4j 服务是否运行：`curl http://<IP>:7474`
- 确认防火墙已放行 7687 端口（Bolt 协议）

### 6. 切换 Embedding 模型后数据异常

不同模型的向量维度不同，切换后需要：

```powershell
# 删除旧的向量数据
Remove-Item -Recurse -Force .\qdrant_data

# 修改 config.yaml 中的 embedding_model_dims 为新模型的维度
# 然后重启后端服务
```

### 7. Docker 部署时 Ollama 连接失败

Docker 容器内无法直接访问宿主机的 `localhost`，需要使用 `host.docker.internal`：

```env
# .env 中设置
OLLAMA_BASE_URL=http://host.docker.internal:11434
```

### 8. 前端请求返回 401 Unauthorized

- 确认前端 `.env.local` 中的 `NEXT_PUBLIC_MEM0_API_KEY` 与后端 `.env` 中的 `MEM0_API_KEY` 一致
- Docker 部署时，Nginx 会自动注入 API Key，前端无需配置

---

## 📎 附录：云服务器部署

### 部署 Ollama

```bash
# 安装
curl -fsSL https://ollama.com/install.sh | sh

# 配置监听外网
sudo systemctl edit ollama
# 添加: Environment="OLLAMA_HOST=0.0.0.0"
sudo systemctl daemon-reload
sudo systemctl restart ollama

# 拉取模型
ollama pull qwen2.5:7b
ollama pull nomic-embed-text

# 验证
ollama list
```

### 部署 Neo4j（图谱记忆）

```bash
# Docker 方式部署
docker run -d \
  --name neo4j \
  -p 7474:7474 -p 7687:7687 \
  -e NEO4J_AUTH=neo4j/<你的密码> \
  -v neo4j_data:/data \
  neo4j:5

# 验证
curl http://localhost:7474
```

### 开放防火墙端口

```bash
# Ubuntu
sudo ufw allow 11434/tcp   # Ollama
sudo ufw allow 7687/tcp    # Neo4j Bolt
sudo ufw reload
```

> ⚠️ 云平台用户还需在**控制台安全组**中放行对应端口（TCP 入方向）。

---

## 📄 技术栈

| 层级 | 技术 | 说明 |
|------|------|------|
| 前端框架 | Next.js 14 | App Router + React 18 |
| UI 组件 | Radix UI + Tailwind CSS | 无障碍组件 + 原子化样式 |
| 图表库 | Recharts | 仪表盘统计图表 |
| 图谱可视化 | react-force-graph-2d | 力导向图渲染 |
| 状态管理 | Zustand + React Query | 全局状态 + 服务端缓存 |
| 后端框架 | FastAPI + Uvicorn | 异步 Web 框架 + ASGI 服务器 |
| 记忆引擎 | Mem0 | 向量记忆管理 |
| 向量数据库 | Qdrant（本地文件模式） | 嵌入向量存储与检索 |
| 图数据库 | Neo4j | 知识图谱存储（实体-关系） |
| ORM | SQLAlchemy | 记忆元数据管理（对齐 OpenMemory 官方架构） |
| 日志存储 | SQLite | 访问日志、请求日志 |
| AI 对话框架 | LangGraph | Playground 状态图驱动的对话流程 |
| Webhook 引擎 | 自研 | 事件推送 + Fernet 加密 + SSRF 防护 |
| LLM 服务 | Ollama (qwen2.5:7b) | 记忆提取与智能分类 |
| 嵌入模型 | Ollama (nomic-embed-text) | 768 维向量嵌入 |
| 异步 HTTP | httpx | 全局异步 HTTP 客户端 |
| 加密 | cryptography (Fernet) | Webhook secret 加密存储 |
| 反向代理 | Nginx | HTTPS 终止 + API 转发 + 静态资源缓存 |
| 容器化 | Docker + Docker Compose | 一键部署全部服务 |
| 运行环境 | Python 3.10+ / Node.js 18+ | 后端 / 前端 |

---

## 📝 更新日志

### v1.2.0（2026-04-17）— 功能增强 + 安全加固 + Docker 部署

**🤖 新功能**

| 功能 | 说明 |
|------|------|
| **Playground AI 对话** | 基于 LangGraph StateGraph 的记忆增强对话，支持流式/非流式输出，自动检索记忆 → LLM 生成 → 存储新记忆 |
| **Webhook 管理** | 完整的 Webhook CRUD + 测试推送，支持企业微信群机器人，secret 加密存储 |
| **深度健康检查** | `/v1/health/deep` 一次性检测 Qdrant / Ollama / Neo4j 连通性，适用于 K8s readinessProbe |
| **记忆元数据库** | 基于 SQLAlchemy ORM 的关系型元数据存储，对齐 OpenMemory 官方架构 |
| **后台任务托管** | 统一追踪 fire-and-forget 任务，应用关闭时优雅等待完成 |
| **Docker Compose 部署** | 一键部署后端 + 前端 + Nginx + Neo4j，支持 HTTPS |

**🔒 安全加固**

| 改进 | 说明 |
|------|------|
| 生产环境强制 API Key | `MEM0_ENV=production` 时必须配置 `security.api_key`，禁止无鉴权启动 |
| Webhook secret 加密 | 使用 Fernet 对称加密存储，旧明文 secret 自动迁移 |
| URL 安全校验 | Webhook URL 创建/更新时校验目标主机，防止内网/元数据服务 SSRF 攻击 |
| Nginx 注入 API Key | Docker 部署时 Nginx 自动注入认证头，前端无需暴露密钥 |
| 环境变量配置 | `config.yaml` 支持 `${ENV_VAR}` 语法，敏感信息不再硬编码 |

**🏗️ 架构改进**

| 改进 | 说明 |
|------|------|
| 双写一致性 | 记忆增删改操作同步写入 Qdrant + 关系库，`delete_all_memories` 同步清理关系库 |
| 前端 API 客户端重构 | 动态解析 API 基础地址，生产环境自动走同源反向代理 |
| Bearer Token 认证 | 前端认证头从 `X-API-Key` 统一为 `Authorization: Bearer` |
| 配置热加载 | `/v1/config/info` 实时从 `config.yaml` 读取，修改配置后刷新即可同步 |

### v1.1.0（2026-04-07）— 后端模块化重构

**🏗️ 架构重构**

将原来的单文件 `server.py`（2800+ 行）拆分为模块化的 `server/` Python 包：

| 变更 | 说明 |
|------|------|
| `server/config.py` | 配置中心：从 `config.yaml` 加载配置，支持 `${ENV_VAR}` 环境变量替换 |
| `server/app.py` | 应用组装：FastAPI 实例创建、生命周期管理、中间件 & 路由注册 |
| `server/main.py` | 启动入口：区分开发/生产模式（热重载 vs 多 Worker） |
| `server/middleware/` | 中间件层：API Key 认证、速率限制、请求日志 |
| `server/models/schemas.py` | 数据模型：所有 Pydantic 请求/响应 Schema |
| `server/routes/` | 路由层：按功能拆分为 6 个路由模块 |
| `server/services/` | 业务逻辑层：记忆服务、日志服务、图谱服务 |
| `server/__init__.py` | 向后兼容层：确保 `from server import app` 等旧导入仍然有效 |

**✅ 向后兼容**

- `python server.py` 启动方式不变
- `uvicorn server:app` 仍然有效
- 所有 API 端点路径和行为完全不变
- 测试文件中的 `from server import ...` 导入仍然有效

**🔧 其他改进**

- 配置从硬编码迁移到 `config.yaml` 文件，支持环境变量替换
- 生产模式支持多 Worker 进程（`MEM0_ENV=production`）
- 所有文件路径使用动态计算（基于 `__file__`），不再硬编码绝对路径
- 全局异常处理：生产环境隐藏内部错误详情
