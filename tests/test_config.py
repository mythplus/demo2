"""
系统配置接口测试
"""

import pytest
from unittest.mock import patch, AsyncMock, MagicMock


class TestConfigInfo:
    """系统配置信息接口测试"""

    def test_get_config_info(self, client):
        """测试获取系统配置信息"""
        response = client.get("/v1/config/info")
        assert response.status_code == 200
        data = response.json()
        assert "llm" in data
        assert "embedder" in data
        assert "vector_store" in data
        assert "graph_store" in data

    def test_config_info_llm_fields(self, client):
        """测试 LLM 配置字段完整"""
        response = client.get("/v1/config/info")
        data = response.json()
        llm = data["llm"]
        assert "provider" in llm
        assert "model" in llm
        assert "base_url" in llm

    def test_config_info_embedder_fields(self, client):
        """测试 Embedder 配置字段完整"""
        response = client.get("/v1/config/info")
        data = response.json()
        embedder = data["embedder"]
        assert "provider" in embedder
        assert "model" in embedder


class TestLLMConnectionTest:
    """LLM 连接测试接口"""

    def test_test_llm_connection(self, client):
        """测试 LLM 连接测试端点"""
        with patch("server._http_client") as mock_client:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"models": [{"name": "qwen2.5:7b"}]}
            mock_client.get = AsyncMock(return_value=mock_response)

            mock_chat_response = MagicMock()
            mock_chat_response.status_code = 200
            mock_chat_response.json.return_value = {"message": {"content": "Hello!"}}
            mock_client.post = AsyncMock(return_value=mock_chat_response)

            response = client.get("/v1/config/test-llm")
            assert response.status_code == 200
            data = response.json()
            assert "status" in data
            assert "provider" in data
            assert "model" in data


class TestEmbedderConnectionTest:
    """Embedder 连接测试接口"""

    def test_test_embedder_connection(self, client):
        """测试 Embedder 连接测试端点"""
        with patch("server._http_client") as mock_client:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"embedding": [0.1] * 768}
            mock_client.post = AsyncMock(return_value=mock_response)

            response = client.get("/v1/config/test-embedder")
            assert response.status_code == 200
            data = response.json()
            assert "status" in data
            assert "provider" in data
