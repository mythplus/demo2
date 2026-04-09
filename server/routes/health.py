"""
健康检查 + 系统配置信息 + 连接测试路由
"""

import os
import re
import time
import logging

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from server.config import MEM0_CONFIG, load_config_from_yaml, _safe_error_detail
from server.services import memory_service
from server.services.graph_service import get_neo4j_driver

logger = logging.getLogger(__name__)

router = APIRouter()


def _mask_url(url: str) -> str:
    """对 URL 中的 IP 地址进行脱敏处理，保留协议和端口，隐藏 IP 中间段"""
    if not url:
        return url

    def _mask_ip(match):
        ip = match.group(0)
        parts = ip.split(".")
        if len(parts) == 4:
            return f"{parts[0]}.***.***.{parts[3]}"
        return ip
    return re.sub(r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}', _mask_ip, url)


@router.get("/")
async def health_check():
    """健康检查端点"""
    return {"status": "ok", "message": "Mem0 Dashboard API 运行中"}


@router.get("/v1/config/info")
async def get_config_info():
    """获取当前系统配置信息（实时从 config.yaml 读取，修改配置文件后刷新即可同步）"""
    # 实时读取 config.yaml，而非使用启动时的静态变量
    live_config = load_config_from_yaml() or MEM0_CONFIG

    llm_config = live_config.get("llm", {})
    embedder_config = live_config.get("embedder", {})
    vector_config = live_config.get("vector_store", {})
    graph_config = live_config.get("graph_store", {})

    # 是否为生产环境（生产环境对 URL 做脱敏处理）
    is_prod = os.environ.get("ENV", "development") == "production"

    llm_cfg = llm_config.get("config", {})
    llm_base_url = llm_cfg.get("vllm_base_url", llm_cfg.get("ollama_base_url", llm_cfg.get("openai_base_url", "")))
    embedder_base_url = embedder_config.get("config", {}).get("ollama_base_url", embedder_config.get("config", {}).get("openai_base_url", ""))
    graph_url = graph_config.get("config", {}).get("url", "")

    return {
        "llm": {
            "provider": llm_config.get("provider", "unknown"),
            "model": llm_config.get("config", {}).get("model", "unknown"),
            "base_url": _mask_url(llm_base_url) if is_prod else llm_base_url,
            "temperature": llm_config.get("config", {}).get("temperature", 0.1),
        },
        "embedder": {
            "provider": embedder_config.get("provider", "unknown"),
            "model": embedder_config.get("config", {}).get("model", "unknown"),
            "base_url": _mask_url(embedder_base_url) if is_prod else embedder_base_url,
        },
        "vector_store": {
            "provider": vector_config.get("provider", "unknown"),
            "collection_name": vector_config.get("config", {}).get("collection_name", ""),
            "embedding_model_dims": vector_config.get("config", {}).get("embedding_model_dims", 0),
        },
        "graph_store": {
            "provider": graph_config.get("provider", "unknown"),
            "url": _mask_url(graph_url) if is_prod else graph_url,
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
    base_url = config.get("vllm_base_url", config.get("ollama_base_url", config.get("openai_base_url", "")))

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
        elif provider == "vllm":
            # 测试 vLLM：调用 OpenAI 兼容的 /models 接口，再做一次简单生成测试
            headers = {"Content-Type": "application/json"}
            api_key = config.get("api_key", "")
            if api_key:
                headers["Authorization"] = f"Bearer {api_key}"

            # 获取模型列表
            resp = await client.get(f"{base_url}/models", headers=headers, timeout=10)
            resp.raise_for_status()
            models_data = resp.json().get("data", [])
            model_ids = [m.get("id", "") for m in models_data]
            model_found = model in model_ids

            # 简单生成测试
            gen_resp = await client.post(
                f"{base_url}/chat/completions",
                json={
                    "model": model,
                    "messages": [{"role": "user", "content": "hi"}],
                    "max_tokens": 5,
                    "temperature": 0.1,
                },
                headers=headers,
                timeout=30,
            )
            gen_resp.raise_for_status()
            gen_text = gen_resp.json().get("choices", [{}])[0].get("message", {}).get("content", "")

            return {
                "status": "connected",
                "provider": provider,
                "model": model,
                "base_url": base_url,
                "model_available": model_found,
                "test_response": gen_text[:100] if gen_text else "(空响应)",
                "message": f"vLLM 连接成功，模型 {model} {'可用' if model_found else '未在模型列表中找到，但生成测试通过'}",
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


async def _check_llm() -> dict:
    """检测 LLM 服务连通性（根据 provider 自动选择检测方式）"""
    start = time.time()
    try:
        client = memory_service.http_client
        llm_provider = MEM0_CONFIG.get("llm", {}).get("provider", "ollama")
        llm_config = MEM0_CONFIG.get("llm", {}).get("config", {})
        base_url = llm_config.get("vllm_base_url", llm_config.get("ollama_base_url", llm_config.get("openai_base_url", "")))
        if not base_url:
            return {"status": "skip", "latency_ms": 0, "message": "未配置 LLM 服务地址"}

        if llm_provider == "ollama":
            # Ollama：请求 /api/tags
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
        elif llm_provider == "vllm":
            # vLLM：请求 OpenAI 兼容的 /models
            headers = {}
            api_key = llm_config.get("api_key", "")
            if api_key:
                headers["Authorization"] = f"Bearer {api_key}"
            resp = await client.get(f"{base_url}/models", headers=headers, timeout=5)
            resp.raise_for_status()
            models = resp.json().get("data", [])
            latency = round((time.time() - start) * 1000, 1)
            return {
                "status": "ok",
                "latency_ms": latency,
                "models_count": len(models),
                "message": f"vLLM 正常，共 {len(models)} 个模型可用",
            }
        else:
            # 其他 OpenAI 兼容接口
            headers = {}
            api_key = llm_config.get("api_key", "")
            if api_key:
                headers["Authorization"] = f"Bearer {api_key}"
            resp = await client.get(f"{base_url}/models", headers=headers, timeout=5)
            resp.raise_for_status()
            latency = round((time.time() - start) * 1000, 1)
            return {
                "status": "ok",
                "latency_ms": latency,
                "message": f"LLM 服务（{llm_provider}）正常",
            }
    except Exception as e:
        latency = round((time.time() - start) * 1000, 1)
        llm_provider = MEM0_CONFIG.get("llm", {}).get("provider", "unknown")
        logger.warning(f"深度健康检查 - LLM（{llm_provider}）异常: {e}")
        return {
            "status": "error",
            "latency_ms": latency,
            "message": f"LLM 服务（{llm_provider}）不可用: {_safe_error_detail(e)}",
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
    """深度健康检查 — 一次性检测所有依赖服务的连通性（Qdrant / LLM / Neo4j）
    返回各服务状态和整体健康状态，适用于 K8s readinessProbe 或监控系统。
    """
    import asyncio

    # 并发检测所有依赖服务
    qdrant_task = asyncio.create_task(_check_qdrant())
    llm_task = asyncio.create_task(_check_llm())
    neo4j_task = asyncio.create_task(_check_neo4j())

    qdrant_result, llm_result, neo4j_result = await asyncio.gather(
        qdrant_task, llm_task, neo4j_task
    )

    # 判断整体健康状态：任一核心服务异常则整体不健康
    # Qdrant 和 LLM 是核心依赖，Neo4j 为可选（skip 不算异常）
    all_checks = {
        "qdrant": qdrant_result,
        "llm": llm_result,
        "neo4j": neo4j_result,
    }

    core_services = ["qdrant", "llm"]
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
