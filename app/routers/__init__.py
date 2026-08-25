"""
Mem0 Dashboard 后端 - 路由注册
"""
from app.routers.memories import router as memories_router
from app.routers.stats import router as stats_router
from app.routers.logs import router as logs_router
from app.routers.graph import router as graph_router
from app.routers.users import router as users_router
from app.routers.system import router as system_router
from app.routers.auth import router as auth_router
from app.routers.tenants import router as tenants_router
from app.routers.tenant_config import router as tenant_config_router
from app.routers.quota import router as quota_router

__all__ = [
    "memories_router",
    "stats_router",
    "logs_router",
    "graph_router",
    "users_router",
    "system_router",
    "auth_router",
    "tenants_router",
    "tenant_config_router",
    "quota_router",
]
