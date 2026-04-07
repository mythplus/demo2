"""
语义搜索接口测试
"""

import pytest
from unittest.mock import patch, MagicMock


class TestSearchMemories:
    """语义搜索记忆测试"""

    def test_search_memories_success(self, client, sample_search_request):
        """测试正常搜索"""
        response = client.post("/v1/memories/search/", json=sample_search_request)
        assert response.status_code == 200
        data = response.json()
        assert "results" in data
        assert isinstance(data["results"], list)

    def test_search_memories_with_user_id(self, client):
        """测试按用户搜索"""
        response = client.post(
            "/v1/memories/search/",
            json={"query": "测试搜索", "user_id": "user1"},
        )
        assert response.status_code == 200
        data = response.json()
        assert "results" in data

    def test_search_memories_empty_query(self, client):
        """测试空查询字符串"""
        response = client.post(
            "/v1/memories/search/",
            json={"query": ""},
        )
        assert response.status_code in [200, 422]

    def test_search_memories_with_limit(self, client):
        """测试带 limit 参数的搜索"""
        response = client.post(
            "/v1/memories/search/",
            json={"query": "测试", "limit": 3},
        )
        assert response.status_code == 200

    def test_search_results_exclude_deleted(self, client, mock_memory):
        """测试搜索结果排除已删除的记忆"""
        mock_memory.search.return_value = {
            "results": [
                {"id": "id-1", "memory": "活跃记忆", "score": 0.9, "user_id": "user1", "metadata": {"state": "active"}},
                {"id": "id-2", "memory": "已删除记忆", "score": 0.8, "user_id": "user1", "metadata": {"state": "deleted"}},
            ]
        }
        response = client.post(
            "/v1/memories/search/",
            json={"query": "测试", "user_id": "user1"},
        )
        assert response.status_code == 200
        data = response.json()
        for result in data.get("results", []):
            assert result.get("state") != "deleted"


class TestMemoryHistory:
    """记忆修改历史测试"""

    def test_get_memory_history(self, client, mock_memory):
        """测试获取记忆修改历史"""
        response = client.get("/v1/memories/history/test-id-1/")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)

    def test_get_memory_history_empty(self, client, mock_memory):
        """测试获取无历史记录的记忆"""
        mock_memory.history.return_value = []
        response = client.get("/v1/memories/history/no-history-id/")
        assert response.status_code == 200
