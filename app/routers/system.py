"""
Mem0 Dashboard 后端 - 系统路由（健康检查、配置、导出、连接测试）
"""
import json
import csv
import io
import logging
from typing import Optional

import httpx
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse

from app.config import MEM0_CONFIG, load_config_from_yaml, _safe_error_detail
from app.memory_engine import get_all_memories_raw

logger = logging.getLogger(__name__)

router = APIRouter(tags=["system"])


@router.get("/v1/health/")
async def health_check():
    """健康检查（轻量级，不加载全部记忆）"""
    try:
        # 轻量级检查：仅查询 Qdrant collection 的点数
        from app.memory_engine import get_memory
        from app.config import MEM0_CONFIG
        m = get_memory()
        collection_name = MEM0_CONFIG["vector_store"]["config"]["collection_name"]
        qdrant_client = m.vector_store.client
        count_result = qdrant_client.count(
            collection_name=collection_name,
            exact=False,
        )
        total = count_result.count if hasattr(count_result, "count") else 0

        return {
            "status": "ok",
            "version": MEM0_CONFIG.get("version", "v1.1"),
            "memories_total": total,
            "memories_active": total,  # 精确的 active 数需要 scroll，健康检查不需要
        }
    except Exception as e:
        return {
            "status": "degraded",
            "version": MEM0_CONFIG.get("version", "v1.1"),
            "error": _safe_error_detail(e),
        }


@router.get("/v1/config/")
async def get_config():
    """获取当前配置（脱敏）"""
    try:
        safe_config = {}
        for key, value in MEM0_CONFIG.items():
            if key == "graph_store":
                graph_config = value.get("config", {})
                safe_config[key] = {
                    "provider": value.get("provider"),
                    "config": {
                        "url": graph_config.get("url", ""),
                        "username": graph_config.get("username", ""),
                        "password": "***" if graph_config.get("password") else "",
                    },
                }
            elif isinstance(value, dict) and "config" in value:
                raw_cfg = value.get("config", {})
                safe_cfg = {}
                for k, v in raw_cfg.items():
                    if k in ("api_key", "password", "token", "secret"):
                        safe_cfg[k] = "***" if v else ""
                    else:
                        safe_cfg[k] = v
                safe_config[key] = {
                    "provider": value.get("provider"),
                    "config": safe_cfg,
                }
            else:
                safe_config[key] = value
        safe_config["qdrant_data_path"] = MEM0_CONFIG.get("vector_store", {}).get("config", {}).get("path", "")
        return safe_config
    except Exception as e:
        logger.error(f"获取配置失败: {e}")
        raise HTTPException(status_code=500, detail=_safe_error_detail(e))


@router.get("/v1/config/info")
async def get_config_info():
    """获取当前配置（脱敏）- /v1/config/info 别名"""
    return await get_config()


@router.get("/v1/config/test-llm")
async def test_llm_connection():
    """测试 LLM 大模型连接"""
    live_config = load_config_from_yaml() or MEM0_CONFIG
    llm_config = live_config.get("llm", {})
    provider = llm_config.get("provider", "unknown")
    config = llm_config.get("config", {})
    model = config.get("model", "unknown")
    base_url = config.get("ollama_base_url", config.get("openai_base_url", ""))

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            if provider == "ollama":
                resp = await client.get(f"{base_url}/api/tags", timeout=10)
                resp.raise_for_status()
                models_data = resp.json()
                model_names = [m.get("name", "").split(":")[0] for m in models_data.get("models", [])]
                model_base = model.split(":")[0]
                model_found = model_base in model_names or model in [m.get("name", "") for m in models_data.get("models", [])]

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
    """测试 Embedder 嵌入模型连接"""
    live_config = load_config_from_yaml() or MEM0_CONFIG
    embedder_config = live_config.get("embedder", {})
    provider = embedder_config.get("provider", "unknown")
    config = embedder_config.get("config", {})
    model = config.get("model", "unknown")
    base_url = config.get("ollama_base_url", config.get("openai_base_url", ""))

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            if provider == "ollama":
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


@router.get("/v1/export/")
async def export_memories(
    format: str = Query("json", pattern="^(json|csv)$"),
    user_id: Optional[str] = Query(None),
    state: Optional[str] = Query("active"),
):
    """导出记忆数据"""
    try:
        all_memories = get_all_memories_raw()

        if user_id:
            all_memories = [m for m in all_memories if m.get("user_id") == user_id]
        if state:
            all_memories = [m for m in all_memories if m.get("state", "active") == state]

        if not all_memories:
            raise HTTPException(status_code=404, detail="没有可导出的数据")

        export_data = []
        for m in all_memories:
            export_data.append({
                "id": m.get("id", ""),
                "memory": m.get("memory", ""),
                "user_id": m.get("user_id", ""),
                "categories": m.get("categories", []),
                "state": m.get("state", "active"),
                "created_at": m.get("created_at", ""),
                "updated_at": m.get("updated_at", ""),
            })

        if format == "csv":
            output = io.StringIO()
            writer = csv.DictWriter(output, fieldnames=["id", "memory", "user_id", "categories", "state", "created_at", "updated_at"])
            writer.writeheader()
            for item in export_data:
                item["categories"] = ";".join(item["categories"])
                writer.writerow(item)
            csv_content = output.getvalue()
            return StreamingResponse(
                io.BytesIO(csv_content.encode("utf-8-sig")),
                media_type="text/csv",
                headers={"Content-Disposition": "attachment; filename=memories_export.csv"},
            )
        else:
            json_content = json.dumps(export_data, ensure_ascii=False, indent=2)
            return StreamingResponse(
                io.BytesIO(json_content.encode("utf-8")),
                media_type="application/json",
                headers={"Content-Disposition": "attachment; filename=memories_export.json"},
            )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"导出数据失败: {e}")
        raise HTTPException(status_code=500, detail=_safe_error_detail(e))
