"""
Mem0 Dashboard 后端 - AI 自动分类模块
"""
import json
import logging
import httpx
from typing import List

from app.config import (
    MEM0_CONFIG, VALID_CATEGORIES, CATEGORY_DESCRIPTIONS, MEMORY_CATEGORIZATION_PROMPT,
)

logger = logging.getLogger(__name__)


async def auto_categorize_memory(memory_text: str) -> List[str]:
    """使用 LLM 对记忆内容进行自动分类（异步 httpx，不阻塞事件循环）"""
    try:
        cat_text = "\n".join(f"- {k}: {v}" for k, v in CATEGORY_DESCRIPTIONS.items())
        prompt = MEMORY_CATEGORIZATION_PROMPT.format(
            categories=cat_text,
            memory_content=memory_text,
        )

        llm_config = MEM0_CONFIG.get("llm", {}).get("config", {})
        provider = MEM0_CONFIG.get("llm", {}).get("provider", "ollama")
        model = llm_config.get("model", "qwen2.5:7b")

        async with httpx.AsyncClient(timeout=30) as client:
            if provider == "ollama":
                ollama_base_url = llm_config.get("ollama_base_url", "http://localhost:11434")
                response = await client.post(
                    f"{ollama_base_url}/api/generate",
                    json={
                        "model": model,
                        "prompt": prompt,
                        "stream": False,
                        "format": "json",
                        "options": {"temperature": 0.1},
                    },
                )
            else:
                # OpenAI 兼容接口
                base_url = llm_config.get("openai_base_url", "https://api.openai.com/v1")
                api_key = llm_config.get("api_key", "")
                headers = {"Content-Type": "application/json"}
                if api_key:
                    headers["Authorization"] = f"Bearer {api_key}"
                response = await client.post(
                    f"{base_url}/chat/completions",
                    json={
                        "model": model,
                        "messages": [{"role": "user", "content": prompt}],
                        "temperature": 0.1,
                        "response_format": {"type": "json_object"},
                    },
                    headers=headers,
                )
            response.raise_for_status()

            if provider == "ollama":
                result_text = response.json().get("response", "")
            else:
                choices = response.json().get("choices", [])
                result_text = choices[0].get("message", {}).get("content", "") if choices else ""

        parsed = json.loads(result_text)
        raw_categories = parsed.get("categories", [])

        valid = [c for c in raw_categories if c in VALID_CATEGORIES]
        logger.info(f"AI 自动分类结果: {valid} (原始: {raw_categories})")
        return valid

    except Exception as e:
        logger.warning(f"AI 自动分类失败: {e}")
        return []
