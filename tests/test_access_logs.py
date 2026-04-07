"""
访问日志接口测试
"""

import pytest
from datetime import datetime


class TestAccessLogs:
    """访问日志接口测试"""

    def test_get_access_logs(self, client, in_memory_db):
        """测试获取全局访问日志"""
        in_memory_db.execute(
            "INSERT INTO access_logs (memory_id, action, memory_preview, timestamp) VALUES (?, ?, ?, ?)",
            ("test-id-1", "view", "测试记忆预览", datetime.now().isoformat()),
        )
        in_memory_db.commit()
        response = client.get("/v1/access-logs/")
        assert response.status_code == 200
        data = response.json()
        assert "logs" in data

    def test_get_access_logs_with_memory_id(self, client, in_memory_db):
        """测试按记忆 ID 筛选访问日志"""
        in_memory_db.execute(
            "INSERT INTO access_logs (memory_id, action, memory_preview, timestamp) VALUES (?, ?, ?, ?)",
            ("test-id-1", "view", "测试", datetime.now().isoformat()),
        )
        in_memory_db.commit()
        response = client.get("/v1/access-logs/?memory_id=test-id-1")
        assert response.status_code == 200
        data = response.json()
        assert "logs" in data

    def test_get_memory_access_logs(self, client, in_memory_db):
        """测试获取单条记忆的访问日志"""
        in_memory_db.execute(
            "INSERT INTO access_logs (memory_id, action, memory_preview, timestamp) VALUES (?, ?, ?, ?)",
            ("test-id-1", "search", "搜索预览", datetime.now().isoformat()),
        )
        in_memory_db.commit()
        response = client.get("/v1/memories/test-id-1/access-logs/")
        assert response.status_code == 200
        data = response.json()
        assert "logs" in data

    def test_get_access_logs_with_limit(self, client, in_memory_db):
        """测试访问日志分页限制"""
        for i in range(10):
            in_memory_db.execute(
                "INSERT INTO access_logs (memory_id, action, memory_preview, timestamp) VALUES (?, ?, ?, ?)",
                (f"id-{i}", "view", f"预览{i}", datetime.now().isoformat()),
            )
        in_memory_db.commit()
        response = client.get("/v1/access-logs/?limit=5")
        assert response.status_code == 200
        data = response.json()
        assert len(data["logs"]) <= 5
