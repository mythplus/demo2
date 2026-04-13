"""
Mem0 Dashboard 后端 API 服务 — FastAPI 应用组装
创建 FastAPI 实例、生命周期管理、中间件注册、路由注册
"""

import logging
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from server.config import (
    MEM0_CONFIG, QDRANT_DATA_PATH, ACCESS_LOG_DB_PATH,
    IS_PRODUCTION, _safe_error_detail, setup_logging,
)
from server.services import memory_service
from server.services.log_service import init_access_log_db, start_log_writer, stop_log_writer
from server.services.graph_service import close_neo4j_driver
from server.middleware.auth import ApiKeyAuthMiddleware
from server.middleware.rate_limit import RateLimitMiddleware
from server.middleware.request_log import RequestLogMiddleware
from server.routes import health, memories, search, stats, logs, graph, playground, webhooks

logger = logging.getLogger(__name__)

# 配置结构化日志（生产环境 JSON 格式，开发环境可读文本格式）
setup_logging()


# ============ 应用生命周期 ============

@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用启动时初始化 Mem0"""
    logger.info("=" * 50)
    logger.info("Mem0 Dashboard 后端服务启动中...")
    logger.info(f"Qdrant 存储模式: 本地文件模式 (on_disk)")
    logger.info(f"Qdrant 数据目录: {QDRANT_DATA_PATH}")
    logger.info("=" * 50)
    # 初始化全局异步 HTTP 客户端
    memory_service.http_client = httpx.AsyncClient(timeout=30.0)
    # 预初始化 Memory 实例
    memory_service.get_memory()
    # 初始化访问日志数据库
    init_access_log_db()
    logger.info(f"访问日志数据库: {ACCESS_LOG_DB_PATH}")
    # 启动后台日志写入线程
    start_log_writer()
    yield
    # 停止后台日志写入线程（flush 剩余日志）
    stop_log_writer()
    # 关闭全局异步 HTTP 客户端
    if memory_service.http_client:
        await memory_service.http_client.aclose()
    # 关闭全局 Neo4j 驱动
    close_neo4j_driver()
    logger.info("Mem0 Dashboard 后端服务已关闭")


# ============ FastAPI 应用 ============

# ============ Swagger 分类标签（控制 /docs 页面的分组顺序和描述） ============

openapi_tags = [
    {"name": "记忆管理", "description": "记忆的增删改查、批量导入/删除、修改历史"},
    {"name": "语义检索", "description": "基于向量嵌入的语义相似度搜索"},
    {"name": "统计", "description": "全局统计（分类/状态分布、趋势）"},
    {"name": "日志", "description": "访问日志、请求日志"},
    {"name": "图谱记忆", "description": "Neo4j 知识图谱实体/关系管理"},
{"name": "Playground", "description": "AI 记忆增强对话调试"},
    {"name": "系统", "description": "健康检查、配置信息、服务测试"},
]

app = FastAPI(
    title="Mem0 Dashboard API",
    description="Mem0 记忆管理后端服务（Qdrant 本地文件模式）",
    version="1.1.0",
    lifespan=lifespan,
    openapi_tags=openapi_tags,
)

# ============ 全局异常处理 ============

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """全局未捕获异常处理：记录日志，不暴露内部错误详情"""
    logger.error(f"未捕获异常 [{request.method} {request.url.path}]: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"detail": _safe_error_detail(exc)},
    )


# ============ 中间件注册 ============

# CORS 配置（从 config.yaml 读取允许的来源）
_cors_origins_str = MEM0_CONFIG.get("security", {}).get("cors_origins", "*")
_cors_origins = [o.strip() for o in _cors_origins_str.split(",") if o.strip()] if _cors_origins_str != "*" else ["*"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True if _cors_origins != ["*"] else False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# API Key 认证中间件
_configured_api_key = MEM0_CONFIG.get("security", {}).get("api_key", "")
if _configured_api_key:
    app.add_middleware(ApiKeyAuthMiddleware, api_key=_configured_api_key)
    logger.info("API Key 认证已启用")
else:
    logger.warning("⚠️ 未配置 API Key，所有接口无需认证即可访问（建议生产环境设置 security.api_key）")

# 速率限制中间件
_rate_limit_rpm = int(MEM0_CONFIG.get("security", {}).get("rate_limit", 60))
_rate_limit_enabled = _rate_limit_rpm > 0
if _rate_limit_enabled:
    app.add_middleware(RateLimitMiddleware, rpm=_rate_limit_rpm)
    logger.info(f"速率限制已启用：每分钟最多 {_rate_limit_rpm} 次请求")
else:
    logger.info("速率限制未启用（rate_limit 为 0）")

# 请求日志中间件
app.add_middleware(RequestLogMiddleware)


# ============ 路由注册 ============

app.include_router(health.router)
app.include_router(memories.router)
app.include_router(search.router)
app.include_router(stats.router)
app.include_router(logs.router)
app.include_router(graph.router)
app.include_router(playground.router)
app.include_router(webhooks.router)
