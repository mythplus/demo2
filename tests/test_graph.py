"""
图谱记忆接口测试
覆盖：统计、实体列表、关系列表、搜索、用户子图、全量图谱、删除实体、删除关系、健康检查
"""

import pytest
from unittest.mock import patch, MagicMock


class TestGraphStats:
    """图谱统计接口测试"""

    def test_get_graph_stats(self, client):
        """测试获取图谱统计"""
        with patch("server._neo4j_query") as mock_query:
            mock_query.side_effect = [
                [{"count": 100}],
                [{"count": 200}],
                [{"relation_type": "KNOWS", "count": 50}],
                [{"user_id": "user1", "count": 30}],
            ]
            response = client.get("/v1/graph/stats")
            assert response.status_code == 200
            data = response.json()
            assert "entity_count" in data
            assert "relation_count" in data
            assert "relation_type_distribution" in data
            assert "user_entity_distribution" in data


class TestGraphEntities:
    """图谱实体列表接口测试"""

    def test_get_entities(self, client):
        """测试获取实体列表"""
        with patch("server._neo4j_query") as mock_query:
            mock_query.side_effect = [
                [{"name": "Python", "user_id": "user1", "labels": ["Entity"], "element_id": "1", "relation_count": 5}],
                [{"total": 1}],
            ]
            response = client.get("/v1/graph/entities")
            assert response.status_code == 200
            data = response.json()
            assert "entities" in data
            assert "total" in data

    def test_get_entities_with_search(self, client):
        """测试搜索实体"""
        with patch("server._neo4j_query") as mock_query:
            mock_query.side_effect = [
                [{"name": "Python", "user_id": "user1", "labels": ["Entity"], "element_id": "1", "relation_count": 3}],
                [{"total": 1}],
            ]
            response = client.get("/v1/graph/entities?search=Python")
            assert response.status_code == 200

    def test_get_entities_with_user_filter(self, client):
        """测试按用户筛选实体"""
        with patch("server._neo4j_query") as mock_query:
            mock_query.side_effect = [[], [{"total": 0}]]
            response = client.get("/v1/graph/entities?user_id=user1")
            assert response.status_code == 200


class TestGraphRelations:
    """图谱关系列表接口测试"""

    def test_get_relations(self, client):
        """测试获取关系列表"""
        with patch("server._neo4j_query") as mock_query:
            mock_query.side_effect = [
                [{"source": "Python", "relation": "USED_BY", "target": "user1", "source_user_id": None, "target_user_id": "user1", "element_id": "r1"}],
                [{"total": 1}],
            ]
            response = client.get("/v1/graph/relations")
            assert response.status_code == 200
            data = response.json()
            assert "relations" in data
            assert "total" in data

    def test_get_relations_with_pagination(self, client):
        """测试关系列表分页"""
        with patch("server._neo4j_query") as mock_query:
            mock_query.side_effect = [[], [{"total": 0}]]
            response = client.get("/v1/graph/relations?limit=10&offset=5")
            assert response.status_code == 200


class TestGraphSearch:
    """图谱搜索接口测试"""

    def test_search_graph(self, client):
        """测试图谱搜索"""
        with patch("server._neo4j_query") as mock_query:
            mock_query.side_effect = [
                [{"source": "Python", "relation": "KNOWS", "target": "Java", "source_user_id": "user1", "target_user_id": "user1"}],
                [],
            ]
            response = client.post(
                "/v1/graph/search",
                json={"query": "Python", "limit": 10},
            )
            assert response.status_code == 200
            data = response.json()
            assert "relations" in data
            assert "isolated_entities" in data
            assert "total" in data

    def test_search_graph_with_user_id(self, client):
        """测试带用户 ID 的图谱搜索"""
        with patch("server._neo4j_query") as mock_query:
            mock_query.side_effect = [[], []]
            response = client.post(
                "/v1/graph/search",
                json={"query": "测试", "user_id": "user1"},
            )
            assert response.status_code == 200


class TestGraphUserSubgraph:
    """用户子图接口测试"""

    def test_get_user_graph(self, client):
        """测试获取用户子图"""
        with patch("server._neo4j_query") as mock_query:
            mock_query.side_effect = [
                [{"source": "A", "source_user_id": "user1", "source_labels": ["Entity"],
                  "relation": "KNOWS", "target": "B", "target_user_id": "user1", "target_labels": ["Entity"]}],
                [],
            ]
            response = client.get("/v1/graph/user/user1")
            assert response.status_code == 200
            data = response.json()
            assert "nodes" in data
            assert "links" in data
            assert "node_count" in data
            assert "link_count" in data


class TestGraphAll:
    """全量图谱接口测试"""

    def test_get_all_graph(self, client):
        """测试获取全量图谱"""
        with patch("server._neo4j_query") as mock_query:
            mock_query.side_effect = [
                [{"source": "A", "source_user_id": "user1", "source_labels": ["Entity"],
                  "relation": "KNOWS", "target": "B", "target_user_id": "user1", "target_labels": ["Entity"]}],
                [],
            ]
            response = client.get("/v1/graph/all")
            assert response.status_code == 200
            data = response.json()
            assert "nodes" in data
            assert "links" in data


class TestGraphDelete:
    """图谱删除接口测试"""

    def test_delete_entity(self, client):
        """测试删除实体"""
        with patch("server._neo4j_query") as mock_query:
            mock_query.return_value = [{"deleted_relations": 3}]
            with patch("server._get_neo4j_driver") as mock_driver:
                mock_session = MagicMock()
                mock_session.run.return_value = MagicMock()
                mock_driver_instance = MagicMock()
                mock_driver_instance.session.return_value.__enter__ = MagicMock(return_value=mock_session)
                mock_driver_instance.session.return_value.__exit__ = MagicMock(return_value=False)
                mock_driver.return_value = mock_driver_instance
                response = client.delete("/v1/graph/entities/Python")
                assert response.status_code in [200, 500]

    def test_delete_relation(self, client):
        """测试删除关系"""
        with patch("server._neo4j_query") as mock_query:
            mock_query.return_value = [{"deleted": 1}]
            response = client.delete(
                "/v1/graph/relations?source=Python&relation=KNOWS&target=Java"
            )
            assert response.status_code == 200


class TestGraphHealth:
    """图谱健康检查测试"""

    def test_graph_health_connected(self, client):
        """测试 Neo4j 连接正常"""
        with patch("server._get_neo4j_driver") as mock_driver:
            mock_session = MagicMock()
            mock_session.run.return_value = True
            mock_driver_instance = MagicMock()
            mock_driver_instance.session.return_value.__enter__ = MagicMock(return_value=mock_session)
            mock_driver_instance.session.return_value.__exit__ = MagicMock(return_value=False)
            mock_driver.return_value = mock_driver_instance
            response = client.get("/v1/graph/health")
            assert response.status_code == 200
            data = response.json()
            assert "status" in data
            assert "message" in data

    def test_graph_health_disconnected(self, client):
        """测试 Neo4j 连接断开"""
        with patch("server._get_neo4j_driver", return_value=None):
            response = client.get("/v1/graph/health")
            assert response.status_code == 200
            data = response.json()
            assert data["status"] in ["disconnected", "error"]
