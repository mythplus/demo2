"""
共享测试 Fixtures
提供 TestClient、Mock 数据库、Mock Mem0 实例等
"""

import os
import sys
import json
import sqlite3
import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from datetime import datetime

# 确保项目根目录在 sys.path 中
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


@pytest.fixture(scope="session", autouse=True)
def mock_env():
    """设置测试环境变量，避免加载真实配置"""
    os.environ["MEM0_ENV"] = "development"
    os.environ["OLLAMA_BASE_URL"] = "http://localhost:11434"
    os.environ["OLLAMA_MODEL"] = "qwen2.5:7b"
    os.environ["EMBED_MODEL"] = "nomic-embed-text"
    os.environ["NEO4J_URL"] = "bolt://localhost:7687"
    os.environ["NEO4J_USER"] = "neo4j"
    os.environ["NEO4J_PASSWORD"] = "test_password"


@pytest.fixture
def mock_memory():
    """Mock Mem0 Memory 实例"""
    mock = MagicMock()
    mock.add.return_value = {
        "results": [
            {"id": "test-id-1", "memory": "测试记忆内容", "event": "ADD"}
        ]
    }
    mock.get.return_value = {
        "id": "test-id-1",
        "memory": "测试记忆内容",
        "user_id": "user1",
        "hash": "abc123",
        "metadata": {"categories": ["work"], "state": "active"},
        "created_at": "2024-01-01T00:00:00",
        "updated_at": "2024-01-01T00:00:00",
    }
    mock.search.return_value = {
        "results": [
            {
                "id": "test-id-1",
                "memory": "测试记忆内容",
                "score": 0.95,
                "user_id": "user1",
                "metadata": {"categories": ["work"], "state": "active"},
            }
        ]
    }
    mock.update.return_value = {"message": "Memory updated successfully!"}
    mock.delete.return_value = {"message": "Memory deleted successfully!"}
    mock.delete_all.return_value = {"message": "Memories deleted successfully!"}
    mock.history.return_value = [
        {
            "id": "hist-1",
            "memory_id": "test-id-1",
            "old_memory": None,
            "new_memory": "测试记忆内容",
            "event": "ADD",
            "created_at": "2024-01-01T00:00:00",
        }
    ]

    # Mock vector_store 和 qdrant_client
    mock_qdrant = MagicMock()
    mock_point = MagicMock()
    mock_point.payload = {
        "data": "测试记忆内容",
        "metadata": {"categories": ["work"], "state": "active"},
        "user_id": "user1",
        "created_at": "2024-01-01T00:00:00",
        "updated_at": "2024-01-01T00:00:00",
    }
    mock_point.id = "test-id-1"
    mock_qdrant.scroll.return_value = ([mock_point], None)
    mock_qdrant.retrieve.return_value = [mock_point]
    mock_qdrant.set_payload.return_value = None
    mock.vector_store = MagicMock()
    mock.vector_store.client = mock_qdrant

    return mock


@pytest.fixture
def mock_neo4j_driver():
    """Mock Neo4j 驱动"""
    mock_driver = MagicMock()
    mock_session = MagicMock()
    mock_driver.session.return_value.__enter__ = MagicMock(return_value=mock_session)
    mock_driver.session.return_value.__exit__ = MagicMock(return_value=False)
    return mock_driver


@pytest.fixture
def in_memory_db():
    """创建内存 SQLite 数据库用于测试"""
    conn = sqlite3.connect(":memory:", check_same_thread=False)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS access_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            memory_id TEXT NOT NULL,
            action TEXT NOT NULL,
            memory_preview TEXT,
            timestamp TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS request_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            method TEXT NOT NULL,
            path TEXT NOT NULL,
            request_type TEXT,
            user_id TEXT,
            status_code INTEGER,
            latency_ms REAL,
            payload_summary TEXT,
            error TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS memory_change_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            memory_id TEXT NOT NULL,
            event TEXT NOT NULL,
            old_memory TEXT,
            new_memory TEXT,
            categories TEXT NOT NULL DEFAULT '[]',
            old_categories TEXT NOT NULL DEFAULT '[]',
            timestamp TEXT NOT NULL
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS category_snapshots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            memory_id TEXT NOT NULL,
            categories TEXT NOT NULL DEFAULT '[]',
            timestamp TEXT NOT NULL
        )
    """)
    conn.commit()
    yield conn
    conn.close()


@pytest.fixture
def client(mock_memory, in_memory_db):
    """创建 FastAPI TestClient（同步），注入 Mock 依赖"""
    from fastapi.testclient import TestClient

    # 在导入 server 之前先 mock 掉 Memory 初始化
    with patch("server.get_memory", return_value=mock_memory), \
         patch("server._get_db_conn", return_value=in_memory_db), \
         patch("server._init_access_log_db"), \
         patch("server._start_log_writer"), \
         patch("server._stop_log_writer"), \
         patch("server._close_neo4j_driver"), \
         patch("server._enqueue_log"), \
         patch("server._auto_categorize_memory", new_callable=AsyncMock, return_value=["work"]), \
         patch("server._configured_api_key", ""), \
         patch("server._rate_limit_rpm", 0):

        import server as srv
        from server import app

        # 清除速率限制中间件的请求记录（避免跨测试限流）
        # 遍历 ASGI 中间件栈，找到 RateLimitMiddleware 并清除其状态
        _current = getattr(app, "middleware_stack", None)
        while _current is not None:
            if hasattr(_current, "_requests"):
                _current._requests.clear()
            _current = getattr(_current, "app", None)

        yield TestClient(app, raise_server_exceptions=False)


# ============ 测试数据工厂 ============

@pytest.fixture
def sample_memory():
    """示例记忆数据"""
    return {
        "id": "test-id-1",
        "memory": "测试记忆内容",
        "user_id": "user1",
        "hash": "abc123",
        "categories": ["work"],
        "state": "active",
        "created_at": "2024-01-01T00:00:00",
        "updated_at": "2024-01-01T00:00:00",
    }


@pytest.fixture
def sample_add_request():
    """示例添加记忆请求"""
    return {
        "messages": [{"role": "user", "content": "我今天完成了项目报告"}],
        "user_id": "user1",
        "categories": ["work"],
        "state": "active",
        "infer": False,
        "auto_categorize": False,
    }


@pytest.fixture
def sample_search_request():
    """示例搜索请求"""
    return {
        "query": "项目报告",
        "user_id": "user1",
    }
