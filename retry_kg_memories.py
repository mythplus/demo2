"""
重试添加失败的知识图谱记忆数据（简化内容避免特殊字符问题）
"""
import requests
import time

API_BASE = "http://localhost:8080"

# 简化内容，避免括号等特殊字符导致 Neo4j 语法错误
retry_memories = [
    # 苹果公司相关（去掉括号）
    "苹果公司总部位于美国硅谷库比蒂诺，其代表产品包括iPhone、iPad和Mac系列电脑。苹果公司是全球市值最高的科技公司之一。",
    # 爱因斯坦相关（简化括号内容）
    "阿尔伯特爱因斯坦是著名的物理学家，他提出了狭义相对论和广义相对论，彻底改变了人类对时间、空间和引力的理解。爱因斯坦于1921年获得诺贝尔物理学奖。",
    # 人工智能概念（简化）
    "人工智能是计算机科学的一个分支，致力于创建能够模拟人类智能的系统。图数据库是一种专门用于存储和查询图结构数据的数据库技术，常用于知识图谱的构建。区块链是一种去中心化的分布式账本技术。",
    # 清华大学等（简化）
    "清华大学位于北京市海淀区，是中国顶尖的高等学府之一，创建于1911年。2008年北京奥运会是中国首次举办的夏季奥运会，在北京鸟巢体育场举行。",
]

user_id = "knowledge_graph_demo"

print(f"重试添加 {len(retry_memories)} 条记忆数据...")
print("=" * 60)

success_count = 0
fail_count = 0

for i, content in enumerate(retry_memories, 1):
    print(f"\n[{i}/{len(retry_memories)}] 正在添加...")
    print(f"  内容: {content[:60]}...")
    
    try:
        resp = requests.post(
            f"{API_BASE}/v1/memories/",
            json={
                "messages": [{"role": "user", "content": content}],
                "user_id": user_id,
                "infer": False,
                "auto_categorize": True,
            },
            timeout=60,
        )
        
        if resp.status_code == 200:
            result = resp.json()
            added = [r for r in result.get("results", []) if r.get("event") == "ADD"]
            print(f"  ✅ 成功! 添加了 {len(added)} 条记忆")
            for r in added:
                print(f"     - ID: {r.get('id', 'N/A')}")
            success_count += 1
        else:
            print(f"  ❌ 失败! HTTP {resp.status_code}")
            print(f"     {resp.text[:300]}")
            fail_count += 1
    except Exception as e:
        print(f"  ❌ 异常: {e}")
        fail_count += 1
    
    time.sleep(2)

print("\n" + "=" * 60)
print(f"重试完成! 成功: {success_count}, 失败: {fail_count}")
