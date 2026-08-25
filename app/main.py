"""
Mem0 Dashboard 后端 - 应用主模块

创建 FastAPI 应用、注册中间件、挂载路由、管理生命周期事件。
server_new.py 和 tests 均通过 `app.main:app` 引用。
"""
import logging
import time
import os
import httpx
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import IS_PRODUCTION, MEM0_CONFIG, _safe_error_detail
from app.database import init_db, start_log_writer, stop_log_writer, log_request_async
from app.tenant_db import init_tenant_db, ensure_default_tenant
from app.middleware.auth import auth_middleware
from app.middleware.quota import quota_rate_limit_middleware
from app.routers import (
    memories_router,
    stats_router,
    logs_router,
    graph_router,
    users_router,
    system_router,
    auth_router,
    tenants_router,
    tenant_config_router,
    quota_router,
)

# ============ 日志配置 ============
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

# ============ 全局异步 HTTP 客户端（用于 LLM/Embedder 连接测试） ============
_http_client: httpx.AsyncClient | None = None


def get_http_client() -> httpx.AsyncClient:
    """获取全局异步 HTTP 客户端"""
    global _http_client
    if _http_client is None or _http_client.is_closed:
        _http_client = httpx.AsyncClient(timeout=30.0)
    return _http_client


# ============ 生命周期管理 ============
@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期：启动时初始化，关闭时清理"""
    # --- 启动 ---
    init_db()
    init_tenant_db()
    # 初始化默认租户和管理员
    auth_config = MEM0_CONFIG.get("auth", {})
    ensure_default_tenant(
        admin_username=auth_config.get("default_admin_username", "admin"),
        admin_password=auth_config.get("default_admin_password", "admin123456"),
    )
    start_log_writer()
    logger.info(f"Mem0 Dashboard API 启动完成 (模式: {'生产' if IS_PRODUCTION else '开发'})")
    yield
    # --- 关闭 ---
    global _http_client
    if _http_client and not _http_client.is_closed:
        await _http_client.aclose()
    # 关闭 Neo4j 驱动
    try:
        from app.routers.graph import close_neo4j_driver
        close_neo4j_driver()
    except Exception:
        pass
    stop_log_writer()
    logger.info("Mem0 Dashboard API 已关闭")


# ============ 创建 FastAPI 应用 ============
app = FastAPI(
    title="Mem0 Dashboard API",
    description="Mem0 记忆管理系统 Dashboard 后端",
    version=MEM0_CONFIG.get("version", "v1.1"),
    docs_url="/docs" if not IS_PRODUCTION else None,
    redoc_url="/redoc" if not IS_PRODUCTION else None,
    lifespan=lifespan,
)


# ============ 中间件 ============
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if not IS_PRODUCTION else [
        os.environ.get("MEM0_DASHBOARD_URL", "http://localhost:3000"),
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def request_logging_middleware(request: Request, call_next):
    """请求日志中间件：记录每个请求的方法、路径、状态码和耗时"""
    start_time = time.time()
    status_code = 200
    error_msg = None

    try:
        response = await call_next(request)
        status_code = response.status_code
        return response
    except Exception as e:
        status_code = 500
        error_msg = str(e)
        logger.error(f"请求异常: {request.method} {request.url.path} - {e}")
        return JSONResponse(
            status_code=500,
            content={"detail": _safe_error_detail(e)},
        )
    finally:
        latency_ms = (time.time() - start_time) * 1000
        tenant_id = getattr(request.state, "tenant_id", "default") if hasattr(request, "state") else "default"
        await log_request_async(
            method=request.method,
            path=request.url.path,
            request_type=_classify_request_type(request.url.path),
            status_code=status_code,
            latency_ms=latency_ms,
            error=error_msg,
            tenant_id=tenant_id,
        )


def _classify_request_type(path: str) -> str:
    """根据路径分类请求类型"""
    if "/memories" in path:
        return "memory"
    elif "/graph" in path:
        return "graph"
    elif "/stats" in path:
        return "stats"
    elif "/request-logs" in path:
        return "log"
    elif "/config" in path:
        return "config"
    elif "/users" in path:
        return "user"
    elif "/health" in path or path == "/":
        return "health"
    return "other"


# ============ 认证中间件 ============

@app.middleware("http")
async def authentication_middleware(request: Request, call_next):
    """统一认证中间件：JWT / API Key / 开发模式"""
    return await auth_middleware(request, call_next)


# ============ 配额与速率限制中间件 ============

@app.middleware("http")
async def quota_rate_limit(request: Request, call_next):
    """配额 + 速率限制中间件（认证之后执行）"""
    return await quota_rate_limit_middleware(request, call_next)


# ============ 注册路由 ============
app.include_router(system_router)
app.include_router(memories_router)
app.include_router(stats_router)
app.include_router(logs_router)
app.include_router(graph_router)
app.include_router(users_router)
app.include_router(auth_router)
app.include_router(tenants_router)
app.include_router(tenant_config_router)
app.include_router(quota_router)


# ============ 根路由 ============
@app.get("/")
async def root():
    """根路由 - 简单健康检查"""
    return {
        "status": "ok",
        "service": "Mem0 Dashboard API",
        "version": MEM0_CONFIG.get("version", "v1.1"),
        "docs": "/docs" if not IS_PRODUCTION else None,
    }
