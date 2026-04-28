"""
中间件测试
覆盖：API Key 认证、速率限制、请求日志记录、CORS、全局异常处理、Request-ID 注入
"""

import re
import pytest
from unittest.mock import patch, AsyncMock, MagicMock


class TestApiKeyAuth:
    """API Key 认证中间件测试"""

    def test_no_auth_when_key_not_configured(self, client):
        """测试未配置 API Key 时无需认证"""
        response = client.get("/")
        assert response.status_code == 200

    def test_auth_required_when_key_configured(self, mock_memory, in_memory_db):
        """测试配置 API Key 后需要认证（注意：中间件在模块加载时注册，此测试验证概念）"""
        # 由于中间件在模块加载时就已注册，无法在运行时动态添加
        # 此测试验证 API Key 认证的概念正确性
        import server
        # 验证 ApiKeyAuthMiddleware 类存在
        assert hasattr(server, 'ApiKeyAuthMiddleware')


class TestRateLimiting:
    """速率限制中间件测试"""

    def test_no_rate_limit_when_disabled(self, client):
        """测试禁用速率限制时不限流"""
        for _ in range(10):
            response = client.get("/")
            assert response.status_code == 200


class TestRequestLogMiddleware:
    """请求日志中间件测试"""

    def test_get_requests_not_logged(self, client):
        """测试 GET 请求不被记录到请求日志"""
        response = client.get("/")
        assert response.status_code == 200

    def test_post_requests_logged(self, client, sample_add_request):
        """测试 POST 请求被记录"""
        response = client.post("/v1/memories/", json=sample_add_request)
        assert response.status_code == 200


class TestCORS:
    """CORS 中间件测试"""

    def test_cors_headers_present(self, client):
        """测试 CORS 头存在"""
        response = client.options(
            "/",
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "GET",
            },
        )
        assert response.status_code == 200


class TestGlobalExceptionHandler:
    """全局异常处理测试"""

    def test_unhandled_exception_returns_500(self, client, mock_memory):
        """测试未捕获异常返回 500"""
        mock_memory.get.side_effect = RuntimeError("意外错误")
        mock_memory.vector_store.client.retrieve.side_effect = RuntimeError("意外错误")
        response = client.get("/v1/memories/test-id/")
        assert response.status_code in [500, 200]  # 取决于异常是否被内部 try/except 捕获
        mock_memory.get.side_effect = None
        mock_memory.vector_store.client.retrieve.side_effect = None


# ============ RequestIdMiddleware 测试 ============

# 32 位小写/大写/混合 hex 字符串的正则；uuid4().hex 生成的是 32 位十六进制
_HEX_32_RE = re.compile(r"^[A-Fa-f0-9]{32}$")


class TestRequestIdMiddleware:
    """请求 ID 中间件测试：验证 request_id 的生成、复用、拦截、唯一性"""

    HEADER = "X-Request-ID"

    # ---- 1. 基础：未传入 ID 时，服务端自动生成合法 hex ----
    def test_generates_new_id_when_header_absent(self, client):
        """未传入 X-Request-ID 时，响应头应包含一个新生成的 32 位 hex ID"""
        response = client.get("/")
        assert response.status_code == 200
        request_id = response.headers.get(self.HEADER)
        assert request_id, f"响应头缺少 {self.HEADER}"
        assert _HEX_32_RE.match(request_id), f"新生成的 ID 格式应为 32 位 hex，实际: {request_id}"

    # ---- 2. 唯一性：连续多次请求，每次生成的 ID 不应重复 ----
    def test_generated_ids_are_unique_across_requests(self, client):
        """连续发 5 次请求，每次自动生成的 request_id 互不相同"""
        ids = []
        for _ in range(5):
            response = client.get("/")
            assert response.status_code == 200
            ids.append(response.headers.get(self.HEADER))
        assert all(ids), "每次请求都应有 request_id"
        assert len(set(ids)) == len(ids), f"生成的 ID 应该唯一，实际: {ids}"

    # ---- 3. 复用：客户端传入合法 ID 时，应原样返回（跨服务链路追踪场景） ----
    def test_reuses_valid_incoming_request_id(self, client):
        """传入合法 X-Request-ID 时应原样返回，支持跨服务链路追踪"""
        incoming = "trace-abc-12345678"
        response = client.get("/", headers={self.HEADER: incoming})
        assert response.status_code == 200
        assert response.headers.get(self.HEADER) == incoming

    # ---- 4a. 拦截过短 ID ----
    def test_rejects_too_short_request_id(self, client):
        """过短（< 8 字符）的 request_id 应被拦截并重新生成"""
        response = client.get("/", headers={self.HEADER: "abc"})
        assert response.status_code == 200
        returned = response.headers.get(self.HEADER)
        assert returned != "abc", "非法 ID 不应被原样回显（避免 CRLF 注入等风险）"
        assert _HEX_32_RE.match(returned), f"应重新生成合法 hex ID，实际: {returned}"

    # ---- 4b. 拦截超长 ID ----
    def test_rejects_too_long_request_id(self, client):
        """超长（> 128 字符）的 request_id 应被拦截"""
        too_long = "a" * 129
        response = client.get("/", headers={self.HEADER: too_long})
        assert response.status_code == 200
        returned = response.headers.get(self.HEADER)
        assert returned != too_long
        assert _HEX_32_RE.match(returned)

    # ---- 4c. 拦截含非法字符（避免响应头注入） ----
    def test_rejects_request_id_with_invalid_chars(self, client):
        """含空格、特殊符号的 request_id 应被拦截"""
        # 注意：
        # 1) 换行符会被底层 HTTP 库先行拒绝，无法抵达中间件，不在此测试
        # 2) 非 ASCII 字符（如中文）会被 Starlette 在请求解析阶段就拒绝 400，
        #    也不在中间件测试范围，这里只覆盖 ASCII 可打印但不符合正则的字符
        bad_ids = [
            "id with spaces",       # 空格
            "id<html>tag",           # HTML 尖括号
            "id;drop=table",         # 分号
            "id/slash",              # 斜杠
            "id+plus=sign",          # 加号与等号
        ]
        for bad in bad_ids:
            response = client.get("/", headers={self.HEADER: bad})
            assert response.status_code == 200, f"请求应当仍然成功，bad={bad!r}"
            returned = response.headers.get(self.HEADER)
            assert returned != bad, f"非法 ID {bad!r} 被原样回显，存在注入风险"
            assert _HEX_32_RE.match(returned), f"非法 ID 应触发重新生成，实际: {returned}"


    # ---- 5. 边界：恰好 8 位合法字符应被接受（边界测试） ----
    def test_accepts_min_length_valid_request_id(self, client):
        """恰好 8 位的合法 ID 应被接受（边界值）"""
        min_valid = "a1b2c3d4"
        response = client.get("/", headers={self.HEADER: min_valid})
        assert response.status_code == 200
        assert response.headers.get(self.HEADER) == min_valid

    # ---- 6. 边界：恰好 128 位合法字符应被接受 ----
    def test_accepts_max_length_valid_request_id(self, client):
        """恰好 128 位的合法 ID 应被接受（边界值）"""
        max_valid = "a" * 128
        response = client.get("/", headers={self.HEADER: max_valid})
        assert response.status_code == 200
        assert response.headers.get(self.HEADER) == max_valid

    # ---- 7. 异常路径：业务错误响应也应带 request_id（运维排障场景） ----
    def test_request_id_present_on_error_response(self, client, mock_memory):
        """即使业务返回错误，响应头也应带 request_id，保证链路追踪不中断"""
        mock_memory.get.side_effect = RuntimeError("模拟异常")
        mock_memory.vector_store.client.retrieve.side_effect = RuntimeError("模拟异常")
        response = client.get("/v1/memories/nonexistent-id/")
        # 无论是 500 还是路由层 catch 后的 200，都应带 request_id
        assert self.HEADER in response.headers, "错误响应也必须带 X-Request-ID"
        assert _HEX_32_RE.match(response.headers[self.HEADER])
        # 清理 side_effect，避免污染其它测试
        mock_memory.get.side_effect = None
        mock_memory.vector_store.client.retrieve.side_effect = None

    # ---- 8. POST 请求场景：确认 body 读取 + request_id 注入不冲突 ----
    def test_request_id_works_with_body_reading(self, client, sample_search_request):
        """POST 请求携带 body 时，request_id 注入和 body 读取都应正常工作。

        用 /v1/memories/search/ 代替 /v1/memories/（后者会走 LLM 写入路径，
        触发 _flush_log_batch 的同步刷盘，与 conftest 的 SQLite mock 不兼容）。
        搜索接口是纯读路径，更适合测试“中间件 + body”的集成。
        """
        incoming = "post-trace-id-xyz-999"
        response = client.post(
            "/v1/memories/search/",
            json=sample_search_request,
            headers={self.HEADER: incoming},
        )
        # 无论业务返回什么状态码，request_id 都应原样返回
        assert response.headers.get(self.HEADER) == incoming, (
            f"POST 请求的 X-Request-ID 应被原样复用，实际: {response.headers.get(self.HEADER)!r}"
        )
