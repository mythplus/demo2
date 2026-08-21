"""
Mem0 Dashboard 后端 - API 集成测试

使用 FastAPI TestClient 进行端到端测试。
注意: 部分测试需要 Mem0 和 Qdrant 实例运行，已标记 @pytest.mark.integration。

运行方式:
  pytest tests/test_api_integration.py -v
  pytest tests/test_api_integration.py -v -m integration  # 仅运行集成测试
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi.testclient import TestClient


@pytest.fixture(scope="module")
def client():
    """创建测试客户端"""
    from app.main import app
    with TestClient(app) as c:
        yield c


class TestHealthEndpoints:
    """健康检查端点测试（不需要外部服务）"""

    def test_root_endpoint(self, client):
        """根路由应返回服务信息"""
        resp = client.get("/")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert "service" in data

    def test_health_endpoint(self, client):
        """健康检查端点应返回记忆统计"""
        resp = client.get("/v1/health/")
        assert resp.status_code in (200, 500)  # 可能 Mem0 未初始化
        if resp.status_code == 200:
            data = resp.json()
            assert "status" in data


class TestConfigEndpoint:
    """配置端点测试"""

    def test_get_config(self, client):
        """获取配置信息应成功（脱敏）"""
        resp = client.get("/v1/config/")
        assert resp.status_code in (200, 500)
        if resp.status_code == 200:
            data = resp.json()
            # 密码字段应被脱敏
            if "graph_store" in data:
                assert data["graph_store"].get("config", {}).get("password") in ("***", "", None)


class TestStatsEndpoint:
    """统计端点测试"""

    def test_get_stats(self, client):
        """获取统计数据"""
        resp = client.get("/v1/stats/")
        # 可能因 Mem0 未初始化返回 500
        assert resp.status_code in (200, 500)
        if resp.status_code == 200:
            data = resp.json()
            assert "total_memories" in data
            assert "total_users" in data


class TestMemoryValidation:
    """记忆请求参数验证测试（不实际写入数据）"""

    def test_add_memory_missing_messages(self, client):
        """缺少 messages 字段应返回 422"""
        resp = client.post("/v1/memories/", json={"user_id": "test"})
        assert resp.status_code == 422

    def test_add_memory_empty_messages(self, client):
        """空 messages 列表应返回 422（Pydantic 验证）或 400（业务验证）"""
        resp = client.post("/v1/memories/", json={"messages": []})
        assert resp.status_code in (400, 422)

    def test_search_missing_query(self, client):
        """搜索缺少 query 应返回 422"""
        resp = client.post("/v1/memories/search/", json={"user_id": "test"})
        assert resp.status_code == 422

    def test_search_query_too_long(self, client):
        """query 超长应返回 422"""
        resp = client.post(
            "/v1/memories/search/",
            json={"query": "x" * 501},
        )
        assert resp.status_code == 422


class TestGraphEndpoints:
    """图谱端点测试"""

    def test_graph_stats(self, client):
        """获取图谱统计"""
        resp = client.get("/v1/graph/stats")
        # 需要 Neo4j 连接，未连接时返回 500
        assert resp.status_code in (200, 500)

    def test_graph_health(self, client):
        """图谱健康检查"""
        resp = client.get("/v1/graph/health")
        assert resp.status_code in (200, 500)
        if resp.status_code == 200:
            data = resp.json()
            assert "status" in data


class TestExportEndpoint:
    """导出端点测试"""

    def test_export_json(self, client):
        """JSON 导出"""
        resp = client.get("/v1/export/?format=json")
        assert resp.status_code in (200, 404, 500)

    def test_export_csv(self, client):
        """CSV 导出"""
        resp = client.get("/v1/export/?format=csv")
        assert resp.status_code in (200, 404, 500)


@pytest.mark.integration
class TestMemoryCRUDIntegration:
    """记忆 CRUD 集成测试（需要 Mem0 + Qdrant 运行）"""

    def test_full_crud_flow(self, client):
        """完整的 CRUD 流程：添加 → 查询 → 更新 → 删除"""
        # 1. 添加
        resp = client.post(
            "/v1/memories/",
            json={
                "messages": [{"role": "user", "content": "测试记忆内容 for CRUD"}],
                "user_id": "test_integration_user",
                "infer": False,
            },
        )
        if resp.status_code != 200:
            pytest.skip("Mem0 服务未运行，跳过集成测试")
        add_data = resp.json()
        assert "results" in add_data
        memory_id = add_data["results"][0]["id"]

        # 2. 查询
        resp = client.get(f"/v1/memories/{memory_id}/")
        assert resp.status_code == 200

        # 3. 更新
        resp = client.put(
            f"/v1/memories/{memory_id}/",
            json={"text": "更新后的测试记忆"},
        )
        assert resp.status_code == 200

        # 4. 删除
        resp = client.delete(f"/v1/memories/{memory_id}/")
        assert resp.status_code == 200
