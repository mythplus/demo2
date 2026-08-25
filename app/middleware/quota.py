"""
配额与速率限制中间件

在认证中间件之后执行，对已认证的请求进行：
1. 速率限制检查（每分钟/每小时）
2. 配额检查（每日 API 调用上限 + 记忆总量上限）

对公开路径（登录、健康检查、文档）跳过检查。
"""
import logging

from fastapi import Request
from fastapi.responses import JSONResponse

from app.middleware.rate_limiter import check_rate_limit, check_quota

logger = logging.getLogger(__name__)

# 不需要配额/限流检查的路径前缀
EXEMPT_PREFIXES = (
    "/v1/auth",
    "/docs",
    "/redoc",
    "/openapi.json",
    "/v1/health",
)


def _is_exempt(path: str) -> bool:
    """判断是否豁免限流/配额"""
    if path == "/":
        return True
    for prefix in EXEMPT_PREFIXES:
        if path.startswith(prefix):
            return True
    return False


async def quota_rate_limit_middleware(request: Request, call_next):
    """配额 + 速率限制中间件"""
    if _is_exempt(request.url.path):
        return await call_next(request)

    tenant_id = getattr(request.state, "tenant_id", None)
    if not tenant_id:
        return await call_next(request)

    # --- 速率限制检查 ---
    try:
        allowed, reason = check_rate_limit(tenant_id)
        if not allowed:
            logger.warning(f"租户 {tenant_id} 触发速率限制: {reason}")
            return JSONResponse(
                status_code=429,
                content={"detail": f"请求过于频繁：{reason}"},
                headers={"Retry-After": "60"},
            )
    except Exception as e:
        logger.warning(f"速率限制检查异常（跳过）: {e}")

    # --- 配额检查（仅对写操作和 API 调用计数） ---
    try:
        allowed, reason, usage = check_quota(tenant_id)
        if not allowed:
            logger.warning(f"租户 {tenant_id} 配额超限: {reason}")
            return JSONResponse(
                status_code=429,
                content={"detail": f"配额超限：{reason}", "usage": usage},
                headers={"Retry-After": "3600"},
            )
    except Exception as e:
        logger.warning(f"配额检查异常（跳过）: {e}")

    return await call_next(request)
