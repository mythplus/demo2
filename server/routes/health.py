"""
健康检查 + 系统配置信息 + 连接测试路由
"""

import os
import re
import logging

from fastapi import APIRouter

from server.config import MEM0_CONFIG, load_config_from_yaml, _safe_error_detail
from server.services import memory_service

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

    llm_base_url = llm_config.get("config", {}).get("ollama_base_url", llm_config.get("config", {}).get("openai_base_url", ""))
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
