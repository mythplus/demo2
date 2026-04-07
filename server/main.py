"""
Mem0 Dashboard 后端 API 服务 — uvicorn 启动入口
"""

import os
import logging

import uvicorn

from server.config import IS_PRODUCTION

logger = logging.getLogger(__name__)


def main():
    """启动 Mem0 API 服务"""
    # 默认监听 8080 端口，与前端 .env.local 中配置一致
    port = int(os.environ.get("MEM0_PORT", 8080))
    logger.info(f"启动 Mem0 API 服务，端口: {port}，环境: {'production' if IS_PRODUCTION else 'development'}")

    run_kwargs = {
        "host": "0.0.0.0",
        "port": port,
        "log_level": "info",
    }

    # 开发环境启用热重载，生产环境启用多 Worker + 性能优化
    if not IS_PRODUCTION:
        run_kwargs.update({
            "reload": True,
            "reload_includes": ["*.py"],
            "reload_excludes": ["qdrant_data/**", "*.log"],
        })
    else:
        import multiprocessing
        # 生产环境：多 Worker 利用多核 CPU，关闭 access log 减少 IO
        workers = int(os.environ.get("MEM0_WORKERS", min(multiprocessing.cpu_count(), 4)))
        run_kwargs.update({
            "workers": workers,
            "access_log": False,
            "timeout_keep_alive": 30,
        })
        logger.info(f"生产模式：启动 {workers} 个 Worker 进程")

    uvicorn.run("server.app:app", **run_kwargs)


if __name__ == "__main__":
    main()
