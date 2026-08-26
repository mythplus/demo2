#!/usr/bin/env python3
"""
批量添加测试数据：3 个用户，每个用户 10 条记忆
"""
import requests
import json
import time

BASE = "http://127.0.0.1:8080/v1"

test_data = {
    "alice": [
        "我叫 Alice，是一名前端工程师，主要用 React 和 TypeScript 开发。",
        "我住在上海，每天通勤坐地铁 2 号线到公司。",
        "我最喜欢的编程语言是 TypeScript，因为它有强大的类型系统。",
        "我的猫叫橘子，是一只橘猫，今年 3 岁了。",
        "我最近在学习 Rust，觉得所有权概念很有趣但也很挑战。",
        "我的生日是 3 月 15 日，喜欢草莓蛋糕。",
        "我用 VS Code 作为主要编辑器，装了 Vim 插件。",
        "周末喜欢去咖啡馆写代码，常去的一家叫 Blue Bottle。",
        "我有一个个人博客，用 Next.js 搭建的，部署在 Vercel 上。",
        "我对花粉过敏，春天的时候需要吃药。",
    ],
    "bob": [
        "我是 Bob，一名后端工程师，主要用 Go 和 Python 写服务。",
        "我住在深圳，公司在南山科技园。",
        "我最常用的数据库是 PostgreSQL，觉得它的 JSON 支持很好。",
        "我有一只金毛犬叫旺财，每天早上 6 点起来遛狗。",
        "我正在学习 Kubernetes，准备考 CKA 认证。",
        "我的生日是 7 月 22 日，喜欢吃火锅。",
        "我用 Neovim 配合 tmux 开发，自己写了一套 Lua 配置。",
        "业余时间在做一个开源项目，是一个分布式任务调度器。",
        "我喜欢跑步，每周跑 3 次，每次 5 公里左右。",
        "我对牛奶不耐受，喝咖啡只能喝燕麦拿铁。",
    ],
    "carol": [
        "我是 Carol，一名产品经理，负责一个 AI 对话产品的设计。",
        "我住在北京，公司在望京 SOHO。",
        "我最常用的工具是 Figma 和 Notion，每天都在用。",
        "我有一只布偶猫叫雪球，非常粘人。",
        "我正在学习 SQL 和数据分析，想更好地理解用户行为。",
        "我的生日是 11 月 8 日，喜欢吃日料。",
        "我用 Mac Book Pro 16 寸作为工作电脑。",
        "我喜欢看推理小说，最喜欢的作者是东野圭吾。",
        "我每周日下午会做瑜伽，已经坚持两年了。",
        "我对尘螨过敏，家里配了两台空气净化器。",
    ],
}

for user_id, memories in test_data.items():
    items = [{"content": m, "user_id": user_id, "state": "active"} for m in memories]
    payload = {
        "items": items,
        "default_user_id": user_id,
        "infer": True,
        "auto_categorize": True,
    }
    print(f"\n{'='*50}")
    print(f"正在为用户 [{user_id}] 添加 {len(items)} 条记忆...")
    t0 = time.time()
    resp = requests.post(f"{BASE}/memories/batch", json=payload, timeout=120)
    elapsed = time.time() - t0
    print(f"  耗时: {elapsed:.1f}s  状态码: {resp.status_code}")
    if resp.status_code == 200:
        data = resp.json()
        print(f"  总计: {data['total']}  成功: {data['success']}  失败: {data['failed']}")
        for r in data["results"]:
            if r.get("success"):
                print(f"    [{r.get('index')}] id={r.get('id')}  memory={r.get('memory')}")
            else:
                print(f"    [{r.get('index')}] 失败: {r.get('error')}")
    else:
        print(f"  错误: {resp.text[:300]}")

print(f"\n{'='*50}")
print("全部完成！正在验证用户列表...")
resp = requests.get(f"{BASE}/users/")
if resp.status_code == 200:
    data = resp.json()
    print(f"\n用户总数: {data['total']}")
    for u in data["users"]:
        print(f"  {u['user_id']}: {u['memory_count']} 条记忆 (active={u['active_count']})")
