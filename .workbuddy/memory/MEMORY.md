# MEMORY.md - demo2 项目长期记忆

## 项目概述
- **目标**: 复刻 mem0.ai dashboard 前端功能，自己部署使用
- **技术栈**: Next.js 14 + TypeScript + Tailwind CSS + Radix UI/shadcn + lucide-react + recharts + zustand | FastAPI + Mem0 + Qdrant(远程服务) + PostgreSQL(记忆元数据 + 访问/请求日志 + 限流 + Webhook 配置) + Neo4j + Ollama
- **风格约束**: 简约设计系统 (Swiss Modernism + Data-Dense Dashboard)，Inter 字体，Indigo 主色 (#4F46E5)，中性灰基底
- **排除功能**: Apps 应用管理、Skill/SubAgent（列为扩展任务）

## 完成状态 (2026-03-27)
- Phase 1 ✅: 分类系统、状态管理、多维筛选、表格视图、独立详情页
- Phase 2 ✅: recharts 图表、关联记忆、Zustand store、JSON编辑器
- Phase 3 ✅: 访问日志(SQLite)、骨架屏、防抖hook、响应式布局

## 关键约束
- categories/state 通过 Mem0 metadata 透传，不修改 Mem0 内核
- 后端 Ollama 地址: http://9.134.231.238:11434 (qwen2.5:7b + nomic-embed-text)
- 前端默认端口 3000，后端默认端口 8080
- 访问日志/请求日志/限流/Webhook 配置/记忆元数据统一存 PostgreSQL（DSN 由 `DATABASE_URL` 指定）
- 生产环境必须配置 `security.api_key`；前端不再使用 `NEXT_PUBLIC_MEM0_API_KEY`，默认通过同源 Nginx 反向代理访问后端
- Webhook URL 需经过 SSRF 安全校验；`secret` 使用加密存储，密钥来自 `security.webhook_secret_key` 或 `api_key` 派生值
- 生产模式默认单 worker，避免对日志写入产生锁竞争（同一 PG 连接池共享）


## 用户偏好
- 主人惜字如金，喜欢简短交流
- 不需要 Skill/SubAgent 方式开发，直接写代码
- 只复刻功能，不做视觉改版
- 前后端同步，每个前端功能必须有对应后端支持
