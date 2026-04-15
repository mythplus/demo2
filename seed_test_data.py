"""
测试数据填充脚本 — 通过后端 API 添加 3 个用户各 10 条记忆
"""
import requests
import time

API_BASE = "http://localhost:8080"

# 3 个测试用户及其记忆内容
TEST_DATA = {
    "alice": [
        "我喜欢在早晨跑步，每天坚持5公里",
        "我的编程语言偏好是 Python 和 TypeScript",
        "我正在学习机器学习，目前在看吴恩达的课程",
        "我家有一只叫小橘的橘猫，今年3岁了",
        "我最喜欢的电影是《星际穿越》，看了不下5遍",
        "我在一家互联网公司做后端开发，工作3年了",
        "我习惯用 VS Code 写代码，装了很多插件",
        "周末我喜欢去咖啡馆看书，最近在读《人类简史》",
        "我对 Docker 和 Kubernetes 比较熟悉",
        "我计划明年去日本旅行，想去看樱花",
    ],
    "bob": [
        "我是一名前端工程师，主要使用 React 技术栈",
        "我每周打两次羽毛球，是公司羽毛球队的成员",
        "我最近在研究 WebAssembly，觉得很有前景",
        "我养了两条金鱼，一条红色一条黑色",
        "我喜欢听摇滚音乐，最喜欢的乐队是 Coldplay",
        "我的早餐通常是牛奶加全麦面包",
        "我用 MacBook Pro 开发，配了一个4K显示器",
        "我正在考虑转向全栈开发，在学习 Node.js",
        "我住在北京朝阳区，通勤大概40分钟",
        "我喜欢玩策略类游戏，最近在玩文明6",
    ],
    "charlie": [
        "我是一名数据分析师，日常使用 SQL 和 Python",
        "我每天冥想15分钟，已经坚持了半年",
        "我对数据可视化很感兴趣，常用 ECharts 和 D3.js",
        "我有一个3岁的女儿，她最喜欢画画",
        "我喜欢看科幻小说，最近在读刘慈欣的《三体》",
        "我在上海浦东工作，公司离家很近走路10分钟",
        "我周末喜欢做饭，拿手菜是红烧肉和糖醋排骨",
        "我正在学习 Apache Spark 处理大数据",
        "我喜欢摄影，用的是索尼 A7M4 相机",
        "我计划考一个 AWS 云计算认证",
    ],
}


def add_memory(user_id: str, content: str):
    """通过 API 添加一条记忆"""
    payload = {
        "messages": [{"role": "user", "content": content}],
        "user_id": user_id,
        "infer": False,           # 原文存储，不让 AI 拆分
        "auto_categorize": False, # 关闭自动分类，加快速度
    }
    resp = requests.post(f"{API_BASE}/v1/memories/", json=payload, timeout=60)
    return resp.status_code, resp.json()


def main():
    total = 0
    success = 0
    failed = 0

    for user_id, memories in TEST_DATA.items():
        print(f"\n{'='*50}")
        print(f"正在为用户 [{user_id}] 添加 {len(memories)} 条记忆...")
        print(f"{'='*50}")

        for i, content in enumerate(memories, 1):
            try:
                status, result = add_memory(user_id, content)
                total += 1
                if status == 200:
                    success += 1
                    print(f"  [{i:2d}/10] OK {content[:40]}...")
                else:
                    failed += 1
                    print(f"  [{i:2d}/10] FAIL 状态码 {status}: {result}")
            except Exception as e:
                total += 1
                failed += 1
                print(f"  [{i:2d}/10] FAIL 异常: {e}")

            # 每条之间稍微间隔，避免并发压力
            time.sleep(0.5)

    print(f"\n{'='*50}")
    print(f"完成！总计: {total}, 成功: {success}, 失败: {failed}")
    print(f"{'='*50}")


if __name__ == "__main__":
    main()
