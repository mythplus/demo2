"""
请求 ID 注入中间件 — 为每个请求生成唯一 request_id，贯穿中间件链和业务逻辑。

- 入口：优先使用客户端 / 反向代理传入的 X-Request-ID 头（便于跨服务链路追踪），
  非法或缺失时即时生成一个新的 hex UUID。
- 注入：写入 request.state.request_id，全局异常处理器与其他中间件可直接读取。
- 出口：无论请求成功 / 失败，统一在响应头返回 X-Request-ID。
"""

import re
import uuid
import logging
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger(__name__)

# 仅接受安全字符（防止被恶意注入日志或响应头换行），长度限制 8-128
# 不合法时会被忽略，改为服务端重新生成
_SAFE_REQUEST_ID = re.compile(r"^[A-Za-z0-9\-_]{8,128}$")


class RequestIdMiddleware(BaseHTTPMiddleware):
    """请求 ID 注入中间件。

    应注册为最外层中间件（即最后一个 `app.add_middleware(...)`），
    这样它在进入任何业务中间件之前就能为整个请求链路提供 request_id。
    """

    HEADER_NAME = "X-Request-ID"

    async def dispatch(self, request: Request, call_next):
        # 1. 优先复用客户端 / 上游网关传入的 Request-ID，方便跨服务链路追踪
        incoming = request.headers.get(self.HEADER_NAME, "").strip()
        if incoming and _SAFE_REQUEST_ID.match(incoming):
            request_id = incoming
        else:
            if incoming:
                # 非法格式不直接采用，避免日志注入；但记录 debug 方便排查
                logger.debug(
                    f"忽略非法的 {self.HEADER_NAME} 头值（已重新生成）: {incoming[:64]!r}"
                )
            request_id = uuid.uuid4().hex

        # 2. 注入到 request.state，后续中间件与路由都能通过 request.state.request_id 访问
        request.state.request_id = request_id

        # 3. 无论响应成功还是异常，响应头都带上 request_id
        #    （全局异常处理器已单独处理了异常分支的响应头，这里覆盖正常路径）
        response = await call_next(request)
        response.headers[self.HEADER_NAME] = request_id
        return response
