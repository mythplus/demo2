"""
最终重试 - 进一步简化内容
"""
import requests
import time

API_BASE = "http://localhost:8080"

retry_memories = [
    # 苹果公司 - 拆分为更短的句子
    "苹果公司总部位于美国硅谷。苹果公司的代表产品是iPhone。苹果公司是全球市值最高的科技公司之一。",
    # 清华大学和奥运会 - 拆分
    "清华大学位于北京海淀区，创建于1911年，是中国顶尖高等学府。2008年北京奥运会在鸟巢体育场举行，是中国首次举办夏季奥运会。",
]

user_id = "knowledge_graph_demo"

print(f"最终重试 {len(retry_memories)} 条...")
print("=" * 60)

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
        else:
            print(f"  ❌ 失败! HTTP {resp.status_code}")
            print(f"     {resp.text[:300]}")
    except Exception as e:
        print(f"  ❌ 异常: {e}")
    
    time.sleep(2)

print("\n" + "=" * 60)
print("完成!")
