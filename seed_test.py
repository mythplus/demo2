import requests
import time

API = "http://localhost:8080/v1/memories/"
USER = "test001"
MEMORIES = [
    "我喜欢每天早上跑步五公里锻炼身体",
    "我最喜欢的编程语言是Python和Go",
    "我养了一只橘猫叫小橘今年三岁了",
    "我在一家互联网公司做后端开发已经三年了",
    "周末的时候我喜欢去咖啡馆看书，最近在读刘慈欣的三体",
    "我喜欢吃川菜特别是麻婆豆腐和水煮鱼",
    "我的生日是三月十五日，是双鱼座",
    "我正在自学机器学习和深度学习的相关知识",
    "我计划明年去日本旅行看樱花",
    "我每天晚上十一点前睡觉保持早睡早起的习惯",
]

ok = 0
fail = 0
for i, text in enumerate(MEMORIES, 1):
    for attempt in range(3):
        try:
            r = requests.post(API, json={
                "messages": [{"role": "user", "content": text}],
                "user_id": USER,
                "infer": False,
                # auto_categorize 默认为 True，不再显式关闭
            }, timeout=300)
            status = r.status_code
            if status == 200:
                ok += 1
                print(f"[{i}/10] OK - {text[:25]}", flush=True)
                break
            else:
                print(f"[{i}/10] RETRY {attempt+1} status={status} {r.text[:100]}", flush=True)
                time.sleep(3)
        except Exception as e:
            print(f"[{i}/10] RETRY {attempt+1} error={e}", flush=True)
            time.sleep(3)
    else:
        fail += 1
        print(f"[{i}/10] FAIL - {text[:25]}", flush=True)
    time.sleep(1)

print(f"\nDone! ok={ok}, fail={fail}", flush=True)
