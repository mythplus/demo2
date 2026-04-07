"""
图谱服务 — Neo4j 图数据库操作（驱动管理、Cypher 查询封装）
"""

import logging
from server.config import MEM0_CONFIG

logger = logging.getLogger(__name__)

# 全局单例 Neo4j 驱动（延迟初始化，应用关闭时统一清理）
_neo4j_driver_instance = None


def get_neo4j_driver():
    """获取 Neo4j 驱动全局单例（延迟初始化，复用连接池）"""
    global _neo4j_driver_instance
    if _neo4j_driver_instance is not None:
        return _neo4j_driver_instance
    graph_config = MEM0_CONFIG.get("graph_store", {}).get("config", {})
    if not graph_config:
        return None
    try:
        from neo4j import GraphDatabase
        _neo4j_driver_instance = GraphDatabase.driver(
            graph_config["url"],
            auth=(graph_config["username"], graph_config["password"]),
        )
        logger.info("Neo4j 驱动全局单例已初始化")
        return _neo4j_driver_instance
    except Exception as e:
        logger.warning(f"Neo4j 连接失败: {e}")
        return None


def close_neo4j_driver():
    """关闭全局 Neo4j 驱动（应用关闭时调用）"""
    global _neo4j_driver_instance
    if _neo4j_driver_instance is not None:
        try:
            _neo4j_driver_instance.close()
            logger.info("Neo4j 驱动已关闭")
        except Exception as e:
            logger.warning(f"关闭 Neo4j 驱动失败: {e}")
        finally:
            _neo4j_driver_instance = None


def neo4j_query(cypher: str, params: dict = None) -> list:
    """执行 Neo4j Cypher 查询并返回结果列表（复用全局驱动）"""
    driver = get_neo4j_driver()
    if not driver:
        return []
    try:
        with driver.session() as session:
            result = session.run(cypher, params or {})
            return [record.data() for record in result]
    except Exception as e:
        logger.warning(f"Neo4j 查询失败: {e}")
        return []
