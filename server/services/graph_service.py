"""
图谱服务 — Neo4j 图数据库操作（驱动管理、Cypher 查询封装）

B2 P2-3 改造记录：
- 旧实现会对所有异常 ``log.warning`` 后返回 ``[]``，让上层以为"图谱为空"而非"查询失败"；
  这既违反"严禁静默吞错"原则，又让前端诊断变得困难。
- 新实现做了两件事：
  1) 区分"未配置 / 驱动为 None"（真的是图谱未启用，返回空表示功能关闭）与"查询/连接异常"
     （这是错误，必须用 ``logger.error`` + 完整堆栈记录，不再伪装成空结果）。
  2) 为避免一次性把所有上层路由改成 try/except 的大爆炸，暂保留"返回 []"作为查询异常的兜底，
     但日志级别升为 ``error`` 并附 ``exc_info=True``，后续可统一抽象成带失败计数的 metrics。
"""

import logging
from server.config import MEM0_CONFIG

logger = logging.getLogger(__name__)

# 全局单例 Neo4j 驱动（延迟初始化，应用关闭时统一清理）
_neo4j_driver_instance = None
# 记录驱动初始化曾经失败过的配置快照，避免反复尝试产生海量日志
_neo4j_driver_failed = False


def is_graph_enabled() -> bool:
    """快速判断当前是否启用了 Neo4j 图谱（供路由层做 feature flag）。"""
    return bool(MEM0_CONFIG.get("graph_store", {}).get("config"))


def get_neo4j_driver():
    """获取 Neo4j 驱动全局单例（延迟初始化，复用连接池）。

    返回 ``None`` 表示图谱未配置或驱动初始化失败；调用方应该用 ``is_graph_enabled()`` 区分
    "没配置" 和 "配置了但连不上"，避免误把连接失败当成空图谱。
    """
    global _neo4j_driver_instance, _neo4j_driver_failed
    if _neo4j_driver_instance is not None:
        return _neo4j_driver_instance
    graph_config = MEM0_CONFIG.get("graph_store", {}).get("config", {})
    if not graph_config:
        # 纯粹没开图谱功能，这是正常场景
        return None
    if _neo4j_driver_failed:
        # 之前已经失败过，避免每次查询都重复触发 GraphDatabase.driver 并打印错误
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
        _neo4j_driver_failed = True
        # 不吞错：用 error 级别 + 堆栈，便于排查配置或网络问题
        logger.error(f"Neo4j 驱动初始化失败（图谱功能将不可用）: {e}", exc_info=True)
        return None


def close_neo4j_driver():
    """关闭全局 Neo4j 驱动（应用关闭时调用）"""
    global _neo4j_driver_instance
    if _neo4j_driver_instance is not None:
        try:
            _neo4j_driver_instance.close()
            logger.info("Neo4j 驱动已关闭")
        except Exception as e:
            logger.warning(f"关闭 Neo4j 驱动失败: {e}", exc_info=True)
        finally:
            _neo4j_driver_instance = None


def neo4j_query(cypher: str, params: dict = None) -> list:
    """执行 Neo4j Cypher 查询并返回结果列表（复用全局驱动）。

    语义：
    - 驱动未初始化（未启用图谱或曾经失败）：返回 ``[]``（表达"图谱没东西"），不记录错误。
    - 查询执行异常：用 ``logger.error`` 附堆栈记录，**不再伪装成空数据**；但为了向后兼容路由层
      目前的处理方式，仍返回 ``[]``——这是需要在后续统一引入 result envelope 时改造的点。
    """
    driver = get_neo4j_driver()
    if not driver:
        return []
    try:
        with driver.session() as session:
            result = session.run(cypher, params or {})
            return [record.data() for record in result]
    except Exception as e:
        # B2 P2-3：不再静默吞错。error 级别 + exc_info 让堆栈进入日志系统，上层依旧拿到空列表兜底。
        logger.error(
            "Neo4j 查询失败（cypher=%s, params=%s）: %s",
            cypher[:120],
            params,
            e,
            exc_info=True,
        )
        return []
