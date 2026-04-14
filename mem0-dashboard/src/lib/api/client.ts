/**
 * Mem0 API 客户端
 * 对接 mem0 server start 启动的 FastAPI 服务
 */

import type {
  Memory,
  AddMemoryRequest,
  AddMemoryResponse,
  SearchMemoryRequest,
  SearchMemoryResponse,
  UpdateMemoryRequest,
  DeleteResponse,
  MemoryHistory,
  FilterParams,
  StatsResponse,
  PaginatedMemoriesResponse,
  Category,
  MemoryState,
  MemorySummaryResponse,
  RelatedMemoriesResponse,
  AccessLogsResponse,
  RequestLogsResponse,
  RequestLogsStats,
  BatchImportRequest,
  BatchImportResponse,
  BatchDeleteRequest,
  BatchDeleteResponse,
  GraphData,
  GraphEntitiesResponse,
  GraphRelationsResponse,
  GraphSearchRequest,
  GraphSearchResponse,
  GraphStatsResponse,
  GraphHealthResponse,
  ConfigInfoResponse,
  ServiceTestResponse,
  PlaygroundChatRequest,
  PlaygroundChatResponse,
  PlaygroundSSEEvent,
} from "./types";

// API 基础地址
const API_BASE =
  process.env.NEXT_PUBLIC_MEM0_API_URL || "http://localhost:8080";

// API Key 认证（与后端 security.api_key 配置对应）
const API_KEY = process.env.NEXT_PUBLIC_MEM0_API_KEY || "";

// 全局请求超时（毫秒）
const DEFAULT_TIMEOUT = 30000;

/**
 * 通用请求方法（带全局超时控制）
 */
async function request<T>(
  endpoint: string,
  options?: RequestInit & { timeout?: number; externalSignal?: AbortSignal }
): Promise<T> {
  const url = `${API_BASE}${endpoint}`;
  const timeout = options?.timeout ?? DEFAULT_TIMEOUT;

  // 构建请求头，如果配置了 API Key 则自动携带认证头
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
  };
  if (API_KEY) {
    headers["X-API-Key"] = API_KEY;
  }

  // 超时控制 + 外部取消信号合并
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), timeout);

  // 如果有外部 signal，监听其 abort 事件来联动取消
  const externalSignal = options?.externalSignal;
  let onExternalAbort: (() => void) | undefined;
  if (externalSignal) {
    if (externalSignal.aborted) {
      controller.abort();
    } else {
      onExternalAbort = () => controller.abort();
      externalSignal.addEventListener("abort", onExternalAbort);
    }
  }

  try {
    const response = await fetch(url, {
      headers: {
        ...headers,
        ...options?.headers,
      },
      ...options,
      signal: controller.signal,
    });

    if (!response.ok) {
      const error = await response.json().catch(() => ({
        detail: `HTTP ${response.status}: ${response.statusText}`,
      }));
      // detail 可能是字符串或数组（如 Pydantic 422 验证错误），需统一处理
      const detail = error.detail;
      const message =
        typeof detail === "string"
          ? detail
          : Array.isArray(detail)
            ? detail.map((d: Record<string, unknown>) => d.msg || JSON.stringify(d)).join("; ")
            : detail
              ? JSON.stringify(detail)
              : "请求失败";
      throw new Error(message);
    }

    // DELETE 请求可能返回空内容
    const text = await response.text();
    if (!text) return {} as T;

    return JSON.parse(text) as T;
  } catch (err) {
    if (err instanceof DOMException && err.name === "AbortError") {
      throw new Error(`请求超时（${timeout / 1000}秒），请检查网络连接或服务状态`);
    }
    throw err;
  } finally {
    clearTimeout(timeoutId);
    if (onExternalAbort && externalSignal) {
      externalSignal.removeEventListener("abort", onExternalAbort);
    }
  }
}

/**
 * Mem0 API 客户端
 */
export const mem0Api = {
  // ============ 记忆 CRUD ============

  /**
   * 添加记忆（支持 categories 和 state）
   * @param data 包含消息列表和用户信息
   */
  async addMemory(data: AddMemoryRequest): Promise<AddMemoryResponse> {
    return request<AddMemoryResponse>("/v1/memories/", {
      method: "POST",
      body: JSON.stringify(data),
    });
  },

  /**
   * 批量导入记忆
   * @param data 包含多条记忆和默认配置
   */
  async batchImport(data: BatchImportRequest, signal?: AbortSignal): Promise<BatchImportResponse> {
    return request<BatchImportResponse>("/v1/memories/batch", {
      method: "POST",
      body: JSON.stringify(data),
      timeout: 30 * 60 * 1000, // 30 分钟：每条记忆需要 AI 分类 + 向量化，默认 30s 不够
      externalSignal: signal,
    });
  },

  /**
   * 批量导入完成后发送 Webhook 汇总通知
   * @param summary 全局导入汇总信息
   */
  async batchImportNotify(summary: { total: number; success: number; failed: number; skipped?: number }): Promise<void> {
    return request<void>("/v1/memories/batch-import-notify", {
      method: "POST",
      body: JSON.stringify(summary),
    });
  },

  /**
   * 获取记忆列表（支持多维筛选；传 page/page_size 时返回分页结果）
   * @param filters 可选的筛选参数
   */
  async getMemories(filters?: FilterParams | string): Promise<Memory[] | PaginatedMemoriesResponse> {
    const params = new URLSearchParams();

    if (typeof filters === "string") {
      // 兼容旧的 userId 参数调用方式
      if (filters) params.set("user_id", filters);
    } else if (filters) {
      if (filters.user_id) params.set("user_id", filters.user_id);
      if (filters.categories && filters.categories.length > 0) {
        params.set("categories", filters.categories.join(","));
      }
      if (filters.state) params.set("state", filters.state);
      if (filters.date_from) params.set("date_from", filters.date_from);
      if (filters.date_to) params.set("date_to", filters.date_to);
      if (filters.search) params.set("search", filters.search);
      if (filters.sort_by) params.set("sort_by", filters.sort_by);
      if (filters.sort_order) params.set("sort_order", filters.sort_order);
      if (typeof filters.page === "number") params.set("page", String(filters.page));
      if (typeof filters.page_size === "number") params.set("page_size", String(filters.page_size));
      if (filters.exclude_state) params.set("exclude_state", filters.exclude_state);
    }

    const query = params.toString();
    const response = await request<Memory[] | PaginatedMemoriesResponse>(`/v1/memories/${query ? `?${query}` : ""}`);
    return response;
  },

  /**
   * 获取用户汇总列表（供用户页、筛选器、搜索页和导出页复用）
   */
  async getMemoryUsers(): Promise<{ user_id: string; memory_count: number; last_active?: string }[]> {
    return request<{ user_id: string; memory_count: number; last_active?: string }[]>('/v1/memories/users/');
  },

  /**
   * 获取首页摘要（最近记忆 + 活跃用户）
   */
  async getMemorySummary(params?: { recent_limit?: number; top_users_limit?: number }): Promise<MemorySummaryResponse> {
    const qs = new URLSearchParams();
    if (params?.recent_limit) qs.set('recent_limit', String(params.recent_limit));
    if (params?.top_users_limit) qs.set('top_users_limit', String(params.top_users_limit));
    const query = qs.toString();
    return request<MemorySummaryResponse>(`/v1/memories/summary/${query ? `?${query}` : ''}`);
  },

  /**
   * 获取单条记忆
   * @param memoryId 记忆 ID
   */
  async getMemory(memoryId: string): Promise<Memory> {
    return request<Memory>(`/v1/memories/${encodeURIComponent(memoryId)}/`);
  },

  /**
   * 更新记忆（支持 text、metadata、categories、state 更新）
   * @param memoryId 记忆 ID
   * @param data 更新内容
   */
  async updateMemory(
    memoryId: string,
    data: UpdateMemoryRequest
  ): Promise<Memory> {
    return request<Memory>(`/v1/memories/${encodeURIComponent(memoryId)}/`, {
      method: "PUT",
      body: JSON.stringify(data),
    });
  },

  /**
   * 删除单条记忆
   * @param memoryId 记忆 ID
   */
  async deleteMemory(memoryId: string): Promise<DeleteResponse> {
    return request<DeleteResponse>(`/v1/memories/${encodeURIComponent(memoryId)}/`, {
      method: "DELETE",
    });
  },

  /**
   * 批量删除记忆（一次请求删除多条，替代逐条 Promise.all）
   * @param memoryIds 记忆 ID 列表
   */
  async batchDeleteMemories(memoryIds: string[]): Promise<BatchDeleteResponse> {
    return request<BatchDeleteResponse>("/v1/memories/batch-delete", {
      method: "POST",
      body: JSON.stringify({ memory_ids: memoryIds }),
    });
  },

  /**
   * 删除用户的所有记忆（软删除）
   * @param userId 用户 ID
   */
  async deleteAllMemories(userId: string): Promise<DeleteResponse> {
    return request<DeleteResponse>(`/v1/memories/?user_id=${encodeURIComponent(userId)}`, {
      method: "DELETE",
    });
  },

  /**
   * 硬删除用户：物理删除该用户及其所有记忆数据（不可恢复）
   * @param userId 用户 ID
   */
  async hardDeleteUser(userId: string): Promise<DeleteResponse> {
    return request<DeleteResponse>(`/v1/memories/user/${encodeURIComponent(userId)}/hard-delete`, {
      method: "DELETE",
    });
  },

  // ============ 搜索 ============

  /**
   * 语义检索记忆
   * @param data 搜索参数
   */
  async searchMemories(
    data: SearchMemoryRequest
  ): Promise<SearchMemoryResponse> {
    return request<SearchMemoryResponse>("/v1/memories/search/", {
      method: "POST",
      body: JSON.stringify(data),
    });
  },

  // ============ 历史记录 ============

  /**
   * 获取记忆的修改历史
   * @param memoryId 记忆 ID
   */
  async getMemoryHistory(memoryId: string): Promise<MemoryHistory[]> {
    return request<MemoryHistory[]>(`/v1/memories/history/${encodeURIComponent(memoryId)}/`);
  },

  // ============ 统计 ============

  /**
   * 获取统计数据（分类分布、状态分布、每日趋势）
   */
  async getStats(): Promise<StatsResponse> {
    return request<StatsResponse>("/v1/stats/");
  },

  // ============ 关联记忆 ============

  /**
   * 获取语义相关的记忆
   * @param memoryId 记忆 ID
   * @param limit 返回数量，默认 5
   */
  async getRelatedMemories(memoryId: string, limit: number = 5): Promise<RelatedMemoriesResponse> {
    return request<RelatedMemoriesResponse>(`/v1/memories/${encodeURIComponent(memoryId)}/related/?limit=${limit}`);
  },

  // ============ 访问日志 ============

  /**
   * 获取记忆的访问日志
   */
  async getAccessLogs(memoryId: string, limit: number = 20): Promise<AccessLogsResponse> {
    return request<AccessLogsResponse>(`/v1/memories/${encodeURIComponent(memoryId)}/access-logs/?limit=${limit}`);
  },

  // ============ 请求日志 ============

  /**
   * 获取请求日志列表
   */
  async getRequestLogs(params?: { request_type?: string; since?: string; until?: string; limit?: number; offset?: number }): Promise<RequestLogsResponse> {
    const qs = new URLSearchParams();
    if (params?.request_type) qs.set("request_type", params.request_type);
    if (params?.since) qs.set("since", params.since);
    if (params?.until) qs.set("until", params.until);
    if (params?.limit) qs.set("limit", String(params.limit));
    if (params?.offset) qs.set("offset", String(params.offset));
    const q = qs.toString();
    return request<RequestLogsResponse>(`/v1/request-logs/${q ? `?${q}` : ""}`);
  },

  /**
   * 获取请求日志统计
   */
  async getRequestLogsStats(since?: string, until?: string): Promise<RequestLogsStats> {
    const qs = new URLSearchParams();
    if (since) qs.set("since", since);
    if (until) qs.set("until", until);
    const q = qs.toString();
    return request<RequestLogsStats>(`/v1/request-logs/stats/${q ? `?${q}` : ""}`);
  },

  // ============ 健康检查 ============

  /**
   * 检查 API 连接状态
   */
  async healthCheck(): Promise<boolean> {
    try {
      const headers: Record<string, string> = {};
      if (API_KEY) {
        headers["X-API-Key"] = API_KEY;
      }
      const response = await fetch(`${API_BASE}/`, {
        method: "GET",
        headers,
        signal: AbortSignal.timeout(5000),
      });
      return response.ok;
    } catch {
      return false;
    }
  },

  // ============ 图谱记忆 (Graph Memory) ============

  /**
   * 获取图谱统计信息
   */
  async getGraphStats(): Promise<GraphStatsResponse> {
    return request<GraphStatsResponse>("/v1/graph/stats");
  },

  /**
   * 获取实体列表
   */
  async getGraphEntities(params?: {
    user_id?: string;
    search?: string;
    limit?: number;
    offset?: number;
  }): Promise<GraphEntitiesResponse> {
    const qs = new URLSearchParams();
    if (params?.user_id) qs.set("user_id", params.user_id);
    if (params?.search) qs.set("search", params.search);
    if (params?.limit) qs.set("limit", String(params.limit));
    if (params?.offset) qs.set("offset", String(params.offset));
    const q = qs.toString();
    return request<GraphEntitiesResponse>(`/v1/graph/entities${q ? `?${q}` : ""}`);
  },

  /**
   * 获取关系三元组列表
   */
  async getGraphRelations(params?: {
    user_id?: string;
    search?: string;
    limit?: number;
    offset?: number;
  }): Promise<GraphRelationsResponse> {
    const qs = new URLSearchParams();
    if (params?.user_id) qs.set("user_id", params.user_id);
    if (params?.search) qs.set("search", params.search);
    if (params?.limit) qs.set("limit", String(params.limit));
    if (params?.offset) qs.set("offset", String(params.offset));
    const q = qs.toString();
    return request<GraphRelationsResponse>(`/v1/graph/relations${q ? `?${q}` : ""}`);
  },

  /**
   * 图谱搜索
   */
  async searchGraph(data: GraphSearchRequest): Promise<GraphSearchResponse> {
    return request<GraphSearchResponse>("/v1/graph/search", {
      method: "POST",
      body: JSON.stringify(data),
    });
  },

  /**
   * 获取指定用户的子图数据（用于可视化）
   */
  async getUserGraph(userId: string, limit?: number): Promise<GraphData> {
    const qs = limit ? `?limit=${limit}` : "";
    return request<GraphData>(`/v1/graph/user/${encodeURIComponent(userId)}${qs}`);
  },

  /**
   * 获取全部图谱数据（用于可视化）
   */
  async getAllGraph(limit?: number): Promise<GraphData> {
    const qs = limit ? `?limit=${limit}` : "";
    return request<GraphData>(`/v1/graph/all${qs}`);
  },

  /**
   * 删除实体及其关联关系
   */
  async deleteGraphEntity(entityName: string, userId?: string): Promise<DeleteResponse> {
    const qs = userId ? `?user_id=${encodeURIComponent(userId)}` : "";
    return request<DeleteResponse>(`/v1/graph/entities/${encodeURIComponent(entityName)}${qs}`, {
      method: "DELETE",
    });
  },

  /**
   * 删除指定关系
   */
  async deleteGraphRelation(source: string, relation: string, target: string): Promise<DeleteResponse> {
    const qs = new URLSearchParams({ source, relation, target }).toString();
    return request<DeleteResponse>(`/v1/graph/relations?${qs}`, {
      method: "DELETE",
    });
  },

  /**
   * 检查 Neo4j 图数据库连接状态
   */
  async graphHealthCheck(): Promise<GraphHealthResponse> {
    return request<GraphHealthResponse>("/v1/graph/health");
  },

  // ============ 系统配置信息 (Config) ============

  /**
   * 获取系统配置信息（LLM、Embedder、向量数据库、图数据库）
   */
  async getConfigInfo(): Promise<ConfigInfoResponse> {
    return request<ConfigInfoResponse>("/v1/config/info");
  },

  /**
   * 测试 LLM 大模型连接
   */
  async testLLMConnection(): Promise<ServiceTestResponse> {
    return request<ServiceTestResponse>("/v1/config/test-llm");
  },

  /**
   * 测试 Embedder 嵌入模型连接
   */
  async testEmbedderConnection(): Promise<ServiceTestResponse> {
    return request<ServiceTestResponse>("/v1/config/test-embedder");
  },

  // ============ Playground 对话 ============

  /**
   * Playground 非流式对话
   */
  async playgroundChat(data: PlaygroundChatRequest): Promise<PlaygroundChatResponse> {
    return request<PlaygroundChatResponse>("/v1/playground/chat", {
      method: "POST",
      body: JSON.stringify(data),
      timeout: 120000,
    });
  },

  /**
   * Playground 流式对话（SSE）
   * 返回一个 ReadableStream，调用方通过 EventSource 或手动解析 SSE 消息
   */
  async playgroundChatStream(
    data: PlaygroundChatRequest,
    onEvent: (event: PlaygroundSSEEvent) => void,
    signal?: AbortSignal,
  ): Promise<void> {
    const url = `${API_BASE}/v1/playground/chat/stream`;
    const headers: Record<string, string> = {
      "Content-Type": "application/json",
    };
    if (API_KEY) {
      headers["X-API-Key"] = API_KEY;
    }

    const response = await fetch(url, {
      method: "POST",
      headers,
      body: JSON.stringify(data),
      signal,
    });

    if (!response.ok) {
      const error = await response.json().catch(() => ({ detail: `HTTP ${response.status}` }));
      throw new Error(typeof error.detail === "string" ? error.detail : JSON.stringify(error.detail));
    }

    const reader = response.body?.getReader();
    if (!reader) throw new Error("无法获取响应流");

    const decoder = new TextDecoder();
    let buffer = "";

    try {
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n");
        buffer = lines.pop() || "";

        for (const line of lines) {
          if (line.startsWith("data: ")) {
            try {
              const eventData = JSON.parse(line.slice(6));
              onEvent(eventData as PlaygroundSSEEvent);
            } catch {
              // 忽略解析失败的行
            }
          }
        }
      }
    } finally {
      reader.releaseLock();
    }
  },

  // ============ Webhooks ============

  async getWebhooks(): Promise<{ webhooks: any[]; total: number }> {
    return request<{ webhooks: any[]; total: number }>("/v1/webhooks/");
  },

  async createWebhook(data: any): Promise<any> {
    return request<any>("/v1/webhooks/", {
      method: "POST",
      body: JSON.stringify(data),
    });
  },

  async updateWebhook(id: string, data: any): Promise<any> {
    return request<any>(`/v1/webhooks/${id}`, {
      method: "PUT",
      body: JSON.stringify(data),
    });
  },

  async deleteWebhook(id: string): Promise<any> {
    return request<any>(`/v1/webhooks/${id}`, { method: "DELETE" });
  },

  async toggleWebhook(id: string): Promise<any> {
    return request<any>(`/v1/webhooks/${id}/toggle`, { method: "POST" });
  },

  async testWebhook(id: string): Promise<{ success: boolean; message: string }> {
    return request<{ success: boolean; message: string }>(`/v1/webhooks/${id}/test`, { method: "POST" });
  },
};
