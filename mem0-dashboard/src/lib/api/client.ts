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
   * 添加记忆
   * @param data 包含消息列表和用户信息
   */
  async addMemory(data: AddMemoryRequest): Promise<AddMemoryResponse> {
    return request<AddMemoryResponse>("/v1/memories/", {
      method: "POST",
      body: JSON.stringify(data),
    });
  },

  /**
   * 获取所有记忆
   * @param userId 可选，按用户筛选
   */
  async getMemories(userId?: string): Promise<Memory[]> {
    const params = new URLSearchParams();
    if (userId) params.set("user_id", userId);
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
   * 更新记忆
   * @param memoryId 记忆 ID
   * @param data 新的记忆内容
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
