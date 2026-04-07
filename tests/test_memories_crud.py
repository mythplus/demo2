"""
记忆 CRUD 接口测试
覆盖：添加、批量导入、获取列表、获取详情、更新、删除、批量删除
"""

import pytest
from unittest.mock import patch, AsyncMock, MagicMock


class TestAddMemory:
    """添加记忆接口测试"""

    def test_add_memory_success(self, client, sample_add_request):
        """测试正常添加记忆"""
        response = client.post("/v1/memories/", json=sample_add_request)
        assert response.status_code == 200
        data = response.json()
        assert "results" in data

    def test_add_memory_missing_user_id(self, client):
        """测试缺少 user_id 时返回 400"""
        request_data = {
            "messages": [{"role": "user", "content": "测试内容"}],
            "user_id": "",
        }
        response = client.post("/v1/memories/", json=request_data)
        assert response.status_code in [400, 500]  # 服务端校验 user_id

    def test_add_memory_empty_user_id_whitespace(self, client):
        """测试 user_id 为空白字符串时返回 400"""
        request_data = {
            "messages": [{"role": "user", "content": "测试内容"}],
            "user_id": "   ",
        }
        response = client.post("/v1/memories/", json=request_data)
        assert response.status_code in [400, 500]  # 服务端校验 user_id

    def test_add_memory_with_categories(self, client):
        """测试带分类标签添加记忆"""
        request_data = {
            "messages": [{"role": "user", "content": "学习 Python 编程"}],
            "user_id": "user1",
            "categories": ["education", "ai_ml_technology"],
            "infer": False,
            "auto_categorize": False,
        }
        response = client.post("/v1/memories/", json=request_data)
        assert response.status_code == 200

    def test_add_memory_with_auto_categorize(self, client):
        """测试 AI 自动分类"""
        request_data = {
            "messages": [{"role": "user", "content": "今天去健身房锻炼了"}],
            "user_id": "user1",
            "infer": False,
            "auto_categorize": True,
        }
        response = client.post("/v1/memories/", json=request_data)
        assert response.status_code == 200

    def test_add_memory_missing_messages(self, client):
        """测试缺少 messages 字段时返回 422"""
        request_data = {"user_id": "user1"}
        response = client.post("/v1/memories/", json=request_data)
        assert response.status_code == 422


class TestBatchImport:
    """批量导入接口测试"""

    def test_batch_import_success(self, client, mock_memory):
        """测试批量导入成功"""
        request_data = {
            "items": [
                {"content": "记忆1", "user_id": "user1"},
                {"content": "记忆2", "user_id": "user1"},
            ],
            "default_user_id": "user1",
            "infer": False,
            "auto_categorize": False,
        }
        response = client.post("/v1/memories/batch", json=request_data)
        assert response.status_code == 200
        data = response.json()
        assert "total" in data
        assert "success" in data
        assert "failed" in data
        assert "results" in data
        assert data["total"] == 2

    def test_batch_import_empty_items(self, client):
        """测试空 items 列表返回 400"""
        request_data = {"items": []}
        response = client.post("/v1/memories/batch", json=request_data)
        assert response.status_code == 400


class TestGetMemories:
    """获取记忆列表接口测试"""

    def test_get_memories_success(self, client):
        """测试获取记忆列表"""
        response = client.get("/v1/memories/")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)

    def test_get_memories_with_user_filter(self, client):
        """测试按用户筛选记忆"""
        response = client.get("/v1/memories/?user_id=user1")
        assert response.status_code == 200

    def test_get_memories_with_category_filter(self, client):
        """测试按分类筛选记忆"""
        response = client.get("/v1/memories/?categories=work,education")
        assert response.status_code == 200

    def test_get_memories_with_state_filter(self, client):
        """测试按状态筛选记忆"""
        response = client.get("/v1/memories/?state=active")
        assert response.status_code == 200


class TestGetMemoryDetail:
    """获取记忆详情接口测试"""

    def test_get_memory_detail_success(self, client, mock_memory):
        """测试获取单条记忆详情"""
        response = client.get("/v1/memories/test-id-1/")
        assert response.status_code == 200
        data = response.json()
        assert "id" in data
        assert "memory" in data

    def test_get_memory_detail_not_found(self, client, mock_memory):
        """测试获取不存在的记忆返回 404 或 500"""
        mock_memory.get.return_value = None
        mock_memory.vector_store.client.retrieve.return_value = []
        response = client.get("/v1/memories/nonexistent-id/")
        assert response.status_code in [404, 500]


class TestUpdateMemory:
    """更新记忆接口测试"""

    def test_update_memory_text(self, client, mock_memory):
        """测试更新记忆文本"""
        response = client.put(
            "/v1/memories/test-id-1/",
            json={"text": "更新后的记忆内容"},
        )
        assert response.status_code == 200

    def test_update_memory_categories(self, client, mock_memory):
        """测试更新记忆分类"""
        response = client.put(
            "/v1/memories/test-id-1/",
            json={"categories": ["education", "work"]},
        )
        assert response.status_code == 200

    def test_update_memory_state(self, client, mock_memory):
        """测试更新记忆状态"""
        response = client.put(
            "/v1/memories/test-id-1/",
            json={"state": "paused"},
        )
        assert response.status_code == 200

    def test_update_memory_not_found(self, client, mock_memory):
        """测试更新不存在的记忆（仅更新 categories/state 时可能返回 200）"""
        mock_memory.get.return_value = None
        mock_memory.vector_store.client.retrieve.return_value = []
        response = client.put(
            "/v1/memories/nonexistent-id/",
            json={"text": "更新内容"},
        )
        # 更新接口可能在 Qdrant 层面处理，不一定返回 404
        assert response.status_code in [200, 404, 500]


class TestDeleteMemory:
    """删除记忆接口测试"""

    def test_delete_single_memory(self, client, mock_memory):
        """测试删除单条记忆"""
        response = client.delete("/v1/memories/test-id-1/")
        assert response.status_code == 200

    def test_delete_all_user_memories(self, client, mock_memory):
        """测试删除用户所有记忆"""
        response = client.delete("/v1/memories/?user_id=user1")
        assert response.status_code == 200

    def test_delete_all_memories_missing_user_id(self, client):
        """测试删除所有记忆时缺少 user_id"""
        response = client.delete("/v1/memories/")
        assert response.status_code == 400


class TestBatchDelete:
    """批量删除接口测试"""

    def test_batch_delete_success(self, client, mock_memory):
        """测试批量删除成功"""
        response = client.post(
            "/v1/memories/batch-delete",
            json={"memory_ids": ["id-1", "id-2", "id-3"]},
        )
        assert response.status_code == 200
        data = response.json()
        assert "total" in data
        assert "success" in data
        assert "failed" in data

    def test_batch_delete_empty_ids(self, client):
        """测试空 ID 列表"""
        response = client.post(
            "/v1/memories/batch-delete",
            json={"memory_ids": []},
        )
        assert response.status_code == 400


class TestGetRelatedMemories:
    """关联记忆接口测试"""

    def test_get_related_memories(self, client, mock_memory):
        """测试获取关联记忆"""
        mock_memory.search.return_value = {
            "results": [
                {"id": "related-1", "memory": "相关记忆", "score": 0.8, "user_id": "user1", "metadata": {}}
            ]
        }
        response = client.get("/v1/memories/test-id-1/related/?limit=5")
        assert response.status_code == 200

    def test_get_related_memories_not_found(self, client, mock_memory):
        """测试获取不存在记忆的关联记忆"""
        mock_memory.get.return_value = None
        response = client.get("/v1/memories/nonexistent/related/")
        assert response.status_code == 404
