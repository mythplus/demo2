"""
Mem0 Dashboard 后端 - memory_engine 模块单元测试

运行方式: pytest tests/test_memory_engine.py -v
"""
import sys
from pathlib import Path
from datetime import datetime, timezone

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.memory_engine import extract_memory_fields, apply_filters


class TestExtractMemoryFields:
    """测试 Qdrant payload 字段提取"""

    def test_full_payload(self):
        payload = {
            "id": "test-id-123",
            "data": "some memory content",
            "user_id": "user1",
            "agent_id": "agent1",
            "run_id": "run1",
            "hash": "abc123",
            "metadata": {
                "categories": ["work", "projects"],
                "state": "active",
            },
            "created_at": "2025-01-01T00:00:00Z",
            "updated_at": "2025-01-02T00:00:00Z",
        }
        result = extract_memory_fields(payload)
        assert result["id"] == "test-id-123"
        assert result["memory"] == "some memory content"
        assert result["user_id"] == "user1"
        assert result["categories"] == ["work", "projects"]
        assert result["state"] == "active"

    def test_minimal_payload(self):
        payload = {}
        result = extract_memory_fields(payload)
        assert result["id"] == ""
        assert result["memory"] == ""
        assert result["state"] == "active"  # 默认值
        assert result["categories"] == []

    def test_metadata_is_none(self):
        payload = {"metadata": None}
        result = extract_memory_fields(payload)
        assert result["metadata"] == {}
        assert result["categories"] == []

    def test_fallback_memory_field(self):
        """payload 中没有 data 但有 memory 字段"""
        payload = {"memory": "fallback content"}
        result = extract_memory_fields(payload)
        assert result["memory"] == "fallback content"


class TestApplyFilters:
    """测试记忆列表多维筛选"""

    @pytest.fixture
    def sample_memories(self):
        return [
            {
                "id": "1", "memory": "学习 Python 编程", "user_id": "user_a",
                "state": "active", "categories": ["education", "projects"],
                "created_at": "2025-06-01T10:00:00Z",
            },
            {
                "id": "2", "memory": "健身计划", "user_id": "user_b",
                "state": "paused", "categories": ["health"],
                "created_at": "2025-06-15T10:00:00Z",
            },
            {
                "id": "3", "memory": "Python 项目部署", "user_id": "user_a",
                "state": "active", "categories": ["projects", "work"],
                "created_at": "2025-07-01T10:00:00Z",
            },
            {
                "id": "4", "memory": "已删除的记录", "user_id": "user_c",
                "state": "deleted", "categories": [],
                "created_at": "2025-07-10T10:00:00Z",
            },
        ]

    def test_no_filter(self, sample_memories):
        result = apply_filters(sample_memories)
        assert len(result) == len(sample_memories)

    def test_filter_by_state(self, sample_memories):
        result = apply_filters(sample_memories, state="active")
        assert len(result) == 2
        assert all(m["state"] == "active" for m in result)

    def test_filter_by_categories(self, sample_memories):
        result = apply_filters(sample_memories, categories=["projects"])
        assert len(result) == 2
        assert all("projects" in m["categories"] for m in result)

    def test_filter_by_multiple_categories(self, sample_memories):
        result = apply_filters(sample_memories, categories=["health", "work"])
        assert len(result) == 2

    def test_filter_by_search(self, sample_memories):
        result = apply_filters(sample_memories, search="python")
        assert len(result) == 2
        assert all("python" in m["memory"].lower() for m in result)

    def test_filter_by_search_user_id(self, sample_memories):
        result = apply_filters(sample_memories, search="user_a")
        assert len(result) == 2

    def test_filter_by_date_from(self, sample_memories):
        result = apply_filters(sample_memories, date_from="2025-07-01")
        assert len(result) == 2

    def test_filter_by_date_to(self, sample_memories):
        result = apply_filters(sample_memories, date_to="2025-06-30")
        assert len(result) == 2

    def test_filter_combined(self, sample_memories):
        result = apply_filters(
            sample_memories,
            state="active",
            categories=["projects"],
            search="python",
        )
        assert len(result) == 2

    def test_filter_no_match(self, sample_memories):
        result = apply_filters(sample_memories, search="nonexistent_keyword_xyz")
        assert len(result) == 0

    def test_filter_empty_list(self):
        assert apply_filters([]) == []

    def test_filter_invalid_date(self, sample_memories):
        """无效日期不应抛异常，应忽略筛选"""
        result = apply_filters(sample_memories, date_from="invalid-date")
        assert len(result) == len(sample_memories)
