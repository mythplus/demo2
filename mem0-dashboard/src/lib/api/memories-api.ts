/**
 * Mem0 API - 记忆 CRUD 接口
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
  RelatedMemoriesResponse,
  AccessLogsResponse,
  BatchImportRequest,
  BatchImportResponse,
  BatchDeleteResponse,
} from "./types";
import { request, buildQuery } from "./http-client";

export const memoriesApi = {
  /** 添加记忆（支持 categories 和 state） */
  async addMemory(data: AddMemoryRequest): Promise<AddMemoryResponse> {
    return request<AddMemoryResponse>("/v1/memories/", {
      method: "POST",
      body: JSON.stringify(data),
    });
  },

  /** 批量导入记忆 */
  async batchImport(data: BatchImportRequest): Promise<BatchImportResponse> {
    return request<BatchImportResponse>("/v1/memories/batch", {
      method: "POST",
      body: JSON.stringify(data),
    });
  },

  /** 获取所有记忆（支持多维筛选） */
  async getMemories(filters?: FilterParams | string): Promise<Memory[]> {
    const params: Record<string, string | string[] | undefined> = {};

    if (typeof filters === "string") {
      if (filters) params.user_id = filters;
    } else if (filters) {
      if (filters.user_id) params.user_id = filters.user_id;
      if (filters.categories && filters.categories.length > 0) {
        params.categories = filters.categories.join(",");
      }
      if (filters.state) params.state = filters.state;
      if (filters.date_from) params.date_from = filters.date_from;
      if (filters.date_to) params.date_to = filters.date_to;
      if (filters.search) params.search = filters.search;
    }

    return request<Memory[]>(`/v1/memories/${buildQuery(params)}`);
  },

  /** 获取单条记忆 */
  async getMemory(memoryId: string): Promise<Memory> {
    return request<Memory>(`/v1/memories/${encodeURIComponent(memoryId)}/`);
  },

  /** 更新记忆（支持 text、metadata、categories、state 更新） */
  async updateMemory(memoryId: string, data: UpdateMemoryRequest): Promise<Memory> {
    return request<Memory>(`/v1/memories/${encodeURIComponent(memoryId)}/`, {
      method: "PUT",
      body: JSON.stringify(data),
    });
  },

  /** 删除单条记忆 */
  async deleteMemory(memoryId: string): Promise<DeleteResponse> {
    return request<DeleteResponse>(`/v1/memories/${encodeURIComponent(memoryId)}/`, {
      method: "DELETE",
    });
  },

  /** 批量删除记忆 */
  async batchDeleteMemories(memoryIds: string[]): Promise<BatchDeleteResponse> {
    return request<BatchDeleteResponse>("/v1/memories/batch-delete", {
      method: "POST",
      body: JSON.stringify({ memory_ids: memoryIds }),
    });
  },

  /** 删除用户的所有记忆 */
  async deleteAllMemories(userId: string): Promise<DeleteResponse> {
    return request<DeleteResponse>(
      `/v1/memories/?user_id=${encodeURIComponent(userId)}`,
      { method: "DELETE" }
    );
  },

  /** 语义搜索记忆 */
  async searchMemories(data: SearchMemoryRequest): Promise<SearchMemoryResponse> {
    return request<SearchMemoryResponse>("/v1/memories/search/", {
      method: "POST",
      body: JSON.stringify(data),
    });
  },

  /** 获取记忆的修改历史 */
  async getMemoryHistory(memoryId: string): Promise<MemoryHistory[]> {
    return request<MemoryHistory[]>(
      `/v1/memories/history/${encodeURIComponent(memoryId)}/`
    );
  },

  /** 获取语义相关的记忆 */
  async getRelatedMemories(
    memoryId: string,
    limit: number = 5
  ): Promise<RelatedMemoriesResponse> {
    return request<RelatedMemoriesResponse>(
      `/v1/memories/${encodeURIComponent(memoryId)}/related/?limit=${limit}`
    );
  },

  /** 获取记忆的访问日志 */
  async getAccessLogs(
    memoryId: string,
    limit: number = 20
  ): Promise<AccessLogsResponse> {
    return request<AccessLogsResponse>(
      `/v1/memories/${encodeURIComponent(memoryId)}/access-logs/?limit=${limit}`
    );
  },

  /** 检查 API 连接状态 */
  async healthCheck(): Promise<boolean> {
    try {
      const data = await request<{ status: string }>("", { timeout: 5000 });
      return data.status === "ok";
    } catch {
      return false;
    }
  },
};
