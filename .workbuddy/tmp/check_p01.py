"""验证 P0-1：生产环境缺失 POSTGRES_PASSWORD/HOST 时应 fail fast。"""
import os
import sys
from unittest.mock import patch

# 脚本从项目根目录执行，cwd 就是根
sys.path.insert(0, os.getcwd())

# Mock 掉 load_dotenv 避免 .env 被提前注入干扰校验
with patch("dotenv.load_dotenv", lambda *a, **k: None):
    for key in ("DATABASE_URL", "POSTGRES_PASSWORD", "POSTGRES_HOST", "POSTGRES_USER"):
        os.environ.pop(key, None)
    os.environ["MEM0_ENV"] = "production"

    try:
        import server.config  # noqa: F401
    except RuntimeError as e:
        print("OK fail fast:", e)
        sys.exit(0)
    except Exception as e:  # noqa: BLE001
        print("UNEXPECTED", type(e).__name__, e)
        sys.exit(2)
    else:
        print("NOT OK: DSN =", server.config.DATABASE_URL)
        sys.exit(3)
