"""
健康检查接口测试
"""

import pytest


class TestHealthCheck:
    """健康检查端点测试"""

    def test_health_check_returns_ok(self, client):
        """测试健康检查返回正常状态"""
        response = client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert "message" in data
        assert "Mem0 Dashboard API" in data["message"]

    def test_health_check_response_format(self, client):
        """测试健康检查响应格式正确"""
        response = client.get("/")
        data = response.json()
        assert isinstance(data, dict)
        assert "status" in data
        assert "message" in data
