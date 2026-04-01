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
  Category,
  MemoryState,
  RelatedMemoriesResponse,
  AccessLogsResponse,
  RequestLogsResponse,
  RequestLogsStats,
  BatchImportRequest,
  BatchImportResponse,
} from "./types";

// API 基础地址
const API_BASE =
  process.env.NEXT_PUBLIC_MEM0_API_URL || "http://localhost:8080";

/**
 * 通用请求方法
 */
async function request<T>(
  endpoint: string,
  options?: RequestInit
): Promise<T> {
  const url = `${API_BASE}${endpoint}`;

  const response = await fetch(url, {
    headers: {
      "Content-Type": "application/json",
      ...options?.headers,
    },
    ...options,
  });

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
  async batchImport(data: BatchImportRequest): Promise<BatchImportResponse> {
    return request<BatchImportResponse>("/v1/memories/batch", {
      method: "POST",
      body: JSON.stringify(data),
    });
  },

  /**
   * 获取所有记忆（支持多维筛选）
   * @param filters 可选的筛选参数
   */
  async getMemories(filters?: FilterParams | string): Promise<Memory[]> {
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
    }

    const query = params.toString();
    return request<Memory[]>(`/v1/memories/${query ? `?${query}` : ""}`);
  },

  /**
   * 获取单条记忆
   * @param memoryId 记忆 ID
   */
  async getMemory(memoryId: string): Promise<Memory> {
    return request<Memory>(`/v1/memories/${memoryId}/`);
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
    return request<Memory>(`/v1/memories/${memoryId}/`, {
      method: "PUT",
      body: JSON.stringify(data),
    });
  },

  /**
   * 删除单条记忆
   * @param memoryId 记忆 ID
   */
  async deleteMemory(memoryId: string): Promise<DeleteResponse> {
    return request<DeleteResponse>(`/v1/memories/${memoryId}/`, {
      method: "DELETE",
    });
  },

  /**
   * 删除用户的所有记忆
   * @param userId 用户 ID
   */
  async deleteAllMemories(userId: string): Promise<DeleteResponse> {
    return request<DeleteResponse>(`/v1/memories/?user_id=${userId}`, {
      method: "DELETE",
    });
  },

  // ============ 搜索 ============

  /**
   * 语义搜索记忆
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
    return request<MemoryHistory[]>(`/v1/memories/history/${memoryId}/`);
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
    return request<RelatedMemoriesResponse>(`/v1/memories/${memoryId}/related/?limit=${limit}`);
  },

  // ============ 访问日志 ============

  /**
   * 获取记忆的访问日志
   */
  async getAccessLogs(memoryId: string, limit: number = 20): Promise<AccessLogsResponse> {
    return request<AccessLogsResponse>(`/v1/memories/${memoryId}/access-logs/?limit=${limit}`);
  },

  // ============ 请求日志 ============

  /**
   * 获取请求日志列表
   */
  async getRequestLogs(params?: { request_type?: string; since?: string; limit?: number; offset?: number }): Promise<RequestLogsResponse> {
    const qs = new URLSearchParams();
    if (params?.request_type) qs.set("request_type", params.request_type);
    if (params?.since) qs.set("since", params.since);
    if (params?.limit) qs.set("limit", String(params.limit));
    if (params?.offset) qs.set("offset", String(params.offset));
    const q = qs.toString();
    return request<RequestLogsResponse>(`/v1/request-logs/${q ? `?${q}` : ""}`);
  },

  /**
   * 获取请求日志统计
   */
  async getRequestLogsStats(since?: string): Promise<RequestLogsStats> {
    const qs = since ? `?since=${encodeURIComponent(since)}` : "";
    return request<RequestLogsStats>(`/v1/request-logs/stats/${qs}`);
  },

  // ============ 健康检查 ============

  /**
   * 检查 API 连接状态
   */
  async healthCheck(): Promise<boolean> {
    try {
      const response = await fetch(`${API_BASE}/`, {
        method: "GET",
        signal: AbortSignal.timeout(5000),
      });
      return response.ok;
    } catch {
      return false;
    }
  },
};
