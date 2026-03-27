# Mem0 Dashboard — 快速启动指南

> 基于 [Mem0](https://github.com/mem0ai/mem0) 的记忆管理可视化面板，支持记忆的增删改查、语义搜索、用户管理等功能。

---

## 📋 项目架构

```
本地电脑 (Windows)                              云服务器 (Linux + GPU)
┌────────────────────────────────────┐          ┌──────────────────────────────┐
│  Next.js 前端 (:3000)              │          │  Ollama 服务 (:11434)        │
│  ├── 概览仪表盘                     │          │  ├── qwen2.5:7b (LLM)       │
│  ├── 记忆管理 (CRUD)                │          │  └── nomic-embed-text (嵌入) │
│  ├── 语义搜索                       │          └──────────────────────────────┘
│  └── 用户管理                       │                      ▲
│           ↓                        │                      │
│  FastAPI 后端 (:8080)              │───── HTTP 请求 ──────┘
│  ├── Mem0 (记忆管理引擎)            │
│  └── Qdrant (本地文件向量数据库)     │
└────────────────────────────────────┘
```

### 目录结构

```
demo2/
├── server.py                  # FastAPI 后端服务入口
├── start_server.bat           # 后端一键启动脚本 (Windows)
├── qdrant_data/               # Qdrant 向量数据库本地存储目录（自动生成）
├── .venv/                     # Python 虚拟环境
└── mem0-dashboard/            # Next.js 前端项目
    ├── .env.local             # 前端环境变量配置
    ├── package.json           # 前端依赖
    ├── next.config.js         # Next.js 配置
    └── src/
        ├── app/               # 页面路由
        │   ├── page.tsx       # 概览仪表盘
        │   ├── memories/      # 记忆管理页
        │   ├── search/        # 语义搜索页
        │   ├── users/         # 用户管理页
        │   └── settings/      # 系统设置页
        ├── components/        # UI 组件
        └── lib/               # API 客户端 & 工具函数
```

---

## 🔧 环境要求

| 依赖项 | 版本要求 | 说明 |
|--------|---------|------|
| **Python** | ≥ 3.10 | 后端运行环境 |
| **Node.js** | ≥ 18 | 前端运行环境 |
| **Bun** (推荐) 或 npm | 最新版 | 前端包管理器 |
| **Ollama** | 最新版 | 部署在云服务器上，提供 LLM 和 Embedding 服务 |

### 云服务器要求

- 需要一台带 **NVIDIA GPU** 的 Linux 服务器（推荐 Tesla T4 16GB 或以上）
- 已安装 Ollama 并拉取以下模型：
  - `qwen2.5:7b` — LLM 模型（约 4.7GB）
  - `nomic-embed-text` — 嵌入模型（约 274MB）
- Ollama 服务监听 `0.0.0.0:11434`，防火墙/安全组已放行该端口

> 💡 如果还没有部署 Ollama，请参考下方 [附录：云服务器部署 Ollama](#附录云服务器部署-ollama) 章节。

---

## 🚀 快速启动

### 第一步：克隆项目 & 创建虚拟环境

```powershell
cd d:\Users\V_grhe\Desktop\ai-demo\demo2

# 创建 Python 虚拟环境
python -m venv .venv

# 激活虚拟环境
.\.venv\Scripts\Activate.ps1
```

### 第二步：安装后端依赖

```powershell
pip install fastapi uvicorn mem0ai qdrant-client ollama
```

核心依赖说明：

| 包名 | 用途 |
|------|------|
| `fastapi` + `uvicorn` | Web 框架 & ASGI 服务器 |
| `mem0ai` | Mem0 记忆管理引擎 |
| `qdrant-client` | Qdrant 向量数据库客户端 |
| `ollama` | Ollama Python SDK |

### 第三步：配置 Ollama 地址

编辑 `server.py` 中的 `MEM0_CONFIG`，将 `ollama_base_url` 修改为你的云服务器 IP：

```python
MEM0_CONFIG = {
    "vector_store": {
        "provider": "qdrant",
        "config": {
            "collection_name": "mem0",
            "embedding_model_dims": 768,        # nomic-embed-text 输出维度
            "path": QDRANT_DATA_PATH,
            "on_disk": True,
        },
    },
    "llm": {
        "provider": "ollama",
        "config": {
            "model": "qwen2.5:7b",
            "ollama_base_url": "http://<你的云服务器IP>:11434",  # ← 修改这里
            "temperature": 0.1,
        },
    },
    "embedder": {
        "provider": "ollama",
        "config": {
            "model": "nomic-embed-text",
            "ollama_base_url": "http://<你的云服务器IP>:11434",  # ← 修改这里
        },
    },
    "version": "v1.1",
}
```

### 第四步：启动后端服务

```powershell
# 方式一：直接运行
python server.py

# 方式二：使用启动脚本
.\start_server.bat
```

启动成功后会看到：

```
INFO:server:==================================================
INFO:server:Mem0 Dashboard 后端服务启动中...
INFO:server:Qdrant 存储模式: 本地文件模式 (on_disk)
INFO:server:==================================================
INFO:     Application startup complete.
INFO:     Uvicorn running on http://0.0.0.0:8080
```

验证后端是否正常：

```powershell
curl http://localhost:8080/
# 应返回: {"status":"ok","message":"Mem0 Dashboard API 运行中"}
```

### 第五步：安装前端依赖

**另开一个终端**，执行：

> ⚠️ **注意**：前端命令必须在 `mem0-dashboard` 子目录下执行，不是项目根目录！

```powershell
# 先切换到前端目录（重要！不要在 demo2 根目录执行）
cd d:\Users\V_grhe\Desktop\ai-demo\demo2\mem0-dashboard

# 使用 npm 安装
npm install

# 或使用 Bun 安装（需先安装 Bun：powershell -c "irm bun.sh/install.ps1 | iex"）
# bun install
```

### 第六步：配置前端环境变量

确认 `mem0-dashboard/.env.local` 文件内容：

```env
# Mem0 API Server 地址
NEXT_PUBLIC_MEM0_API_URL=http://localhost:8080
```

> 通常无需修改，默认指向本地后端 8080 端口。

### 第七步：启动前端服务

> ⚠️ **注意**：确保当前目录是 `mem0-dashboard`，不是项目根目录！

```powershell
# 确认在前端目录下
cd d:\Users\V_grhe\Desktop\ai-demo\demo2\mem0-dashboard

# 使用 npm 启动
npm run dev

# 或使用 Bun 启动（需先安装 Bun）
# bun --bun run dev
```

启动成功后访问：**http://localhost:3000** 🎉

---

## 🛑 停止服务

在各终端中按 `Ctrl + C` 优雅退出。

如果端口被占用，可以使用以下命令排查和清理：

```powershell
# 查看端口占用
netstat -ano | findstr "8080"
netstat -ano | findstr "3000"

# 强制结束进程（将 <PID> 替换为实际进程 ID）
taskkill /PID <PID> /F
```

---

## ⚙️ 配置说明

### 后端配置 (`server.py`)

| 配置项 | 默认值 | 说明 |
|--------|--------|------|
| `MEM0_PORT` (环境变量) | `8080` | 后端监听端口 |
| `QDRANT_DATA_PATH` | `./qdrant_data` | Qdrant 数据存储目录 |
| `llm.model` | `qwen2.5:7b` | LLM 模型名称 |
| `embedder.model` | `nomic-embed-text` | 嵌入模型名称 |
| `ollama_base_url` | `http://<IP>:11434` | Ollama 服务地址 |
| `embedding_model_dims` | `768` | 嵌入向量维度（需与模型匹配） |

### 前端配置 (`mem0-dashboard/.env.local`)

| 配置项 | 默认值 | 说明 |
|--------|--------|------|
| `NEXT_PUBLIC_MEM0_API_URL` | `http://localhost:8080` | 后端 API 地址 |

---

## ❓ 常见问题

### 1. 页面显示"无法连接到 Mem0 API Server"

- **检查后端是否启动**：访问 `http://localhost:8080/`，确认返回 JSON
- **检查端口是否被占用**：`netstat -ano | findstr "8080"`
- **刷新页面**：首次加载时后端可能还在初始化，等几秒后刷新即可

### 2. 后端启动报 `OpenAIError: The api_key client option must be set`

说明 Mem0 配置中的 LLM/Embedder 仍在使用 OpenAI 提供商。请确认 `server.py` 中的 `MEM0_CONFIG` 已正确配置为 `ollama` 提供商。

### 3. 添加记忆时报错 / 响应很慢

- **检查 Ollama 服务**：`curl http://<云服务器IP>:11434/api/tags`
- **检查网络连通性**：确认本地能访问云服务器的 11434 端口
- **首次推理较慢**：Ollama 首次加载模型到 GPU 需要几秒，后续请求会快很多

### 4. 切换 Embedding 模型后数据异常

不同模型的向量维度不同，切换后需要：

```powershell
# 删除旧的向量数据
Remove-Item -Recurse -Force d:\Users\V_grhe\Desktop\ai-demo\demo2\qdrant_data

# 同时修改 server.py 中的 embedding_model_dims 为新模型的维度
# 然后重启后端服务
```

### 5. `watchfiles` 不断输出 `change detected`

这是 uvicorn 的热重载监控日志，不影响正常使用。如果觉得干扰，可以在 `server.py` 的 `uvicorn.run()` 中设置 `reload=False` 关闭热重载。

---

## 📎 附录：云服务器部署 Ollama

如果你还没有在云服务器上部署 Ollama，请按以下步骤操作：

### 1. 安装 Ollama

```bash
# SSH 登录云服务器后执行
curl -fsSL https://ollama.com/install.sh | sh
ollama --version
```

### 2. 配置监听外网

```bash
sudo systemctl edit ollama
```

在编辑器中输入：

```ini
[Service]
Environment="OLLAMA_HOST=0.0.0.0"
```

按 `Ctrl+O` 保存，`Ctrl+X` 退出，然后重启：

```bash
sudo systemctl daemon-reload
sudo systemctl restart ollama
```

### 3. 拉取模型

```bash
ollama pull qwen2.5:7b
ollama pull nomic-embed-text

# 验证
ollama list
```

### 4. 开放防火墙端口

```bash
# Ubuntu
sudo ufw allow 11434/tcp
sudo ufw reload
```

> ⚠️ 云平台用户还需在**控制台安全组**中放行 `11434` 端口（TCP 入方向）。

### 5. 验证

```bash
curl http://localhost:11434/api/tags
# 应返回模型列表 JSON
```

---

## 📄 技术栈

| 层级 | 技术 | 版本 |
|------|------|------|
| 前端框架 | Next.js | 14.x |
| UI 组件 | Radix UI + Tailwind CSS | - |
| 后端框架 | FastAPI + Uvicorn | - |
| 记忆引擎 | Mem0 | 1.0.x |
| 向量数据库 | Qdrant (本地文件模式) | - |
| LLM 服务 | Ollama (qwen2.5:7b) | - |
| 嵌入模型 | Ollama (nomic-embed-text) | - |
| 运行环境 | Python 3.14 + Node.js 18+ | - |
