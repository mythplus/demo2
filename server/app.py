"""
Mem0 Dashboard 后端 API 服务 — FastAPI 应用组装
创建 FastAPI 实例、生命周期管理、中间件注册、路由注册
"""

import uuid
import logging
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from server.config import (
    MEM0_CONFIG, ACCESS_LOG_DB_PATH,
    IS_PRODUCTION, IS_TESTING, safe_error_detail, setup_logging,
)
from server.services import memory_service
from server.services.log_service import init_access_log_db, start_log_writer, stop_log_writer, start_log_cleanup
from server.services.webhook_service import (
    init_webhook_table,
    migrate_webhook_secrets,
    _migrate_from_json as _migrate_webhooks_from_json,
)
from server.services.graph_service import close_neo4j_driver
from server.services.background_tasks import wait_background_tasks
from server.models.database import init_db, close_db
from server.middleware.auth import ApiKeyAuthMiddleware
from server.middleware.rate_limit import RateLimitMiddleware
from server.middleware.request_log import RequestLogMiddleware
from server.routes import health, memories, search, stats, logs, graph, playground, webhooks


logger = logging.getLogger(__name__)

# 日志配置延迟到 lifespan 内执行，避免 uvicorn reload 子进程在 import 阶段
# 与 uvicorn 自带的 logging.config 注册顺序冲突、导致 handler 竞争

# ============ 应用生命周期 ============

@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用启动时初始化 Mem0"""
    # 配置结构化日志（生产环境 JSON 格式，开发环境可读文本格式）
    setup_logging()
    logger.info("=" * 50)
    logger.info("Mem0 Dashboard 后端服务启动中...")
    _vs_cfg = MEM0_CONFIG.get("vector_store", {}).get("config", {})
    _qdrant_addr = _vs_cfg.get("url") or f"{_vs_cfg.get('host', 'unknown')}:{_vs_cfg.get('port', 'unknown')}"
    logger.info(f"Qdrant 存储模式: 远程服务模式 ({_qdrant_addr})")
    logger.info("=" * 50)
    # 初始化全局异步 HTTP 客户端
    memory_service.http_client = httpx.AsyncClient(timeout=30.0)
    # 预初始化 Memory 实例
    memory_service.get_memory()
    # 初始化记忆元数据库（SQLAlchemy 管理，对齐 OpenMemory 官方架构）
    init_db()
    # 初始化访问日志数据库
    init_access_log_db()
    logger.info(f"访问日志数据库: {ACCESS_LOG_DB_PATH}")
    # 启动后台日志写入线程
    start_log_writer()
    # 启动日志自动清理（保留 30 天，启动时清理一次 + 每日定时）
    start_log_cleanup()
    # 初始化 Webhook 配置表、迁移旧 JSON 数据，并将旧明文 secret 升级为加密存储
    init_webhook_table()
    _migrate_webhooks_from_json()
    migrate_webhook_secrets()

    yield
    # 等待 Playground 后台任务完成（如记忆存储），最多等 30 秒
    await wait_background_tasks(timeout=30.0)
    # 停止后台日志写入线程（flush 剩余日志）
    stop_log_writer()
    # 关闭全局异步 HTTP 客户端
    if memory_service.http_client:
        await memory_service.http_client.aclose()
    # 关闭记忆元数据库
    close_db()
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
    description="Mem0 记忆管理后端服务（远程 Qdrant / Neo4j / PostgreSQL 模式）",
    version="1.1.0",
    lifespan=lifespan,
    openapi_tags=openapi_tags,
)

# ============ 全局异常处理 ============

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """全局未捕获异常处理：记录日志，不暴露内部错误详情。
    同时为每个失败请求生成/复用 request_id，并写入响应头与响应体，
    方便用户/运维根据该 ID 反查服务端日志。"""
    # 优先复用中间件已注入到 request.state 的 request_id，没有则即时生成
    request_id = getattr(request.state, "request_id", None) or uuid.uuid4().hex

    logger.error(
        f"未捕获异常 [{request.method} {request.url.path}] request_id={request_id}: {exc}",
        exc_info=True,
        extra={
            "request_id": request_id,
            "method": request.method,
            "path": request.url.path,
        },
    )
    return JSONResponse(
        status_code=500,
        headers={"X-Request-ID": request_id},
        content={
            "detail": safe_error_detail(exc),
            "request_id": request_id,
        },
    )


# ============ 中间件注册 ============

# CORS 配置（从 config.yaml 读取允许的来源）
# 注意：必须 strip 一次，避免配置值为 " *"（带空格）时 != "*" 判断失败导致 allow_origins 为空
_cors_origins_str = str(MEM0_CONFIG.get("security", {}).get("cors_origins", "*")).strip()
_cors_origins = [o.strip() for o in _cors_origins_str.split(",") if o.strip()] if _cors_origins_str != "*" else ["*"]
_local_origin_regex = r"^https?://(localhost|127\.0\.0\.1)(:\d+)?$" if not IS_PRODUCTION else None
# allow_credentials 由独立配置项控制，解耦于 origins 是否为通配符。
# 浏览器规范：allow_credentials=True 时 allow_origins 不能为 "*"，此时自动降级为 False。
_cors_allow_credentials = bool(MEM0_CONFIG.get("security", {}).get("cors_allow_credentials", True))
if _cors_allow_credentials and _cors_origins == ["*"]:
    logger.warning("CORS 配置 allow_credentials=True 与 origins=\"*\" 冲突，已自动降级为 False")
    _cors_allow_credentials = False
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_origin_regex=_local_origin_regex,
    allow_credentials=_cors_allow_credentials,
    allow_methods=["*"],
    allow_headers=["*"],
)


# API Key 认证中间件
_configured_api_key = str(MEM0_CONFIG.get("security", {}).get("api_key", "") or "").strip()
if IS_PRODUCTION and not _configured_api_key:
    raise RuntimeError("生产环境必须配置 security.api_key（或 MEM0_API_KEY），禁止无鉴权启动")

if IS_TESTING:
    logger.info("测试环境：已跳过 API Key 认证中间件")
elif _configured_api_key:
    app.add_middleware(ApiKeyAuthMiddleware, api_key=_configured_api_key)
    logger.info("API Key 认证已启用")
else:
    logger.warning("⚠️ 当前未配置 API Key，仅允许在开发/测试环境无鉴权访问")



# 速率限制中间件
_rate_limit_rpm = int(MEM0_CONFIG.get("security", {}).get("rate_limit", 60))
_rate_limit_enabled = _rate_limit_rpm > 0 and not IS_TESTING
if _rate_limit_enabled:
    app.add_middleware(RateLimitMiddleware, rpm=_rate_limit_rpm)
    logger.info(f"速率限制已启用：每分钟最多 {_rate_limit_rpm} 次请求")
else:
    if IS_TESTING:
        logger.info("测试环境：已跳过速率限制中间件")
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
