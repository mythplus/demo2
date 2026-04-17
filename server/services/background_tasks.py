"""后台任务托管服务
统一追踪 fire-and-forget 任务，记录异常并在应用关闭时优雅等待。
"""

import asyncio
import logging
from collections.abc import Coroutine
from typing import Any, Optional

logger = logging.getLogger(__name__)

_background_tasks: set[asyncio.Task[Any]] = set()


def create_background_task(coro: Coroutine[Any, Any, Any], *, name: Optional[str] = None) -> asyncio.Task[Any]:
    """创建可追踪的后台任务。"""
    task = asyncio.create_task(coro, name=name)
    _background_tasks.add(task)

    def _on_done(done_task: asyncio.Task[Any]) -> None:
        _background_tasks.discard(done_task)
        task_name = done_task.get_name()
        if done_task.cancelled():
            logger.warning(f"后台任务被取消: {task_name}")
            return

        try:
            exc = done_task.exception()
        except asyncio.CancelledError:
            logger.warning(f"后台任务被取消: {task_name}")
            return

        if exc is not None:
            logger.error(f"后台任务异常 [{task_name}]: {exc}", exc_info=exc)
        else:
            logger.debug(f"后台任务完成: {task_name}")

    task.add_done_callback(_on_done)
    return task


async def wait_background_tasks(timeout: float = 30.0) -> None:
    """等待所有后台任务完成；超时后取消剩余任务。"""
    if not _background_tasks:
        logger.info("无待完成的后台任务")
        return

    pending_count = len(_background_tasks)
    logger.info(f"等待 {pending_count} 个后台任务完成（超时 {timeout}s）...")
    done, pending = await asyncio.wait(list(_background_tasks), timeout=timeout)

    if pending:
        logger.warning(f"{len(pending)} 个后台任务超时未完成，开始取消")
        for task in pending:
            task.cancel()
        await asyncio.gather(*pending, return_exceptions=True)
    else:
        logger.info(f"所有 {len(done)} 个后台任务已完成")
