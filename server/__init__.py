"""
Mem0 Dashboard 后端 API 服务 — server 包

仅导出核心对象，确保 `uvicorn server:app` 和 `from server import app` 有效。
业务代码请直接从子模块导入，例如：
  from server.config import MEM0_CONFIG
  from server.services.memory_service import get_memory
"""

from server.app import app  # noqa: F401 — FastAPI 应用实例
