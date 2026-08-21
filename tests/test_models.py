"""
Mem0 Dashboard 后端 - 数据模型单元测试

运行方式: pytest tests/test_models.py -v
"""
import sys
from pathlib import Path

import pytest
from pydantic import ValidationError

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.models import (
    MemoryMessage,
    AddMemoryRequest,
    SearchMemoryRequest,
    UpdateMemoryRequest,
    BatchImportItem,
    BatchImportRequest,
    BatchDeleteRequest,
    GraphSearchRequest,
)


class TestMemoryMessage:
    def test_valid_message(self):
        msg = MemoryMessage(role="user", content="hello world")
        assert msg.role == "user"
        assert msg.content == "hello world"

    def test_role_max_length(self):
        with pytest.raises(ValidationError):
            MemoryMessage(role="x" * 21, content="content")

    def test_content_max_length(self):
        with pytest.raises(ValidationError):
            MemoryMessage(role="user", content="x" * 10001)

    def test_missing_fields(self):
        with pytest.raises(ValidationError):
            MemoryMessage(role="user")  # 缺少 content


class TestAddMemoryRequest:
    def test_valid_request(self):
        req = AddMemoryRequest(
            messages=[MemoryMessage(role="user", content="test")],
            user_id="user1",
        )
        assert req.user_id == "user1"
        assert req.infer is True  # 默认值
        assert req.auto_categorize is True  # 默认值

    def test_default_state(self):
        req = AddMemoryRequest(
            messages=[MemoryMessage(role="user", content="test")],
        )
        assert req.state == "active"

    def test_messages_max_length(self):
        msgs = [MemoryMessage(role="user", content=f"msg {i}") for i in range(51)]
        with pytest.raises(ValidationError):
            AddMemoryRequest(messages=msgs)

    def test_empty_messages_allowed(self):
        """空 messages 列表通过 Pydantic 校验（业务层拦截）"""
        req = AddMemoryRequest(messages=[])
        assert len(req.messages) == 0


class TestSearchMemoryRequest:
    def test_valid_search(self):
        req = SearchMemoryRequest(query="test query")
        assert req.query == "test query"
        assert req.limit == 10  # 默认值

    def test_query_max_length(self):
        with pytest.raises(ValidationError):
            SearchMemoryRequest(query="x" * 501)

    def test_limit_range(self):
        with pytest.raises(ValidationError):
            SearchMemoryRequest(query="test", limit=0)  # < 1
        with pytest.raises(ValidationError):
            SearchMemoryRequest(query="test", limit=101)  # > 100

    def test_limit_boundary(self):
        req = SearchMemoryRequest(query="test", limit=1)
        assert req.limit == 1
        req = SearchMemoryRequest(query="test", limit=100)
        assert req.limit == 100


class TestUpdateMemoryRequest:
    def test_all_optional(self):
        req = UpdateMemoryRequest()
        assert req.text is None
        assert req.metadata is None
        assert req.categories is None
        assert req.state is None
        assert req.auto_categorize is False  # 默认值

    def test_categories_max_length(self):
        with pytest.raises(ValidationError):
            UpdateMemoryRequest(categories=["cat"] * 21)


class TestBatchImportRequest:
    def test_valid_batch(self):
        req = BatchImportRequest(
            items=[
                BatchImportItem(content="memory 1", user_id="u1"),
                BatchImportItem(content="memory 2"),
            ],
        )
        assert len(req.items) == 2
        assert req.infer is False  # 默认值
        assert req.auto_categorize is True  # 默认值

    def test_items_max_length(self):
        items = [BatchImportItem(content=f"item {i}") for i in range(101)]
        with pytest.raises(ValidationError):
            BatchImportRequest(items=items)

    def test_batch_item_defaults(self):
        item = BatchImportItem(content="test")
        assert item.state == "active"  # 默认值


class TestBatchDeleteRequest:
    def test_valid_batch_delete(self):
        req = BatchDeleteRequest(memory_ids=["id1", "id2", "id3"])
        assert len(req.memory_ids) == 3

    def test_empty_ids_allowed(self):
        """空 memory_ids 列表通过 Pydantic 校验（业务层拦截）"""
        req = BatchDeleteRequest(memory_ids=[])
        assert len(req.memory_ids) == 0

    def test_max_ids(self):
        with pytest.raises(ValidationError):
            BatchDeleteRequest(memory_ids=["id"] * 101)


class TestGraphSearchRequest:
    def test_valid_search(self):
        req = GraphSearchRequest(query="entity search")
        assert req.query == "entity search"
        assert req.limit == 20  # 默认值

    def test_limit_range(self):
        with pytest.raises(ValidationError):
            GraphSearchRequest(query="test", limit=0)
        with pytest.raises(ValidationError):
            GraphSearchRequest(query="test", limit=201)

    def test_limit_boundary(self):
        req = GraphSearchRequest(query="test", limit=1)
        assert req.limit == 1
        req = GraphSearchRequest(query="test", limit=200)
        assert req.limit == 200
