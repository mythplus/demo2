"""
请求日志记录中间件 — 自动记录前端→后端的业务 API 请求
"""

import time
import logging
from datetime import datetime, timezone
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware

from server.services.log_service import (
    classify_request, extract_user_from_request,
    summarize_payload, log_request,
)

logger = logging.getLogger(__name__)


class RequestLogMiddleware(BaseHTTPMiddleware):
    """自动记录前端→后端的业务 API 请求（添加/搜索/删除/更新），不记录 GET/OPTIONS 等"""

    # 不记录的路径前缀（日志查询接口本身、静态资源等）
    # 注意：不能包含 "/"，否则所有路径都会被 startswith("/") 匹配而跳过
    SKIP_PATHS = {"/v1/request-logs", "/v1/access-logs", "/favicon.ico", "/_next"}

    # 精确匹配跳过的路径（如健康检查）
    SKIP_EXACT = {"/"}

    # 只记录这些 HTTP 方法（前端发出的写操作）
    RECORD_METHODS = {"POST", "PUT", "DELETE"}

    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        method = request.method

        # 只记录前端发出的写操作（POST/PUT/DELETE），跳过所有 GET/OPTIONS/HEAD
        # 同时跳过日志查询等非业务路径
        should_record = (
            method in self.RECORD_METHODS
            and path not in self.SKIP_EXACT
            and not any(path.startswith(p) for p in self.SKIP_PATHS)
        )

        if not should_record:
            return await call_next(request)

        # 读取请求体（不计入耗时）
        # 失败时兜底空串，但必须记录 warning，方便排查请求日志为空的问题
        body = ""
        try:
            body_bytes = await request.body()
            body = body_bytes.decode("utf-8", errors="ignore")
        except Exception as e:
            logger.warning(
                f"读取请求体失败，payload 日志将为空 [{method} {path}]: {e}",
                exc_info=True,
            )

        # 执行请求（只计算业务处理耗时）
        start_time = time.time()
        error_msg = ""
        status_code = 500
        try:
            response = await call_next(request)
            status_code = response.status_code
        except Exception as exc:
            error_msg = str(exc)[:500]
            raise
        finally:
            latency_ms = (time.time() - start_time) * 1000
            request_type = classify_request(method, path)
            user_id = extract_user_from_request(method, path, body)
            payload_summary = summarize_payload(method, path, body)
            ts = datetime.now(timezone.utc).isoformat()

            # 读取 RequestIdMiddleware 注入的 request_id（兜底生成空串，避免 AttributeError）
            request_id = getattr(request.state, "request_id", "") or ""

            # 结构化日志：通过 extra 透传 request_id，JsonLogFormatter 会自动写进 JSON 日志，
            # 这样业务排障时可以基于 request_id 把中间件、路由、下游服务的日志串在一起
            logger.info(
                f"请求完成 [{method} {path}] status={status_code} latency={latency_ms:.1f}ms user={user_id}",
                extra={
                    "request_id": request_id,
                    "method": method,
                    "path": path,
                    "status_code": status_code,
                    "latency_ms": round(latency_ms, 2),
                    "user_id": user_id,
                },
            )

            log_request(ts, method, path, request_type, user_id,
                        status_code, latency_ms, payload_summary, error_msg)

        return response
