# Mem0 Dashboard 前端交付对接说明

> 交付日期：2026-04-13  
> 负责人：前端开发  
> 技术栈：Next.js 14 + React 18 + TypeScript + Tailwind CSS + shadcn/ui

---

## 一、项目概述

Mem0 Dashboard 是一个 AI 记忆管理系统的前端控制台，提供记忆的增删改查、语义搜索、图谱可视化、Playground 对话调试、Webhook 事件通知等功能。

前端为**独立的 Next.js 应用**，通过 REST API 与后端 FastAPI 服务通信，可独立构建和部署。

---

## 二、页面功能清单

| 页面路由 | 功能说明 |
|----------|----------|
| `/` | Dashboard 首页（统计概览、趋势图表） |
| `/memories` | 记忆列表（多维筛选、批量导入/删除、分页） |
| `/memory/[id]` | 记忆详情（编辑、历史记录、关联记忆、访问日志） |
| `/search` | 语义搜索 |
| `/users` | 用户列表 |
| `/users/[userId]` | 用户详情及其记忆 |
| `/graph-memory` | 图谱记忆（Neo4j 实体/关系可视化） |
| `/playground` | AI 对话调试（支持流式 SSE 响应） |
| `/requests` | 请求日志查看 |
| `/webhooks` | Webhook 事件通知管理（CRUD + 测试推送） |
| `/data-transfer` | 数据导入导出 |
| `/settings` | 系统设置（LLM/Embedder 配置查看与连通性测试） |

---

## 三、技术栈与依赖

| 类别 | 技术 | 版本 |
|------|------|------|
| 框架 | Next.js (App Router) | ^14.2.0 |
| UI 库 | React | ^18.3.0 |
| 语言 | TypeScript | ^5.4.0 |
| 样式 | Tailwind CSS | ^3.4.0 |
| 组件库 | Radix UI + shadcn/ui | - |
| 状态管理 | Zustand | ^5.0.12 |
| 图表 | Recharts | ^3.8.1 |
| 图谱可视化 | react-force-graph-2d | ^1.29.1 |
| 数据请求 | TanStack React Query | ^5.50.0 |
| 测试 | Jest + Testing Library | ^29.7.0 |

---

## 四、目录结构

```
mem0-dashboard/
├── src/
│   ├── app/                    # 页面路由（Next.js App Router）
│   │   ├── page.tsx            # Dashboard 首页
│   │   ├── memories/           # 记忆列表
│   │   ├── memory/[id]/        # 记忆详情
│   │   ├── search/             # 语义搜索
│   │   ├── users/              # 用户管理
│   │   ├── graph-memory/       # 图谱记忆
│   │   ├── playground/         # AI 对话调试
│   │   ├── requests/           # 请求日志
│   │   ├── webhooks/           # Webhook 管理
│   │   ├── data-transfer/      # 数据导入导出
│   │   ├── settings/           # 系统设置
│   │   ├── layout.tsx          # 全局布局
│   │   ├── globals.css         # 全局样式
│   │   ├── error.tsx           # 错误边界
│   │   ├── loading.tsx         # 加载状态
│   │   └── not-found.tsx       # 404 页面
│   ├── components/
│   │   ├── ui/                 # 基础 UI 组件（shadcn/ui）
│   │   ├── layout/             # 布局组件（侧边栏、顶栏）
│   │   ├── memories/           # 记忆相关业务组件
│   │   ├── graph/              # 图谱可视化组件
│   │   ├── dashboard/          # Dashboard 图表组件
│   │   └── shared/             # 通用业务组件
│   ├── hooks/                  # 自定义 Hooks
│   ├── lib/
│   │   └── api/
│   │       ├── client.ts       # API 客户端（所有后端接口调用）
│   │       └── types.ts        # TypeScript 类型定义
│   ├── store/                  # Zustand 状态管理
│   └── types/                  # 全局类型声明
├── __tests__/                  # 单元测试
├── public/                     # 静态资源
├── Dockerfile                  # 前端 Docker 构建文件
├── package.json
├── next.config.js
├── tailwind.config.js
├── tsconfig.json
└── .env.example                # 环境变量模板
```

---

## 五、环境变量

| 变量名 | 必填 | 默认值 | 说明 |
|--------|------|--------|------|
| `NEXT_PUBLIC_MEM0_API_URL` | 是 | `http://localhost:8080` | 后端 API 服务地址 |
| `NEXT_PUBLIC_MEM0_API_KEY` | 否 | 空 | API Key 认证密钥（需与后端 `security.api_key` 一致，未配置则留空） |

配置方式：复制 `.env.example` 为 `.env.local`，填入实际值。

---

## 六、本地开发启动

```bash
# 1. 安装依赖
cd mem0-dashboard
npm install

# 2. 配置环境变量
cp .env.example .env.local
# 编辑 .env.local，设置 NEXT_PUBLIC_MEM0_API_URL 指向后端地址

# 3. 启动开发服务器
npm run dev
# 访问 http://localhost:3000
```

其他命令：

```bash
npm run build       # 生产构建
npm start           # 启动生产服务
npm run lint        # ESLint 检查
npm test            # 运行单元测试
npm run test:coverage  # 测试覆盖率
```

---

## 七、Docker 构建与部署

前端有独立的 `Dockerfile`（多阶段构建，使用 Next.js standalone 模式）：

```bash
# 构建镜像
cd mem0-dashboard
docker build -t mem0-frontend:latest .

# 运行容器
docker run -d \
  -p 3000:3000 \
  -e NEXT_PUBLIC_MEM0_API_URL=http://后端地址:8080 \
  -e NEXT_PUBLIC_MEM0_API_KEY=你的密钥 \
  mem0-frontend:latest
```

在 `docker-compose.yml` 中集成前端服务的参考配置：

```yaml
frontend:
  build:
    context: ./mem0-dashboard
    dockerfile: Dockerfile
  container_name: mem0-frontend
  restart: unless-stopped
  ports:
    - "3000:3000"
  environment:
    - NEXT_PUBLIC_MEM0_API_URL=http://backend:8080
    - NEXT_PUBLIC_MEM0_API_KEY=${MEM0_API_KEY:-}
  depends_on:
    backend:
      condition: service_healthy
  healthcheck:
    test: ["CMD", "wget", "--no-verbose", "--tries=1", "--spider", "http://localhost:3000/"]
    interval: 30s
    timeout: 5s
    start_period: 10s
    retries: 3
```

---

## 八、后端 API 依赖清单

前端所有接口调用定义在 `src/lib/api/client.ts`，依赖以下后端 API：

### 8.1 记忆 CRUD

| 方法 | 接口 | 说明 |
|------|------|------|
| POST | `/v1/memories/` | 添加记忆 |
| POST | `/v1/memories/batch` | 批量导入记忆 |
| GET | `/v1/memories/` | 获取记忆列表（支持 `user_id`、`categories`、`state`、`date_from`、`date_to`、`search` 筛选） |
| GET | `/v1/memories/{id}/` | 获取单条记忆 |
| PUT | `/v1/memories/{id}/` | 更新记忆 |
| DELETE | `/v1/memories/{id}/` | 删除单条记忆 |
| POST | `/v1/memories/batch-delete` | 批量删除记忆 |
| DELETE | `/v1/memories/?user_id=xxx` | 删除用户所有记忆 |
| DELETE | `/v1/memories/user/{userId}/hard-delete` | 硬删除用户 |

### 8.2 搜索与关联

| 方法 | 接口 | 说明 |
|------|------|------|
| POST | `/v1/memories/search/` | 语义搜索 |
| GET | `/v1/memories/{id}/related/` | 获取语义相关记忆 |
| GET | `/v1/memories/history/{id}/` | 获取记忆修改历史 |

### 8.3 统计与日志

| 方法 | 接口 | 说明 |
|------|------|------|
| GET | `/v1/stats/` | 统计数据（分类分布、状态分布、趋势） |
| GET | `/v1/memories/{id}/access-logs/` | 记忆访问日志 |
| GET | `/v1/request-logs/` | 请求日志列表 |
| GET | `/v1/request-logs/stats/` | 请求日志统计 |

### 8.4 图谱记忆（Graph Memory）

| 方法 | 接口 | 说明 |
|------|------|------|
| GET | `/v1/graph/stats` | 图谱统计 |
| GET | `/v1/graph/entities` | 实体列表 |
| GET | `/v1/graph/relations` | 关系列表 |
| POST | `/v1/graph/search` | 图谱搜索 |
| GET | `/v1/graph/user/{userId}` | 用户子图数据 |
| GET | `/v1/graph/all` | 全量图谱数据 |
| DELETE | `/v1/graph/entities/{name}` | 删除实体 |
| DELETE | `/v1/graph/relations` | 删除关系 |
| GET | `/v1/graph/health` | Neo4j 连接检查 |

### 8.5 Playground 对话

| 方法 | 接口 | 说明 |
|------|------|------|
| POST | `/v1/playground/chat` | 非流式对话 |
| POST | `/v1/playground/chat/stream` | 流式对话（SSE） |

### 8.6 Webhook 管理

| 方法 | 接口 | 说明 |
|------|------|------|
| GET | `/v1/webhooks/` | 获取 Webhook 列表 |
| POST | `/v1/webhooks/` | 创建 Webhook |
| PUT | `/v1/webhooks/{id}` | 更新 Webhook |
| DELETE | `/v1/webhooks/{id}` | 删除 Webhook |
| POST | `/v1/webhooks/{id}/toggle` | 启用/禁用 Webhook |
| POST | `/v1/webhooks/{id}/test` | 测试 Webhook 推送 |

### 8.7 系统配置

| 方法 | 接口 | 说明 |
|------|------|------|
| GET | `/` | 健康检查 |
| GET | `/v1/config/info` | 获取系统配置信息 |
| GET | `/v1/config/test-llm` | 测试 LLM 连接 |
| GET | `/v1/config/test-embedder` | 测试 Embedder 连接 |

---

## 九、API 代理配置

前端通过 `next.config.js` 中的 rewrite 规则将 `/api/mem0/*` 代理到后端：

```js
async rewrites() {
  return [
    {
      source: '/api/mem0/:path*',
      destination: `${process.env.NEXT_PUBLIC_MEM0_API_URL || 'http://localhost:8080'}/:path*`,
    },
  ];
},
```

> 注意：当前 `client.ts` 中直接使用 `NEXT_PUBLIC_MEM0_API_URL` 拼接请求地址，未走 rewrite 代理。如果部署时存在跨域问题，可将 `client.ts` 中的 `API_BASE` 改为 `/api/mem0`，通过 Next.js 代理转发。

---

## 十、浏览器本地存储说明

以下数据存储在用户浏览器本地，**不依赖后端**：

| 存储方式 | 用途 |
|----------|------|
| IndexedDB (`playground-chat-db`) | Playground 对话历史记录 |
| IndexedDB (`operation-records`) | 前端操作记录 |
| localStorage | 用户偏好设置（主题、分页大小等） |

---

## 十一、后端 Bug 修复说明（需后端同事合入）

前端开发过程中发现并修复了以下后端问题，请后端同事将这些改动合入主分支：

### 11.1 语义搜索缺少 Webhook 触发

**文件**：`server/routes/search.py`  
**问题**：`search_memories` 接口未触发 `memory.searched` 事件的 Webhook，导致前端 Webhook 页面订阅了"记忆检索"事件但永远收不到通知。  
**修复**：在搜索结果返回前，异步调用 `trigger_webhooks("memory.searched", ...)`。

### 11.2 企业微信 Webhook 错误检测不完整

**文件**：`server/services/webhook_service.py`  
**问题**：`_send_webhook` 函数仅检查 HTTP 状态码，但企业微信 API 在请求失败时也返回 HTTP 200，真正的错误在响应体的 `errcode` 字段中。导致推送实际失败但状态显示为 `success`。  
**修复**：增加对企业微信响应体 `errcode` 的检查，`errcode != 0` 时标记为失败。

### 11.3 文案调整

**文件**：`server/app.py`、`server/routes/playground.py`  
**内容**：API 文档 tag 名称 "调试台" → "Playground"，与前端页面名称保持一致。

---

## 十二、注意事项

1. **Node.js 版本**：建议 Node.js >= 18（Dockerfile 中使用 `node:18-alpine`）
2. **构建模式**：生产构建使用 Next.js `standalone` 输出模式，构建产物在 `.next/standalone/` 目录
3. **Playground 对话记录**：存储在浏览器 IndexedDB 中，清除浏览器数据会丢失
4. **图谱功能**：依赖后端 Neo4j 图数据库，如未部署 Neo4j，图谱相关页面会显示连接失败提示
5. **API 认证**：如后端配置了 `security.api_key`，前端需在 `.env.local` 中设置相同的 `NEXT_PUBLIC_MEM0_API_KEY`
