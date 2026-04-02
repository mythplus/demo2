"""
批量添加知识图谱示例记忆数据
基于用户提供的实体、关系、属性示例
"""
import requests
import time

API_BASE = "http://localhost:8080"

# 定义要添加的记忆数据
memories = [
    # 1. 马化腾相关
    "马化腾是腾讯的创始人，他的国籍是中国。马化腾于1998年创立了腾讯公司，是中国互联网行业的领军人物之一。",
    # 2. 腾讯相关
    "腾讯公司总部位于深圳，成立时间为1998年。腾讯是中国最大的互联网公司之一，业务涵盖社交、游戏、金融科技等领域。",
    # 3. 微信相关
    "微信是腾讯旗下的即时通讯产品，月活跃用户数达13亿。微信由张小龙团队开发，于2011年正式上线。",
    # 4. 乔布斯相关
    "史蒂夫·乔布斯是苹果公司的联合创始人，他是美国著名的企业家和发明家。乔布斯以其对产品设计的极致追求而闻名于世。",
    # 5. 苹果公司相关
    "苹果公司总部位于美国硅谷（加利福尼亚州库比蒂诺），其代表产品包括iPhone、iPad和Mac系列电脑。苹果公司是全球市值最高的科技公司之一。",
    # 6. 爱因斯坦相关
    "阿尔伯特·爱因斯坦是著名的物理学家，他提出了相对论（包括狭义相对论和广义相对论），彻底改变了人类对时间、空间和引力的理解。爱因斯坦于1921年获得诺贝尔物理学奖。",
    # 7. 人工智能、区块链等概念
    "人工智能（AI）是计算机科学的一个分支，致力于创建能够模拟人类智能的系统。图数据库是一种专门用于存储和查询图结构数据的数据库技术，常用于知识图谱的构建。区块链是一种去中心化的分布式账本技术，具有不可篡改和透明的特性。",
    # 8. 清华大学、2008年奥运会、COVID-19
    "清华大学位于北京市海淀区，是中国顶尖的高等学府之一，创建于1911年。2008年北京奥运会是中国首次举办的夏季奥林匹克运动会，在北京鸟巢体育场举行。COVID-19疫情于2019年底爆发，对全球公共卫生和经济产生了深远影响。",
]

user_id = "knowledge_graph_demo"

print(f"开始批量添加 {len(memories)} 条记忆数据...")
print(f"用户ID: {user_id}")
print("=" * 60)

success_count = 0
fail_count = 0

for i, content in enumerate(memories, 1):
    print(f"\n[{i}/{len(memories)}] 正在添加...")
    print(f"  内容: {content[:50]}...")
    
    try:
        resp = requests.post(
            f"{API_BASE}/v1/memories/",
            json={
                "messages": [{"role": "user", "content": content}],
                "user_id": user_id,
                "infer": False,
                "auto_categorize": True,
            },
            timeout=30,
        )
        
        if resp.status_code == 200:
            result = resp.json()
            added = [r for r in result.get("results", []) if r.get("event") == "ADD"]
            print(f"  ✅ 成功! 添加了 {len(added)} 条记忆")
            for r in added:
                print(f"     - ID: {r.get('id', 'N/A')}")
                print(f"       内容: {r.get('memory', '')[:60]}...")
            success_count += 1
        else:
            print(f"  ❌ 失败! HTTP {resp.status_code}: {resp.text[:200]}")
            fail_count += 1
    except Exception as e:
        print(f"  ❌ 异常: {e}")
        fail_count += 1
    
    # 稍微等待一下，避免请求过快
    time.sleep(1)

print("\n" + "=" * 60)
print(f"批量添加完成! 成功: {success_count}, 失败: {fail_count}")
