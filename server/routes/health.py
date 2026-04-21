"""
健康检查 + 系统配置信息 + 连接测试路由
"""

import os
import re
import time
import logging
from urllib.parse import urlsplit, urlunsplit

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from server.config import MEM0_CONFIG, DATABASE_URL, load_config_from_yaml, _safe_error_detail
from server.services import memory_service
from server.services.graph_service import get_neo4j_driver

logger = logging.getLogger(__name__)

router = APIRouter(tags=["系统"])


def _strip_url_credentials(url: str) -> str:
    """剥离 URL 中的用户名和密码（user:pass@host 形式），防止凭据在配置接口中泄漏。

    无论是否为生产环境，该函数都会被调用，确保任何环境下配置接口都不会暴露 userinfo。
    """
    if not url or "://" not in url:
        return url
    try:
        parts = urlsplit(url)
        if not parts.username and not parts.password:
            return url
        # 重建 netloc，去除 userinfo
        host = parts.hostname or ""
        if parts.port:
            new_netloc = f"{host}:{parts.port}"
        else:
            new_netloc = host
        return urlunsplit((parts.scheme, new_netloc, parts.path, parts.query, parts.fragment))
    except Exception:
        return url


def _mask_url(url: str) -> str:
    """对 URL 中的 IP 地址进行脱敏处理，保留协议和端口，隐藏 IP 中间段。

    注意：调用前应先通过 _strip_url_credentials 剥离 userinfo。
    """
    if not url:
        return url

    def _mask_ip(match):
        ip = match.group(0)
        parts = ip.split(".")
        if len(parts) == 4:
            return f"{parts[0]}.***.***.{parts[3]}"
        return ip
    return re.sub(r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}', _mask_ip, url)


def _is_prod() -> bool:
    """是否处于生产环境（用于决定是否对 URL 中 IP 做脱敏）"""
    return os.environ.get("MEM0_ENV", "development") == "production"


def _resolve_vector_url(vector_cfg: dict) -> str:
    """从 vector_store 配置中解析可访问的 URL（兼容 url / host+port 两种写法）"""
    inner = vector_cfg.get("config", {}) or {}
    url = inner.get("url") or ""
    if url:
        return url
    host = inner.get("host")
    port = inner.get("port")
    if host and port:
        return f"http://{host}:{port}"
    if host:
        return f"http://{host}"
    return ""


def _sanitize_display_url(url: str) -> str:
    """统一处理展示用 URL：先剥离凭据、生产环境再脱敏 IP。"""
    url = _strip_url_credentials(url)
    return _mask_url(url) if _is_prod() else url


def _parse_meta_dsn(dsn: str) -> dict:
    """解析 PostgreSQL DSN，返回用于展示的 provider/host/port/database。

    注意：返回值不包含 username/password，避免凭据泄漏。
    """
    if not dsn:
        return {"provider": "unknown", "host": "", "port": 0, "database": ""}
    try:
        parts = urlsplit(dsn)
        # postgresql://user:pass@host:port/db -> scheme=postgresql
        scheme = parts.scheme or ""
        provider = "postgresql" if scheme.startswith("postgresql") else (scheme or "unknown")
        host = parts.hostname or ""
        port = parts.port or (5432 if provider == "postgresql" else 0)
        # path 形如 "/mem0"，去掉前导 "/"
        database = (parts.path or "").lstrip("/")
        return {
            "provider": provider,
            "host": host,
            "port": int(port) if port else 0,
            "database": database,
        }
    except Exception:
        return {"provider": "unknown", "host": "", "port": 0, "database": ""}


def _build_meta_display_url(info: dict) -> str:
    """构造展示用地址：host:port/database，生产环境对 IP 脱敏"""
    host = info.get("host", "")
    port = info.get("port", 0)
    database = info.get("database", "")
    if not host:
        return ""
    base = f"{host}:{port}" if port else host
    shown = f"{base}/{database}" if database else base
    return _mask_url(shown) if _is_prod() else shown


@router.get("/")
async def health_check():
    """健康检查端点"""
    return {"status": "ok", "message": "Mem0 Dashboard API 运行中"}


@router.get("/health")
async def health_check_alias():
    """健康检查别名端点（兼容 LB/K8s/监控系统常用的 /health 路径）"""
    return {"status": "ok", "message": "Mem0 Dashboard API 运行中"}


@router.get("/health/log-writer")
async def health_log_writer():
    """日志写入线程运行指标（B2 P1-8）。

    用于 Prometheus/监控面板观测异步日志队列的健康度：
    - running：后台线程是否存活
    - queue_size：当前排队等待写入 PostgreSQL 的日志条数
    - dropped：累计因队列满而丢弃的条数（自进程启动以来）
    - failed_batches / failed_entries：穷尽重试后仍写入失败的批次/条目数
    - last_error：最近一次失败的错误摘要（便于报警时直接看到上下文）
    """
    from server.services.log_service import get_log_writer_metrics
    metrics = get_log_writer_metrics()
    return {
        "status": "ok" if metrics.get("running") else "degraded",
        "metrics": metrics,
    }


@router.get("/v1/config/info")
async def get_config_info():
    """获取当前系统配置信息（实时从 config.yaml 读取，修改配置文件后刷新即可同步）"""
    # 实时读取 config.yaml，而非使用启动时的静态变量
    live_config = load_config_from_yaml() or MEM0_CONFIG

    llm_config = live_config.get("llm", {})
    embedder_config = live_config.get("embedder", {})
    vector_config = live_config.get("vector_store", {})
    graph_config = live_config.get("graph_store", {})

    llm_base_url = llm_config.get("config", {}).get("ollama_base_url", llm_config.get("config", {}).get("openai_base_url", ""))
    embedder_base_url = embedder_config.get("config", {}).get("ollama_base_url", embedder_config.get("config", {}).get("openai_base_url", ""))
    graph_url = graph_config.get("config", {}).get("url", "")
    vector_url = _resolve_vector_url(vector_config)

    # 元数据库：DATABASE_URL 可能含用户名/密码，解析时只保留主机信息用于展示
    meta_info = _parse_meta_dsn(DATABASE_URL)

    return {
        "llm": {
            "provider": llm_config.get("provider", "unknown"),
            "model": llm_config.get("config", {}).get("model", "unknown"),
            "base_url": _sanitize_display_url(llm_base_url),
            "temperature": llm_config.get("config", {}).get("temperature", 0.1),
        },
        "embedder": {
            "provider": embedder_config.get("provider", "unknown"),
            "model": embedder_config.get("config", {}).get("model", "unknown"),
            "base_url": _sanitize_display_url(embedder_base_url),
        },
        "vector_store": {
            "provider": vector_config.get("provider", "unknown"),
            "collection_name": vector_config.get("config", {}).get("collection_name", ""),
            "embedding_model_dims": vector_config.get("config", {}).get("embedding_model_dims", 0),
            "url": _sanitize_display_url(vector_url),
        },
        "graph_store": {
            "provider": graph_config.get("provider", "unknown"),
            "url": _sanitize_display_url(graph_url),
        },
        # 新增：元数据库（PostgreSQL）基本信息。URL 仅保留 host:port/database，不含 userinfo
        "meta_store": {
            "provider": meta_info["provider"],
            "host": _mask_url(meta_info["host"]) if _is_prod() else meta_info["host"],
            "port": meta_info["port"],
            "database": meta_info["database"],
            "url": _build_meta_display_url(meta_info),
        },
    }


@router.get("/v1/config/test-llm")
async def test_llm_connection():
    """测试 LLM 大模型连接（实时从 config.yaml 读取配置，复用全局异步 HTTP 客户端）"""
    live_config = load_config_from_yaml() or MEM0_CONFIG
    llm_config = live_config.get("llm", {})
    provider = llm_config.get("provider", "unknown")
    config = llm_config.get("config", {})
    model = config.get("model", "unknown")
    base_url = config.get("ollama_base_url", config.get("openai_base_url", ""))

    try:
        client = memory_service.http_client
        if provider == "ollama":
            # 测试 Ollama：调用 /api/tags 获取模型列表，验证目标模型是否存在
            resp = await client.get(f"{base_url}/api/tags", timeout=10)
            resp.raise_for_status()
            models_data = resp.json()
            model_names = [m.get("name", "").split(":")[0] for m in models_data.get("models", [])]
            model_base = model.split(":")[0]
            model_found = model_base in model_names or model in [m.get("name", "") for m in models_data.get("models", [])]

            # 进一步做一次简单的生成测试
            gen_resp = await client.post(
                f"{base_url}/api/generate",
                json={"model": model, "prompt": "hi", "stream": False, "options": {"num_predict": 5}},
                timeout=30,
            )
            gen_resp.raise_for_status()
            gen_text = gen_resp.json().get("response", "")

            return {
                "status": "connected",
                "provider": provider,
                "model": model,
                "base_url": base_url,
                "model_available": model_found,
                "test_response": gen_text[:100] if gen_text else "(空响应)",
                "message": f"LLM 连接成功，模型 {model} {'可用' if model_found else '未在模型列表中找到，但生成测试通过'}",
            }
        else:
            # OpenAI 兼容接口测试
            headers = {}
            api_key = config.get("api_key", "")
            if api_key:
                headers["Authorization"] = f"Bearer {api_key}"
            resp = await client.get(f"{base_url}/models", headers=headers, timeout=10)
            resp.raise_for_status()
            return {
                "status": "connected",
                "provider": provider,
                "model": model,
                "base_url": base_url,
                "model_available": True,
                "message": f"LLM 连接成功（{provider}）",
            }
    except Exception as e:
        logger.warning(f"LLM 连接测试失败: {e}")
        return {
            "status": "error",
            "provider": provider,
            "model": model,
            "base_url": base_url,
            "model_available": False,
            "message": f"连接失败: {_safe_error_detail(e)}",
        }


@router.get("/v1/config/test-embedder")
async def test_embedder_connection():
    """测试 Embedder 嵌入模型连接（实时从 config.yaml 读取配置，复用全局异步 HTTP 客户端）"""
    live_config = load_config_from_yaml() or MEM0_CONFIG
    embedder_config = live_config.get("embedder", {})
    provider = embedder_config.get("provider", "unknown")
    config = embedder_config.get("config", {})
    model = config.get("model", "unknown")
    base_url = config.get("ollama_base_url", config.get("openai_base_url", ""))

    try:
        client = memory_service.http_client
        if provider == "ollama":
            # 测试 Ollama Embedder：发送一个简单的嵌入请求
            resp = await client.post(
                f"{base_url}/api/embeddings",
                json={"model": model, "prompt": "test"},
                timeout=15,
            )
            resp.raise_for_status()
            embedding = resp.json().get("embedding", [])
            dims = len(embedding)

            return {
                "status": "connected",
                "provider": provider,
                "model": model,
                "base_url": base_url,
                "embedding_dims": dims,
                "message": f"Embedder 连接成功，模型 {model}，向量维度 {dims}",
            }
        else:
            # OpenAI 兼容接口测试
            headers = {"Content-Type": "application/json"}
            api_key = config.get("api_key", "")
            if api_key:
                headers["Authorization"] = f"Bearer {api_key}"
            resp = await client.post(
                f"{base_url}/embeddings",
                json={"model": model, "input": "test"},
                headers=headers,
                timeout=15,
            )
            resp.raise_for_status()
            data = resp.json().get("data", [{}])
            dims = len(data[0].get("embedding", [])) if data else 0
            return {
                "status": "connected",
                "provider": provider,
                "model": model,
                "base_url": base_url,
                "embedding_dims": dims,
                "message": f"Embedder 连接成功（{provider}），向量维度 {dims}",
            }
    except Exception as e:
        logger.warning(f"Embedder 连接测试失败: {e}")
        return {
            "status": "error",
            "provider": provider,
            "model": model,
            "base_url": base_url,
            "embedding_dims": 0,
            "message": f"连接失败: {_safe_error_detail(e)}",
        }


# ============ 存储服务连接测试 ============

@router.get("/v1/config/test-vector")
async def test_vector_store_connection():
    """测试向量数据库（Qdrant）连接：查询集合信息并返回维度 / 向量数量。

    该接口通过 Mem0 SDK 已经建立好的 Qdrant client 访问远端服务，
    不会新建连接，也不会因为 network 短暂抖动而影响业务主链路。
    """
    live_config = load_config_from_yaml() or MEM0_CONFIG
    vector_config = live_config.get("vector_store", {})
    provider = vector_config.get("provider", "unknown")
    inner = vector_config.get("config", {}) or {}
    collection_name = inner.get("collection_name", "")
    configured_dims = int(inner.get("embedding_model_dims", 0) or 0)
    # 展示用 URL，剥离凭据 / 生产脱敏
    display_url = _sanitize_display_url(_resolve_vector_url(vector_config))

    start = time.time()
    try:
        m = memory_service.get_memory()
        # m.vector_store.client 即官方/社区版 Qdrant client
        qdrant_client = getattr(getattr(m, "vector_store", None), "client", None)
        if qdrant_client is None:
            raise RuntimeError("Qdrant client 未初始化，请检查 Mem0 后端配置")

        info = qdrant_client.get_collection(collection_name)
        latency = round((time.time() - start) * 1000, 1)

        # 兼容不同 Qdrant SDK 版本取维度
        vectors_cfg = getattr(getattr(info, "config", None), "params", None)
        actual_dims = 0
        if vectors_cfg is not None:
            vectors = getattr(vectors_cfg, "vectors", None)
            # 可能是单 vector 配置，也可能是 dict (命名向量)
            if vectors is not None and hasattr(vectors, "size"):
                actual_dims = int(getattr(vectors, "size", 0) or 0)
            elif isinstance(vectors, dict) and vectors:
                first_val = next(iter(vectors.values()))
                actual_dims = int(getattr(first_val, "size", 0) or 0)

        # 仅做连通性探测，不再返回集合内向量数量（避免给用户传达“数据量”等与连接测试无关的信息）
        dims_match = (actual_dims == configured_dims) if (configured_dims and actual_dims) else True
        message_parts = [f"Qdrant 连接成功，集合「{collection_name}」"]
        if actual_dims:
            message_parts.append(f"维度 {actual_dims}")
        if configured_dims and actual_dims and not dims_match:
            message_parts.append(
                f"⚠️ 实际维度与配置 {configured_dims} 不一致，可能导致插入失败"
            )

        return {
            "status": "connected",
            "provider": provider,
            "base_url": display_url,
            "collection_name": collection_name,
            # points_count 字段保留 0，兼容前端类型定义；连通性测试不再暴露数据量
            "points_count": 0,
            "dimensions": actual_dims or configured_dims,
            "configured_dimensions": configured_dims,
            "dimensions_match": dims_match,
            "latency_ms": latency,
            "message": "，".join(message_parts),
        }
    except Exception as e:
        latency = round((time.time() - start) * 1000, 1)
        logger.warning(f"Qdrant 连接测试失败: {e}")
        return {
            "status": "error",
            "provider": provider,
            "base_url": display_url,
            "collection_name": collection_name,
            "points_count": 0,
            "dimensions": 0,
            "configured_dimensions": configured_dims,
            "dimensions_match": False,
            "latency_ms": latency,
            "message": f"连接失败: {_safe_error_detail(e)}",
        }


@router.get("/v1/config/test-meta")
async def test_meta_store_connection():
    """测试元数据库（PostgreSQL）连接：仅做连通性探测。

    返回值：
      - server_version：PostgreSQL 版本（执行 SELECT version()）
      - latency_ms：查询耗时
    """
    meta_info = _parse_meta_dsn(DATABASE_URL)
    display_url = _build_meta_display_url(meta_info)

    start = time.time()
    try:
        from sqlalchemy import text as sa_text
        from server.models.database import get_engine

        engine = get_engine()
        with engine.connect() as conn:
            # 1) ping：验证连通性
            conn.execute(sa_text("SELECT 1"))
            # 2) 版本号（截短展示）
            ver_row = conn.execute(sa_text("SELECT version()")).scalar() or ""
            # version() 返回较长，取前 80 字符足够判断引擎/版本
            server_version = ver_row[:80]

        latency = round((time.time() - start) * 1000, 1)
        return {
            "status": "connected",
            "provider": meta_info["provider"],
            "host": _mask_url(meta_info["host"]) if _is_prod() else meta_info["host"],
            "port": meta_info["port"],
            "database": meta_info["database"],
            "base_url": display_url,
            "server_version": server_version,
            # memories_count 字段保留 0，兼容前端类型定义；连通性测试不再统计数据量
            "memories_count": 0,
            "latency_ms": latency,
            "message": "PostgreSQL 连接成功",
        }
    except Exception as e:
        latency = round((time.time() - start) * 1000, 1)
        logger.warning(f"PostgreSQL 连接测试失败: {e}")
        return {
            "status": "error",
            "provider": meta_info["provider"],
            "host": _mask_url(meta_info["host"]) if _is_prod() else meta_info["host"],
            "port": meta_info["port"],
            "database": meta_info["database"],
            "base_url": display_url,
            "server_version": "",
            "memories_count": 0,
            "latency_ms": latency,
            "message": f"连接失败: {_safe_error_detail(e)}",
        }


# ============ 深度健康检查 ============

async def _check_qdrant() -> dict:
    """检测 Qdrant 向量数据库连通性"""
    start = time.time()
    try:
        m = memory_service.get_memory()
        collection_name = MEM0_CONFIG["vector_store"]["config"]["collection_name"]
        info = m.vector_store.client.get_collection(collection_name)
        latency = round((time.time() - start) * 1000, 1)
        return {
            "status": "ok",
            "latency_ms": latency,
            "points_count": info.points_count,
            "message": f"Qdrant 正常，集合 {collection_name} 共 {info.points_count} 条向量",
        }
    except Exception as e:
        latency = round((time.time() - start) * 1000, 1)
        logger.warning(f"深度健康检查 - Qdrant 异常: {e}")
        return {
            "status": "error",
            "latency_ms": latency,
            "message": f"Qdrant 不可用: {_safe_error_detail(e)}",
        }


async def _check_ollama() -> dict:
    """检测 Ollama LLM 服务连通性（轻量级，仅请求 /api/tags）"""
    start = time.time()
    try:
        client = memory_service.http_client
        llm_config = MEM0_CONFIG.get("llm", {}).get("config", {})
        base_url = llm_config.get("ollama_base_url", llm_config.get("openai_base_url", ""))
        if not base_url:
            return {"status": "skip", "latency_ms": 0, "message": "未配置 Ollama 地址"}

        resp = await client.get(f"{base_url}/api/tags", timeout=5)
        resp.raise_for_status()
        models = resp.json().get("models", [])
        latency = round((time.time() - start) * 1000, 1)
        return {
            "status": "ok",
            "latency_ms": latency,
            "models_count": len(models),
            "message": f"Ollama 正常，共 {len(models)} 个模型可用",
        }
    except Exception as e:
        latency = round((time.time() - start) * 1000, 1)
        logger.warning(f"深度健康检查 - Ollama 异常: {e}")
        return {
            "status": "error",
            "latency_ms": latency,
            "message": f"Ollama 不可用: {_safe_error_detail(e)}",
        }


async def _check_neo4j() -> dict:
    """检测 Neo4j 图数据库连通性"""
    start = time.time()
    try:
        driver = get_neo4j_driver()
        if not driver:
            return {"status": "skip", "latency_ms": 0, "message": "未配置 Neo4j 或连接失败"}

        with driver.session() as session:
            result = session.run("RETURN 1 AS ping")
            result.single()
        latency = round((time.time() - start) * 1000, 1)
        return {
            "status": "ok",
            "latency_ms": latency,
            "message": "Neo4j 正常",
        }
    except Exception as e:
        latency = round((time.time() - start) * 1000, 1)
        logger.warning(f"深度健康检查 - Neo4j 异常: {e}")
        return {
            "status": "error",
            "latency_ms": latency,
            "message": f"Neo4j 不可用: {_safe_error_detail(e)}",
        }


@router.get("/v1/health/deep")
async def deep_health_check():
    """深度健康检查 — 一次性检测所有依赖服务的连通性（Qdrant / Ollama / Neo4j）
    返回各服务状态和整体健康状态，适用于 K8s readinessProbe 或监控系统。
    """
    import asyncio

    # 并发检测所有依赖服务
    qdrant_task = asyncio.create_task(_check_qdrant())
    ollama_task = asyncio.create_task(_check_ollama())
    neo4j_task = asyncio.create_task(_check_neo4j())

    qdrant_result, ollama_result, neo4j_result = await asyncio.gather(
        qdrant_task, ollama_task, neo4j_task
    )

    # 判断整体健康状态：任一核心服务异常则整体不健康
    # Qdrant 和 Ollama 是核心依赖，Neo4j 为可选（skip 不算异常）
    all_checks = {
        "qdrant": qdrant_result,
        "ollama": ollama_result,
        "neo4j": neo4j_result,
    }

    core_services = ["qdrant", "ollama"]
    has_core_error = any(
        all_checks[svc]["status"] == "error" for svc in core_services
    )
    has_any_error = any(
        v["status"] == "error" for v in all_checks.values()
    )

    if has_core_error:
        overall = "unhealthy"
    elif has_any_error:
        overall = "degraded"
    else:
        overall = "healthy"

    response_data = {
        "status": overall,
        "services": all_checks,
    }

    # 如果不健康，返回 503 状态码（便于负载均衡器/K8s 判断）
    status_code = 503 if overall == "unhealthy" else 200
    return JSONResponse(content=response_data, status_code=status_code)
