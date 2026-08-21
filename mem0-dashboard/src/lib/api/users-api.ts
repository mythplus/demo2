/**
 * Mem0 API - 用户管理接口
 */

import type { Memory, FilterParams } from "./types";
import { request, buildQuery } from "./http-client";

export interface UserListResponse {
  users: Array<{
    user_id: string;
    memory_count: number;
    active_count: number;
    paused_count: number;
    deleted_count: number;
    last_active: string;
  }>;
  total: number;
  limit: number;
  offset: number;
}

export interface UserDetailResponse {
  user_id: string;
  total_memories: number;
  active_count: number;
  paused_count: number;
  deleted_count: number;
  category_distribution: Record<string, number>;
  last_active: string;
}

export const usersApi = {
  /** 获取用户列表 */
  async getUsers(params?: {
    search?: string;
    limit?: number;
    offset?: number;
  }): Promise<UserListResponse> {
    return request<UserListResponse>(
      `/v1/users/${buildQuery(params ?? {})}`
    );
  },

  /** 获取用户详情 */
  async getUserDetail(userId: string): Promise<UserDetailResponse> {
    return request<UserDetailResponse>(`/v1/users/${encodeURIComponent(userId)}/`);
  },

  /** 获取用户的所有记忆 */
  async getUserMemories(
    userId: string,
    params?: {
      categories?: string;
      state?: string;
      search?: string;
      limit?: number;
      offset?: number;
    }
  ): Promise<{ memories: Memory[]; total: number; limit: number; offset: number }> {
    return request(
      `/v1/users/${encodeURIComponent(userId)}/memories/${buildQuery(params ?? {})}`
    );
  },
};
