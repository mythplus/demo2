/**
 * Mem0 API - 核心请求封装
 *
 * 提供通用的 HTTP 请求方法，支持超时控制、JWT Bearer Token 认证和 401 自动跳转。
 * 各资源 API 模块（memories-api、graph-api 等）基于此模块构建。
 */

// API 基础地址
// 浏览器侧统一走 Next.js rewrite 代理（/api/mem0/:path* → 后端），
// 避免浏览器直连 http://localhost:8080 在云环境/远程访问时不可达。
const API_BASE = "/api/mem0";

// API Key 认证（与后端 security.api_key 配置对应，向后兼容）
const API_KEY = process.env.NEXT_PUBLIC_MEM0_API_KEY || "";

// 全局请求超时（毫秒）
const DEFAULT_TIMEOUT = 30000;

// 从 localStorage 获取 JWT token（避免在模块加载时引入 store 循环依赖）
function getAccessToken(): string | null {
  try {
    const stored = localStorage.getItem("mem0-auth");
    if (stored) {
      const parsed = JSON.parse(stored);
      return parsed?.state?.accessToken || null;
    }
  } catch {
    // ignore
  }
  return null;
}

/**
 * 构建带认证的请求头
 * 优先使用 JWT Bearer Token，其次使用 API Key
 */
export function buildAuthHeaders(
  extra?: Record<string, string>
): Record<string, string> {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
  };

  const token = getAccessToken();
  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  } else if (API_KEY) {
    headers["X-API-Key"] = API_KEY;
  }

  if (extra) {
    Object.assign(headers, extra);
  }
  return headers;
}

/**
 * 通用请求方法（带全局超时控制 + 401 拦截）
 */
export async function request<T>(
  endpoint: string,
  options?: RequestInit & { timeout?: number }
): Promise<T> {
  const url = `${API_BASE}${endpoint}`;
  const timeout = options?.timeout ?? DEFAULT_TIMEOUT;

  const headers = buildAuthHeaders(
    options?.headers as Record<string, string> | undefined
  );

  // 超时控制
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), timeout);

  try {
    const response = await fetch(url, {
      ...options,
      headers,
      signal: controller.signal,
    });

    // 401 拦截：清除认证状态并跳转登录页
    if (response.status === 401) {
      // 避免在登录页自身触发循环跳转
      if (!window.location.pathname.startsWith("/login")) {
        localStorage.removeItem("mem0-auth");
        window.location.href = "/login";
      }
      const error = await response.json().catch(() => ({
        detail: "认证失败，请重新登录",
      }));
      throw new Error(error.detail || "认证失败，请重新登录");
    }

    if (!response.ok) {
      const error = await response.json().catch(() => ({
        detail: `HTTP ${response.status}: ${response.statusText}`,
      }));
      throw new Error(error.detail || "请求失败");
    }

    // DELETE 请求可能返回空内容
    const text = await response.text();
    if (!text) return {} as T;

    return JSON.parse(text) as T;
  } catch (err) {
    if (err instanceof DOMException && err.name === "AbortError") {
      throw new Error(`请求超时（${timeout / 1000}秒），请检查网络连接或服务状态`);
    }
    // 处理非 DOMException 的 AbortError（某些浏览器/环境差异）
    if (err instanceof Error && err.name === "AbortError") {
      throw new Error(`请求超时（${timeout / 1000}秒），请检查网络连接或服务状态`);
    }
    throw err;
  } finally {
    clearTimeout(timeoutId);
  }
}

/**
 * 构建 URL 查询参数
 */
export function buildQuery(
  params: Record<string, string | number | undefined | string[]>
): string {
  const qs = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value === undefined || value === null) continue;
    if (Array.isArray(value)) {
      if (value.length > 0) qs.set(key, value.join(","));
    } else {
      qs.set(key, String(value));
    }
  }
  const str = qs.toString();
  return str ? `?${str}` : "";
}

// 导出基础配置供其他模块使用
export { API_BASE, API_KEY };
