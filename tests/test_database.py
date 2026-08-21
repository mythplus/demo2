"""
Mem0 Dashboard 后端 - 数据库模块单元测试

运行方式: pytest tests/test_database.py -v
"""
import sys
import os
import tempfile
from pathlib import Path
from datetime import datetime

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


@pytest.fixture(autouse=True)
def temp_db(monkeypatch):
    """使用临时数据库，避免污染正式数据"""
    tmpdir = tempfile.mkdtemp()
    tmp_db_path = os.path.join(tmpdir, "test_access_logs.db")
    monkeypatch.setattr("app.database.ACCESS_LOG_DB_PATH", tmp_db_path)

    # 重置线程本地连接
    import app.database as db
    if hasattr(db._thread_local, "db_conn"):
        del db._thread_local.db_conn

    db.init_db()
    # 启动日志写入线程，确保异步队列中的日志被刷入 SQLite
    db.start_log_writer()
    yield
    db.stop_log_writer()
    # 清理
    for f in os.listdir(tmpdir):
        os.remove(os.path.join(tmpdir, f))
    os.rmdir(tmpdir)


class TestDatabaseInit:
    def test_init_db_creates_tables(self):
        """init_db 应创建所有必要的表"""
        import app.database as db
        conn = db._get_db_conn()
        tables = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
        table_names = [t[0] for t in tables]
        assert "access_logs" in table_names
        assert "request_logs" in table_names


class TestAccessLog:
    def test_log_access(self):
        """log_access 应成功写入访问日志"""
        import app.database as db
        import time as _time
        db.log_access(
            memory_id="test-mem-id",
            action="view",
            memory_preview="memory preview text",
        )
        _time.sleep(1)
        logs, total = db.get_access_logs(memory_id="test-mem-id", limit=10)
        assert total >= 1
        assert logs[0]["memory_id"] == "test-mem-id"
        assert logs[0]["action"] == "view"

    def test_get_access_logs_limit(self):
        """get_access_logs 应正确分页"""
        import app.database as db
        import time as _time
        for i in range(5):
            db.log_access(memory_id="limit-test", action="view")
        _time.sleep(1)
        logs, total = db.get_access_logs(memory_id="limit-test", limit=2)
        assert total >= 5
        assert len(logs) <= 2


class TestRequestLogs:
    def test_log_request(self):
        """log_request 应成功写入请求日志"""
        import app.database as db
        db.log_request(
            method="GET",
            path="/v1/memories/",
            request_type="memory",
            status_code=200,
            latency_ms=42.5,
        )
        # 等待异步日志写入线程处理
        import time as _time
        _time.sleep(1)
        logs, total = db.get_request_logs(limit=10)
        assert total >= 1
        assert logs[0]["method"] == "GET"
        assert logs[0]["path"] == "/v1/memories/"
        assert logs[0]["status_code"] == 200

    def test_filter_by_request_type(self):
        """按类型筛选请求日志"""
        import app.database as db
        import time as _time
        db.log_request(method="GET", path="/v1/graph/stats", request_type="graph", status_code=200, latency_ms=10)
        db.log_request(method="GET", path="/v1/memories/", request_type="memory", status_code=200, latency_ms=5)
        _time.sleep(1)

        logs, total = db.get_request_logs(request_type="graph")
        assert total >= 1
        assert all(l["request_type"] == "graph" for l in logs)

    def test_filter_by_date_range(self):
        """按日期范围筛选"""
        import app.database as db
        import time as _time
        db.log_request(method="GET", path="/test", request_type="test", status_code=200, latency_ms=1)
        # 等待异步日志写入线程处理（flush interval is 5s）
        _time.sleep(6)

        # 查询今天的日志（使用 ISO 日期格式匹配数据库存储格式）
        today = datetime.now().strftime("%Y-%m-%d")
        logs, total = db.get_request_logs(since=today)
        assert total >= 1
