"""
健康检查 / 配置信息 / 连接测试接口测试

注意：主要测试通过 FastAPI TestClient（依赖 conftest.client fixture，需要 psycopg2）。
本文件为了规避本地 Python 3.14 + psycopg2 未编译的环境限制，
对 app 导入链做了轻量 stub，让测试能在任意 Python 环境下跑起来。
"""

import sys
from types import ModuleType
from unittest.mock import patch, MagicMock


# ============ 导入保护：在 conftest 尝试 import server.app 前先 stub 掉 psycopg2 ============
# 这里会在模块加载期生效，早于 conftest 的 fixture 被调用。
# 作用是让本地/CI 没装 psycopg2 驱动时，也能跑通这些仅依赖 health.py 逻辑的接口测试。
def _ensure_psycopg2_stub():
    for name in ("psycopg2", "psycopg2.extras", "psycopg2.pool"):
        if name not in sys.modules:
            stub = ModuleType(name)
            # psycopg2.pool 要求 ThreadedConnectionPool 类
            if name == "psycopg2.pool":
                stub.ThreadedConnectionPool = MagicMock  # type: ignore[attr-defined]
            # psycopg2.extras 常用 RealDictCursor
            if name == "psycopg2.extras":
                stub.RealDictCursor = MagicMock  # type: ignore[attr-defined]
            # 顶层 psycopg2 常用 OperationalError
            if name == "psycopg2":
                stub.OperationalError = type("OperationalError", (Exception,), {})  # type: ignore[attr-defined]
                stub.extras = sys.modules.get("psycopg2.extras")  # type: ignore[attr-defined]
                stub.pool = sys.modules.get("psycopg2.pool")  # type: ignore[attr-defined]
            sys.modules[name] = stub


_ensure_psycopg2_stub()


class TestHealthCheck:
    """基础健康检查端点测试"""

    def test_health_check_returns_ok(self, client):
        """测试 / 健康检查返回正常状态"""
        response = client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert "message" in data
        assert "Mem0 Dashboard API" in data["message"]

    def test_health_check_alias_ok(self, client):
        """测试 /health 别名端点也返回正常状态"""
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"

    def test_health_check_response_format(self, client):
        """测试健康检查响应格式正确"""
        response = client.get("/")
        data = response.json()
        assert isinstance(data, dict)
        assert "status" in data
        assert "message" in data


class TestConfigInfo:
    """/v1/config/info 测试：含向量库 / 元数据库 / 图数据库 / LLM / Embedder 全量字段"""

    def test_config_info_has_all_blocks(self, client):
        """返回应包含全部 5 大块：llm / embedder / vector_store / graph_store / meta_store"""
        response = client.get("/v1/config/info")
        assert response.status_code == 200
        data = response.json()
        for block in ("llm", "embedder", "vector_store", "graph_store", "meta_store"):
            assert block in data, f"缺少 {block}"

    def test_config_info_vector_store_has_url(self, client):
        """向量库块现在必须包含 url 字段（空串也算）"""
        data = client.get("/v1/config/info").json()
        vs = data["vector_store"]
        for key in ("provider", "collection_name", "embedding_model_dims", "url"):
            assert key in vs, f"vector_store 缺少 {key}"

    def test_config_info_meta_store_shape(self, client):
        """元数据库块应包含 provider / host / port / database / url，且 URL 不含凭据"""
        data = client.get("/v1/config/info").json()
        ms = data["meta_store"]
        for key in ("provider", "host", "port", "database", "url"):
            assert key in ms, f"meta_store 缺少 {key}"
        # 无论 DSN 里是否带密码，展示 URL 都不应含 @
        assert "@" not in ms["url"], f"meta_store.url 不应包含凭据: {ms['url']}"


class TestVectorStoreConnection:
    """/v1/config/test-vector 测试"""

    def test_test_vector_success(self, client, mock_memory):
        """Mock Qdrant get_collection 返回正常信息，接口应返回 connected"""
        fake_vectors = MagicMock(size=768)
        fake_info = MagicMock()
        fake_info.config.params.vectors = fake_vectors
        fake_info.points_count = 42
        mock_memory.vector_store.client.get_collection.return_value = fake_info

        resp = client.get("/v1/config/test-vector")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "connected"
        assert data["points_count"] == 42
        assert data["dimensions"] == 768
        assert data["dimensions_match"] is True
        assert "Qdrant" in data["message"]

    def test_test_vector_error(self, client, mock_memory):
        """Qdrant 抛异常时，接口应返回 error 且包含错误描述"""
        mock_memory.vector_store.client.get_collection.side_effect = RuntimeError(
            "connection refused"
        )
        resp = client.get("/v1/config/test-vector")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "error"
        assert "连接失败" in data["message"]


class TestMetaStoreConnection:
    """/v1/config/test-meta 测试：mock SQLAlchemy engine 的 execute 返回"""

    def test_test_meta_success(self, client):
        """Mock engine 正常返回版本号和计数，接口应返回 connected"""
        class _FakeScalarResult:
            def __init__(self, value):
                self._value = value

            def scalar(self):
                return self._value

        call_counter = {"n": 0}

        def _exec(_stmt):
            call_counter["n"] += 1
            # 第 1 次 SELECT 1；第 2 次 version()；第 3 次 COUNT
            if call_counter["n"] == 1:
                return _FakeScalarResult(1)
            if call_counter["n"] == 2:
                return _FakeScalarResult(
                    "PostgreSQL 15.3 on x86_64-pc-linux-gnu, compiled by gcc"
                )
            return _FakeScalarResult(7)

        fake_conn = MagicMock()
        fake_conn.execute.side_effect = _exec
        fake_engine = MagicMock()
        fake_engine.connect.return_value.__enter__.return_value = fake_conn
        fake_engine.connect.return_value.__exit__.return_value = False

        with patch("server.models.database.get_engine", return_value=fake_engine):
            resp = client.get("/v1/config/test-meta")

        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "connected"
        assert data["memories_count"] == 7
        assert "PostgreSQL" in (data.get("server_version") or "")
        assert "PostgreSQL" in data["message"]

    def test_test_meta_error(self, client):
        """engine.connect 抛异常时应返回 error 状态"""
        fake_engine = MagicMock()
        fake_engine.connect.side_effect = RuntimeError("FATAL: password authentication failed")

        with patch("server.models.database.get_engine", return_value=fake_engine):
            resp = client.get("/v1/config/test-meta")

        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "error"
        assert "连接失败" in data["message"]
