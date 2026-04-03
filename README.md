# 🧠 Mem0 Dashboard — 记忆管理可视化平台

> 基于 [Mem0](https://github.com/mem0ai/mem0) 构建的**全功能记忆管理可视化平台**，集成向量记忆 + 图谱记忆双引擎，支持记忆的增删改查、AI 智能分类、语义搜索、知识图谱可视化、数据导入导出、请求日志监控等功能。

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
| 📦 **数据导出** | 记忆数据 JSON 导出，支持按用户/分类/状态筛选 |
| ⚙️ **系统设置** | 后端连接状态检测、配置信息展示 |

---

## 📋 系统架构

```
本地电脑 (Windows)                                  云服务器 (Linux + GPU)
┌──────────────────────────────────────────┐       ┌──────────────────────────────────┐
│                                          │       │  Ollama 服务 (:11434)            │
│  Next.js 前端 (:3000)                    │       │  ├── qwen2.5:7b (LLM)           │
│  ├── 仪表盘（统计图表）                    │       │  └── nomic-embed-text (嵌入模型)  │
│  ├── 记忆管理（CRUD + 批量导入）           │       └──────────────────────────────────┘
│  ├── 语义搜索                             │                       ▲
│  ├── 用户管理                             │                       │ HTTP
│  ├── 请求日志                             │       ┌──────────────────────────────────┐
│  ├── 图谱记忆（力导向图可视化）             │       │  Neo4j 图数据库 (:7687)          │
│  ├── 数据导出                             │       │  └── 知识图谱存储                 │
│  └── 系统设置                             │       └──────────────────────────────────┘
│           ↓                              │                       ▲
│  FastAPI 后端 (:8080)                    │───── HTTP/Bolt ───────┘
│  ├── Mem0 记忆引擎（向量记忆）             │
│  ├── Qdrant 向量数据库（本地文件模式）      │
│  ├── Neo4j Driver（图谱记忆）             │
│  └── SQLite（访问日志 + 请求日志 + 历史）  │
└──────────────────────────────────────────┘
```

### 目录结构

```
demo2/
├── server.py                  # FastAPI 后端服务（2100+ 行，包含全部 API）
├── start_server.bat           # 后端一键启动脚本 (Windows)
├── access_logs.db             # SQLite 数据库（访问日志、请求日志、修改历史）
├── qdrant_data/               # Qdrant 向量数据库本地存储（自动生成）
├── .venv/                     # Python 虚拟环境
├── README.md                  # 本文档
└── mem0-dashboard/            # Next.js 前端项目
    ├── .env.local             # 前端环境变量
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
        │   ├── data-transfer/     # 数据导出页
        │   └── settings/          # 系统设置页
        ├── components/        # UI 组件
        │   ├── layout/            # 布局（侧边栏、顶栏）
        │   ├── memories/          # 记忆相关组件（表格、筛选、编辑、导入等）
        │   ├── dashboard/         # 仪表盘图表组件
        │   ├── graph/             # 图谱可视化组件（力导向图）
        │   ├── shared/            # 共享组件（访问日志、关联记忆）
        │   └── ui/                # 基础 UI 组件（Radix UI 封装）
        ├── hooks/             # 自定义 Hooks
        ├── lib/               # 工具库
        │   ├── api/               # API 客户端 & 类型定义
        │   ├── constants.ts       # 分类/状态常量（20 种分类 + 3 种状态）
        │   └── utils.ts           # 工具函数
        ├── store/             # Zustand 状态管理
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

### 云服务器要求

- 一台带 **NVIDIA GPU** 的 Linux 服务器（推荐 Tesla T4 16GB 或以上）
- 已安装 **Ollama** 并拉取以下模型：
  - `qwen2.5:7b` — LLM 模型（约 4.7GB）
  - `nomic-embed-text` — 嵌入模型（约 274MB）
- Ollama 服务监听 `0.0.0.0:11434`，防火墙已放行
- （可选）已安装 **Neo4j** 并监听 `bolt://0.0.0.0:7687`，用于图谱记忆功能

---

## 🚀 快速启动

### 1. 克隆项目 & 创建虚拟环境

```powershell
cd d:\Users\V_grhe\Desktop\ai-demo\demo2

# 创建 Python 虚拟环境
python -m venv .venv

# 激活虚拟环境
.\.venv\Scripts\Activate.ps1
```

### 2. 安装后端依赖

```powershell
pip install fastapi uvicorn mem0ai qdrant-client ollama neo4j requests
```

| 包名 | 用途 |
|------|------|
| `fastapi` + `uvicorn` | Web 框架 & ASGI 服务器 |
| `mem0ai` | Mem0 记忆管理引擎 |
| `qdrant-client` | Qdrant 向量数据库客户端 |
| `ollama` | Ollama Python SDK |
| `neo4j` | Neo4j 图数据库驱动（图谱记忆） |
| `requests` | HTTP 客户端（AI 自动分类调用） |

### 3. 配置后端

编辑 `server.py` 中的 `MEM0_CONFIG`，修改以下地址为你的云服务器 IP：

```python
MEM0_CONFIG = {
    "llm": {
        "provider": "ollama",
        "config": {
            "model": "qwen2.5:7b",
            "ollama_base_url": "http://<你的云服务器IP>:11434",  # ← 修改
        },
    },
    "embedder": {
        "provider": "ollama",
        "config": {
            "model": "nomic-embed-text",
            "ollama_base_url": "http://<你的云服务器IP>:11434",  # ← 修改
        },
    },
    "graph_store": {
        "provider": "neo4j",
        "config": {
            "url": "bolt://<你的云服务器IP>:7687",              # ← 修改
            "username": "neo4j",
            "password": "<你的Neo4j密码>",                       # ← 修改
        },
    },
    # ... 其他配置保持默认
}
```

### 4. 启动后端服务

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

### 5. 安装前端依赖

> ⚠️ 前端命令必须在 `mem0-dashboard` 子目录下执行！

```powershell
cd d:\Users\V_grhe\Desktop\ai-demo\demo2\mem0-dashboard
npm install
```

### 6. 配置前端环境变量

确认 `mem0-dashboard/.env.local` 文件：

```env
NEXT_PUBLIC_MEM0_API_URL=http://localhost:8080
```

> 默认指向本地后端 8080 端口，通常无需修改。

### 7. 启动前端服务

```powershell
cd d:\Users\V_grhe\Desktop\ai-demo\demo2\mem0-dashboard
npm run dev
```

启动成功后访问：**http://localhost:3000** 🎉

---

## 📡 API 接口一览

后端共提供 **25 个 RESTful API** 端点：

### 记忆管理（8 个）

| 方法 | 路径 | 说明 |
|------|------|------|
| `POST` | `/v1/memories/` | 添加记忆（支持 AI 自动分类） |
| `POST` | `/v1/memories/batch` | 批量导入记忆 |
| `GET` | `/v1/memories/` | 获取记忆列表（支持多维筛选） |
| `GET` | `/v1/memories/{id}/` | 获取单条记忆详情 |
| `PUT` | `/v1/memories/{id}/` | 更新记忆（内容/分类/状态） |
| `DELETE` | `/v1/memories/{id}/` | 删除单条记忆 |
| `DELETE` | `/v1/memories/` | 删除用户全部记忆 |
| `GET` | `/v1/memories/{id}/related/` | 获取语义关联记忆 |

### 搜索 & 历史（2 个）

| 方法 | 路径 | 说明 |
|------|------|------|
| `POST` | `/v1/memories/search/` | 语义搜索记忆 |
| `GET` | `/v1/memories/history/{id}/` | 获取记忆修改历史 |

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

### 健康检查（1 个）

| 方法 | 路径 | 说明 |
|------|------|------|
| `GET` | `/` | API 健康检查 |

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

## ⚙️ 配置说明

### 后端配置（`server.py`）

| 配置项 | 默认值 | 说明 |
|--------|--------|------|
| `MEM0_PORT`（环境变量） | `8080` | 后端监听端口 |
| `QDRANT_DATA_PATH` | `./qdrant_data` | Qdrant 数据存储目录 |
| `ACCESS_LOG_DB_PATH` | `./access_logs.db` | SQLite 日志数据库路径 |
| `llm.model` | `qwen2.5:7b` | LLM 模型名称 |
| `embedder.model` | `nomic-embed-text` | 嵌入模型名称 |
| `embedding_model_dims` | `768` | 嵌入向量维度（需与模型匹配） |
| `ollama_base_url` | `http://<IP>:11434` | Ollama 服务地址 |
| `graph_store.url` | `bolt://<IP>:7687` | Neo4j 连接地址 |
| `graph_store.username` | `neo4j` | Neo4j 用户名 |
| `graph_store.password` | — | Neo4j 密码 |

### 前端配置（`mem0-dashboard/.env.local`）

| 配置项 | 默认值 | 说明 |
|--------|--------|------|
| `NEXT_PUBLIC_MEM0_API_URL` | `http://localhost:8080` | 后端 API 地址 |

---

## 🛑 停止服务

在各终端中按 `Ctrl + C` 优雅退出。

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

`server.py` 中的 LLM/Embedder 配置仍在使用 OpenAI 提供商，请确认已正确配置为 `ollama`。

### 3. 添加记忆时响应很慢

- 检查 Ollama 服务：`curl http://<云服务器IP>:11434/api/tags`
- 确认本地能访问云服务器 11434 端口
- Ollama 首次加载模型到 GPU 需要几秒，后续请求会快很多

### 4. 图谱记忆页面显示"Neo4j 未连接"

- 确认 `server.py` 中 `graph_store` 配置正确
- 检查 Neo4j 服务是否运行：`curl http://<IP>:7474`
- 确认防火墙已放行 7687 端口（Bolt 协议）

### 5. 切换 Embedding 模型后数据异常

不同模型的向量维度不同，切换后需要：

```powershell
# 删除旧的向量数据
Remove-Item -Recurse -Force .\qdrant_data

# 修改 server.py 中的 embedding_model_dims 为新模型的维度
# 然后重启后端服务
```

### 6. `watchfiles` 不断输出 `change detected`

这是 uvicorn 热重载监控日志，不影响使用。可在 `server.py` 的 `uvicorn.run()` 中设置 `reload=False` 关闭。

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
| 日志存储 | SQLite | 访问日志、请求日志、修改历史 |
| LLM 服务 | Ollama (qwen2.5:7b) | 记忆提取与智能分类 |
| 嵌入模型 | Ollama (nomic-embed-text) | 768 维向量嵌入 |
| 运行环境 | Python 3.10+ / Node.js 18+ | 后端 / 前端 |
