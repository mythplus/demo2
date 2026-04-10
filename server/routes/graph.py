"""
Graph Memory 路由 — Neo4j 图谱全部端点
"""

import logging
from typing import Optional, Dict, Any

from fastapi import APIRouter, HTTPException, Query

from server.config import _safe_error_detail
from server.models.schemas import GraphSearchRequest
from server.services.graph_service import get_neo4j_driver, neo4j_query

logger = logging.getLogger(__name__)

router = APIRouter(tags=["图谱记忆"])


@router.get("/v1/graph/stats")
async def get_graph_stats():
    """获取图谱统计信息（实体数、关系数、类型分布）"""
    try:
        # 实体总数
        entity_count_result = neo4j_query("MATCH (n) RETURN count(n) as count")
        entity_count = entity_count_result[0]["count"] if entity_count_result else 0

        # 关系总数
        relation_count_result = neo4j_query("MATCH ()-[r]->() RETURN count(r) as count")
        relation_count = relation_count_result[0]["count"] if relation_count_result else 0

        # 关系类型分布
        relation_types_result = neo4j_query(
            "MATCH ()-[r]->() RETURN type(r) as relation_type, count(r) as count ORDER BY count DESC"
        )
        relation_type_distribution = {
            item["relation_type"]: item["count"] for item in relation_types_result
        }

        # 按用户统计实体数
        user_entity_result = neo4j_query(
            "MATCH (n) WHERE n.user_id IS NOT NULL RETURN n.user_id as user_id, count(n) as count ORDER BY count DESC LIMIT 20"
        )
        user_entity_distribution = {
            item["user_id"]: item["count"] for item in user_entity_result
        }

        return {
            "entity_count": entity_count,
            "relation_count": relation_count,
            "relation_type_distribution": relation_type_distribution,
            "user_entity_distribution": user_entity_distribution,
        }
    except Exception as e:
        logger.error(f"获取图谱统计失败: {e}")
        raise HTTPException(status_code=500, detail=_safe_error_detail(e))


@router.get("/v1/graph/entities")
async def get_graph_entities(
    user_id: Optional[str] = Query(None, description="按用户ID筛选"),
    search: Optional[str] = Query(None, description="搜索实体名称"),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    """获取实体列表"""
    try:
        where_clauses = []
        params: Dict[str, Any] = {"limit": limit, "offset": offset}

        if user_id:
            where_clauses.append("n.user_id = $user_id")
            params["user_id"] = user_id
        if search:
            where_clauses.append("toLower(n.name) CONTAINS toLower($search)")
            params["search"] = search

        where_str = " WHERE " + " AND ".join(where_clauses) if where_clauses else ""

        # 查询实体及其关系数
        cypher = f"""
            MATCH (n){where_str}
            OPTIONAL MATCH (n)-[r]-()
            RETURN n.name as name, n.user_id as user_id, labels(n) as labels,
                   elementId(n) as element_id, count(r) as relation_count
            ORDER BY relation_count DESC
            SKIP $offset LIMIT $limit
        """
        entities = neo4j_query(cypher, params)

        # 总数
        count_cypher = f"MATCH (n){where_str} RETURN count(n) as total"
        count_params = {k: v for k, v in params.items() if k not in ("limit", "offset")}
        total_result = neo4j_query(count_cypher, count_params)
        total = total_result[0]["total"] if total_result else 0

        return {
            "entities": entities,
            "total": total,
            "limit": limit,
            "offset": offset,
        }
    except Exception as e:
        logger.error(f"获取实体列表失败: {e}")
        raise HTTPException(status_code=500, detail=_safe_error_detail(e))


@router.get("/v1/graph/relations")
async def get_graph_relations(
    user_id: Optional[str] = Query(None, description="按用户ID筛选"),
    search: Optional[str] = Query(None, description="搜索关系中的实体名称"),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    """获取关系三元组列表"""
    try:
        where_clauses = []
        params: Dict[str, Any] = {"limit": limit, "offset": offset}

        if user_id:
            where_clauses.append("(a.user_id = $user_id OR b.user_id = $user_id)")
            params["user_id"] = user_id
        if search:
            where_clauses.append(
                "(toLower(a.name) CONTAINS toLower($search) OR toLower(b.name) CONTAINS toLower($search))"
            )
            params["search"] = search

        where_str = " WHERE " + " AND ".join(where_clauses) if where_clauses else ""

        cypher = f"""
            MATCH (a)-[r]->(b){where_str}
            RETURN a.name as source, type(r) as relation, b.name as target,
                   a.user_id as source_user_id, b.user_id as target_user_id,
                   elementId(r) as element_id
            ORDER BY source
            SKIP $offset LIMIT $limit
        """
        relations = neo4j_query(cypher, params)

        # 总数
        count_cypher = f"MATCH (a)-[r]->(b){where_str} RETURN count(r) as total"
        count_params = {k: v for k, v in params.items() if k not in ("limit", "offset")}
        total_result = neo4j_query(count_cypher, count_params)
        total = total_result[0]["total"] if total_result else 0

        return {
            "relations": relations,
            "total": total,
            "limit": limit,
            "offset": offset,
        }
    except Exception as e:
        logger.error(f"获取关系列表失败: {e}")
        raise HTTPException(status_code=500, detail=_safe_error_detail(e))


@router.post("/v1/graph/search")
async def search_graph(request: GraphSearchRequest):
    """基于图谱的搜索（搜索实体名称和关系）"""
    try:
        params: Dict[str, Any] = {"query": request.query.lower(), "limit": request.limit or 20}
        user_filter = ""
        if request.user_id:
            user_filter = "AND (a.user_id = $user_id OR b.user_id = $user_id)"
            params["user_id"] = request.user_id

        # 搜索包含关键词的实体及其关系
        cypher = f"""
            MATCH (a)-[r]->(b)
            WHERE (toLower(a.name) CONTAINS $query OR toLower(b.name) CONTAINS $query)
            {user_filter}
            RETURN a.name as source, type(r) as relation, b.name as target,
                   a.user_id as source_user_id, b.user_id as target_user_id
            LIMIT $limit
        """
        results = neo4j_query(cypher, params)

        # 同时搜索孤立实体（没有关系的实体）
        entity_cypher = f"""
            MATCH (n)
            WHERE toLower(n.name) CONTAINS $query
            {"AND n.user_id = $user_id" if request.user_id else ""}
            AND NOT (n)-[]-()
            RETURN n.name as name, n.user_id as user_id, labels(n) as labels
            LIMIT $limit
        """
        isolated_entities = neo4j_query(entity_cypher, params)

        return {
            "relations": results,
            "isolated_entities": isolated_entities,
            "total": len(results) + len(isolated_entities),
        }
    except Exception as e:
        logger.error(f"图谱搜索失败: {e}")
        raise HTTPException(status_code=500, detail=_safe_error_detail(e))


@router.get("/v1/graph/user/{user_id}")
async def get_user_graph(
    user_id: str,
    limit: int = Query(200, ge=1, le=1000),
):
    """获取指定用户的子图数据（用于可视化）"""
    try:
        # 获取用户的所有实体和关系
        cypher = """
            MATCH (a)-[r]->(b)
            WHERE a.user_id = $user_id OR b.user_id = $user_id
            RETURN a.name as source, a.user_id as source_user_id, labels(a) as source_labels,
                   type(r) as relation,
                   b.name as target, b.user_id as target_user_id, labels(b) as target_labels
            LIMIT $limit
        """
        relations = neo4j_query(cypher, {"user_id": user_id, "limit": limit})

        # 构建节点和边的数据结构（用于前端力导向图）
        nodes_map: Dict[str, dict] = {}
        links = []

        for rel in relations:
            source_name = rel["source"]
            target_name = rel["target"]

            if source_name not in nodes_map:
                nodes_map[source_name] = {
                    "id": source_name,
                    "name": source_name,
                    "user_id": rel.get("source_user_id"),
                    "labels": rel.get("source_labels", []),
                    "val": 1,
                }
            else:
                nodes_map[source_name]["val"] += 1

            if target_name not in nodes_map:
                nodes_map[target_name] = {
                    "id": target_name,
                    "name": target_name,
                    "user_id": rel.get("target_user_id"),
                    "labels": rel.get("target_labels", []),
                    "val": 1,
                }
            else:
                nodes_map[target_name]["val"] += 1

            links.append({
                "source": source_name,
                "target": target_name,
                "relation": rel["relation"],
            })

        # 也获取孤立实体（有 user_id 但没有关系的实体）
        isolated_cypher = """
            MATCH (n)
            WHERE n.user_id = $user_id AND NOT (n)-[]-()
            RETURN n.name as name, n.user_id as user_id, labels(n) as labels
            LIMIT $limit
        """
        isolated = neo4j_query(isolated_cypher, {"user_id": user_id, "limit": limit})
        for node in isolated:
            name = node["name"]
            if name not in nodes_map:
                nodes_map[name] = {
                    "id": name,
                    "name": name,
                    "user_id": node.get("user_id"),
                    "labels": node.get("labels", []),
                    "val": 1,
                }

        return {
            "nodes": list(nodes_map.values()),
            "links": links,
            "node_count": len(nodes_map),
            "link_count": len(links),
        }
    except Exception as e:
        logger.error(f"获取用户图谱失败: {e}")
        raise HTTPException(status_code=500, detail=_safe_error_detail(e))


@router.get("/v1/graph/all")
async def get_all_graph(
    limit: int = Query(300, ge=1, le=2000),
):
    """获取全部图谱数据（用于可视化）"""
    try:
        cypher = """
            MATCH (a)-[r]->(b)
            RETURN a.name as source, a.user_id as source_user_id, labels(a) as source_labels,
                   type(r) as relation,
                   b.name as target, b.user_id as target_user_id, labels(b) as target_labels
            LIMIT $limit
        """
        relations = neo4j_query(cypher, {"limit": limit})

        nodes_map: Dict[str, dict] = {}
        links = []

        for rel in relations:
            source_name = rel["source"]
            target_name = rel["target"]

            if source_name not in nodes_map:
                nodes_map[source_name] = {
                    "id": source_name,
                    "name": source_name,
                    "user_id": rel.get("source_user_id"),
                    "labels": rel.get("source_labels", []),
                    "val": 1,
                }
            else:
                nodes_map[source_name]["val"] += 1

            if target_name not in nodes_map:
                nodes_map[target_name] = {
                    "id": target_name,
                    "name": target_name,
                    "user_id": rel.get("target_user_id"),
                    "labels": rel.get("target_labels", []),
                    "val": 1,
                }
            else:
                nodes_map[target_name]["val"] += 1

            links.append({
                "source": source_name,
                "target": target_name,
                "relation": rel["relation"],
            })

        return {
            "nodes": list(nodes_map.values()),
            "links": links,
            "node_count": len(nodes_map),
            "link_count": len(links),
        }
    except Exception as e:
        logger.error(f"获取全部图谱失败: {e}")
        raise HTTPException(status_code=500, detail=_safe_error_detail(e))


@router.delete("/v1/graph/entities/{entity_name}")
async def delete_graph_entity(entity_name: str, user_id: Optional[str] = Query(None)):
    """删除指定实体及其所有关联关系"""
    try:
        params: Dict[str, Any] = {"name": entity_name}
        user_filter = ""
        if user_id:
            user_filter = "AND n.user_id = $user_id"
            params["user_id"] = user_id

        cypher = f"MATCH (n) WHERE n.name = $name {user_filter} DETACH DELETE n RETURN count(n) as deleted"
        result = neo4j_query(cypher, params)
        deleted = result[0]["deleted"] if result else 0

        if deleted == 0:
            raise HTTPException(status_code=404, detail="实体不存在")

        return {"message": f"已删除实体 '{entity_name}' 及其关联关系", "deleted": deleted}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"删除实体失败: {e}")
        raise HTTPException(status_code=500, detail=_safe_error_detail(e))


@router.delete("/v1/graph/relations")
async def delete_graph_relation(
    source: str = Query(..., description="源实体名称"),
    relation: str = Query(..., description="关系类型"),
    target: str = Query(..., description="目标实体名称"),
):
    """删除指定关系"""
    try:
        cypher = """
            MATCH (a {name: $source})-[r]->(b {name: $target})
            WHERE type(r) = $relation
            DELETE r
            RETURN count(r) as deleted
        """
        result = neo4j_query(cypher, {"source": source, "relation": relation, "target": target})
        deleted = result[0]["deleted"] if result else 0

        if deleted == 0:
            raise HTTPException(status_code=404, detail="关系不存在")

        return {"message": f"已删除关系: {source} --[{relation}]--> {target}", "deleted": deleted}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"删除关系失败: {e}")
        raise HTTPException(status_code=500, detail=_safe_error_detail(e))


@router.get("/v1/graph/health")
async def graph_health_check():
    """检查 Neo4j 图数据库连接状态"""
    try:
        driver = get_neo4j_driver()
        if not driver:
            return {"status": "disconnected", "message": "未配置 graph_store"}
        try:
            with driver.session() as session:
                result = session.run("RETURN 1 as ok")
                result.single()
            return {"status": "connected", "message": "Neo4j 连接正常"}
        except Exception as e:
            return {"status": "error", "message": str(e)}
    except Exception as e:
        return {"status": "error", "message": str(e)}
