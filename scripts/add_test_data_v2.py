#!/usr/bin/env python3
"""
批量添加测试数据 V2：3 个用户，每个用户 10 条记忆
使用 infer=False 避免LLM去重，逐条添加并验证
"""
import requests
import json
import time

BASE = "http://127.0.0.1:8080/v1"

test_data = {
    "alice": [
        "我叫Alice，是一名前端工程师，主要用React和TypeScript开发",
        "我住在上海，每天通勤坐地铁2号线到公司",
        "我最喜欢的编程语言是TypeScript，因为它有强大的类型系统",
        "我的猫叫橘子，是一只橘猫，今年3岁了",
        "我最近在学习Rust，觉得所有权概念很有趣但也很挑战",
        "我的生日是3月15日，喜欢草莓蛋糕",
        "我用VS Code作为主要编辑器，装了Vim插件",
        "周末喜欢去咖啡馆写代码，常去的一家叫Blue Bottle",
        "我有一个个人博客，用Next.js搭建的，部署在Vercel上",
        "我对花粉过敏，春天的时候需要吃药",
    ],
    "bob": [
        "我是Bob，一名后端工程师，主要用Go和Python写服务",
        "我住在深圳，公司在南山科技园",
        "我最常用的数据库是PostgreSQL，觉得它的JSON支持很好",
        "我有一只金毛犬叫旺财，每天早上6点起来遛狗",
        "我正在学习Kubernetes，准备考CKA认证",
        "我的生日是7月22日，喜欢吃火锅",
        "我用Neovim配合tmux开发，自己写了一套Lua配置",
        "业余时间在做一个开源项目，是一个分布式任务调度器",
        "我喜欢跑步，每周跑3次，每次5公里左右",
        "我对牛奶不耐受，喝咖啡只能喝燕麦拿铁",
    ],
    "carol": [
        "我是Carol，一名产品经理，负责一个AI对话产品的设计",
        "我住在北京，公司在望京SOHO",
        "我最常用的工具是Figma和Notion，每天都在用",
        "我有一只布偶猫叫雪球，非常粘人",
        "我正在学习SQL和数据分析，想更好地理解用户行为",
        "我的生日是11月8日，喜欢吃日料",
        "我用MacBook Pro 16寸作为工作电脑",
        "我喜欢看推理小说，最喜欢的作者是东野圭吾",
        "我每周日下午会做瑜伽，已经坚持两年了",
        "我对尘螨过敏，家里配了两台空气净化器",
    ],
}

total_added = 0
total_failed = 0

for user_id, memories in test_data.items():
    print(f"\n{'='*60}")
    print(f"用户 [{user_id}]：{len(memories)} 条记忆")
    print(f"{'='*60}")
    for i, content in enumerate(memories):
        payload = {
            "messages": [{"role": "user", "content": content}],
            "user_id": user_id,
            "infer": False,
            "auto_categorize": False,
        }
        t0 = time.time()
        resp = requests.post(f"{BASE}/memories/", json=payload, timeout=60)
        elapsed = time.time() - t0

        if resp.status_code == 200:
            data = resp.json()
            results = data.get("results", [])
            if results:
                mid = results[0].get("id", "")
                event = results[0].get("event", "")
                mem_text = results[0].get("memory", "")[:50]
                print(f"  [{i+1:2d}] {elapsed:5.1f}s  id={mid[:12]}  event={event}  memory={mem_text}")
                total_added += 1
            else:
                print(f"  [{i+1:2d}] {elapsed:5.1f}s  无结果返回")
                total_failed += 1
        else:
            print(f"  [{i+1:2d}] {elapsed:5.1f}s  HTTP {resp.status_code}: {resp.text[:100]}")
            total_failed += 1

print(f"\n{'='*60}")
print(f"完成：成功 {total_added} 条，失败 {total_failed} 条")
print(f"{'='*60}")

# 验证
print("\n正在验证用户列表...")
time.sleep(1)
resp = requests.get(f"{BASE}/users/")
if resp.status_code == 200:
    data = resp.json()
    print(f"用户总数: {data['total']}")
    for u in data["users"]:
        if u["user_id"] in ("alice", "bob", "carol"):
            print(f"  {u['user_id']}: {u['memory_count']} 条记忆 (active={u['active_count']})")

print("\n正在验证各用户记忆...")
for uid in ("alice", "bob", "carol"):
    resp = requests.get(f"{BASE}/memories/?user_id={uid}")
    if resp.status_code == 200:
        data = resp.json()
        print(f"\n{uid} 的记忆 ({len(data)} 条):")
        for m in data:
            print(f"  id={m.get('id','')[:12]}  memory={m.get('memory','')[:50]}")
