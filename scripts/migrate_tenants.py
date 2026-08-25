"""
数据迁移脚本：为存量数据打上 tenant_id=default 标签

操作内容：
1. Qdrant 存量记忆批量打 tenant_id=default
2. Neo4j 存量节点批量 SET n.tenant_id = 'default'
3. SQLite 日志表回填 tenant_id='default'
4. Qdrant 创建 tenant_id payload index
5. Neo4j 创建 tenant_id 索引
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.config import MEM0_CONFIG
from app.memory_engine import get_memory


def migrate_qdrant():
    """Qdrant 存量记忆批量打 tenant_id"""
    print("=== Qdrant 迁移开始 ===")
    m = get_memory()
    collection_name = MEM0_CONFIG["vector_store"]["config"]["collection_name"]
    qdrant_client = m.vector_store.client

    # 创建 payload index
    try:
        from qdrant_client.models import PayloadSchemaType
        qdrant_client.create_payload_index(
            collection_name=collection_name,
            field_name="tenant_id",
            field_schema=PayloadSchemaType.KEYWORD,
        )
        print(f"已创建 tenant_id payload index")
    except Exception as e:
        print(f"创建 index（可能已存在）: {e}")

    # 批量打标
    total_updated = 0
    offset = None
    batch_size = 256

    while True:
        records, next_offset = qdrant_client.scroll(
            collection_name=collection_name,
            limit=batch_size,
            offset=offset,
            with_payload=True,
            with_vectors=False,
        )
        if not records:
            break

        # 找出没有 tenant_id 的记录
        to_update = []
        for r in records:
            payload = r.payload or {}
            if not payload.get("tenant_id"):
                to_update.append(r.id)

        if to_update:
            qdrant_client.set_payload(
                collection_name=collection_name,
                payload={"tenant_id": "default"},
                points=to_update,
            )
            total_updated += len(to_update)
            print(f"  批次更新 {len(to_update)} 条 (累计 {total_updated})")

        if next_offset is None:
            break
        offset = next_offset

    print(f"Qdrant 迁移完成: 共更新 {total_updated} 条记忆\n")


def migrate_neo4j():
    """Neo4j 存量节点批量打 tenant_id"""
    print("=== Neo4j 迁移开始 ===")
    graph_config = MEM0_CONFIG.get("graph_store", {}).get("config", {})
    if not graph_config:
        print("未配置 graph_store，跳过")
        return

    try:
        from neo4j import GraphDatabase
        driver = GraphDatabase.driver(
            graph_config["url"],
            auth=(graph_config["username"], graph_config["password"]),
        )

        with driver.session() as session:
            # 创建索引
            try:
                session.run("CREATE INDEX tenant_id_index IF NOT EXISTS FOR (n) ON (n.tenant_id)")
                print("已创建 tenant_id 索引")
            except Exception as e:
                print(f"创建索引（可能已存在）: {e}")

            # 批量打标
            result = session.run(
                "MATCH (n) WHERE n.tenant_id IS NULL SET n.tenant_id = 'default' RETURN count(n) as updated"
            )
            record = result.single()
            updated = record["updated"] if record else 0
            print(f"Neo4j 迁移完成: 共更新 {updated} 个节点\n")

        driver.close()
    except Exception as e:
        print(f"Neo4j 迁移失败: {e}\n")


def migrate_sqlite_logs():
    """SQLite 日志表回填 tenant_id"""
    print("=== SQLite 日志迁移开始 ===")
    from app.database import _get_db_conn
    conn = _get_db_conn()

    tables_columns = {
        "access_logs": ["tenant_id"],
        "request_logs": ["tenant_id"],
        "memory_change_logs": ["tenant_id"],
    }

    for table, cols in tables_columns.items():
        for col in cols:
            try:
                # 检查列是否存在
                cursor = conn.execute(f"PRAGMA table_info({table})")
                columns = [row[1] for row in cursor.fetchall()]
                if col not in columns:
                    conn.execute(f"ALTER TABLE {table} ADD COLUMN {col} TEXT DEFAULT 'default'")
                    print(f"  {table}: 已添加 {col} 列")

                # 回填
                conn.execute(f"UPDATE {table} SET {col} = 'default' WHERE {col} IS NULL")
                conn.commit()
                print(f"  {table}: 已回填 {col}='default'")
            except Exception as e:
                print(f"  {table}: {e}")

    print("SQLite 日志迁移完成\n")


if __name__ == "__main__":
    print("=" * 50)
    print("多租户数据迁移脚本")
    print("=" * 50 + "\n")

    migrate_qdrant()
    migrate_neo4j()
    migrate_sqlite_logs()

    print("=" * 50)
    print("迁移全部完成！")
    print("=" * 50)
