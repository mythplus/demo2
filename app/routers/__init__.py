"""
Mem0 Dashboard 后端 - 路由注册
"""
from app.routers.memories import router as memories_router
from app.routers.stats import router as stats_router
from app.routers.logs import router as logs_router
from app.routers.graph import router as graph_router
from app.routers.users import router as users_router
from app.routers.system import router as system_router

__all__ = [
    "memories_router",
    "stats_router",
    "logs_router",
    "graph_router",
    "users_router",
    "system_router",
]
