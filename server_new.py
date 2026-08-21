"""
Mem0 Dashboard 后端 - 启动入口

所有应用逻辑已拆分到 app/ 目录下各模块：
  - app/main.py     → FastAPI 应用创建、中间件、路由注册、生命周期管理
  - app/config.py   → 配置管理
  - app/database.py → SQLite 日志存储
  - app/routers/    → 路由模块（memories, stats, logs, graph, users, system）

启动方式:
  python server.py
  uvicorn app.main:app --host 0.0.0.0 --port 8080 --reload
"""
import os
import uvicorn

from app.main import app  # noqa: F401 — 导出 app 供 uvicorn 引用

from app.config import IS_PRODUCTION


if __name__ == "__main__":
    host = os.environ.get("MEM0_HOST", "0.0.0.0")
    port = int(os.environ.get("MEM0_PORT", "8080"))
    uvicorn.run(
        "app.main:app",
        host=host,
        port=port,
        reload=not IS_PRODUCTION,
    )
