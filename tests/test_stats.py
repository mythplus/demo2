"""
统计接口测试
"""

import pytest


class TestStats:
    """统计数据接口测试"""

    def test_get_stats_success(self, client):
        """测试获取统计数据"""
        response = client.get("/v1/stats/")
        assert response.status_code == 200
        data = response.json()
        assert "total_memories" in data
        assert "total_users" in data
        assert "category_distribution" in data
        assert "state_distribution" in data
        assert "daily_trend" in data

    def test_stats_category_distribution_format(self, client):
        """测试分类分布格式正确"""
        response = client.get("/v1/stats/")
        data = response.json()
        cat_dist = data["category_distribution"]
        assert isinstance(cat_dist, dict)
        expected_categories = [
            "personal", "relationships", "preferences", "health", "travel",
            "work", "education", "projects", "ai_ml_technology", "technical_support",
            "finance", "shopping", "legal", "entertainment", "messages",
            "customer_support", "product_feedback", "news", "organization", "goals",
        ]
        for cat in expected_categories:
            assert cat in cat_dist

    def test_stats_state_distribution_format(self, client):
        """测试状态分布格式正确"""
        response = client.get("/v1/stats/")
        data = response.json()
        state_dist = data["state_distribution"]
        assert isinstance(state_dist, dict)
        for state in ["active", "paused", "deleted"]:
            assert state in state_dist

    def test_stats_daily_trend_format(self, client):
        """测试每日趋势格式正确（30 天数据）"""
        response = client.get("/v1/stats/")
        data = response.json()
        daily_trend = data["daily_trend"]
        assert isinstance(daily_trend, list)
        assert len(daily_trend) == 30
        for item in daily_trend:
            assert "date" in item
            assert "count" in item
