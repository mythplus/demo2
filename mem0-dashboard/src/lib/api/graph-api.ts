/**
 * Mem0 API - 图谱记忆接口
 */

import type {
  GraphData,
  GraphEntitiesResponse,
  GraphRelationsResponse,
  GraphSearchRequest,
  GraphSearchResponse,
  GraphStatsResponse,
  GraphHealthResponse,
  DeleteResponse,
} from "./types";
import { request, buildQuery } from "./http-client";

export const graphApi = {
  /** 获取图谱统计信息 */
  async getGraphStats(): Promise<GraphStatsResponse> {
    return request<GraphStatsResponse>("/v1/graph/stats");
  },

  /** 获取实体列表 */
  async getGraphEntities(params?: {
    user_id?: string;
    search?: string;
    limit?: number;
    offset?: number;
  }): Promise<GraphEntitiesResponse> {
    return request<GraphEntitiesResponse>(
      `/v1/graph/entities${buildQuery(params ?? {})}`
    );
  },

  /** 获取关系三元组列表 */
  async getGraphRelations(params?: {
    user_id?: string;
    search?: string;
    limit?: number;
    offset?: number;
  }): Promise<GraphRelationsResponse> {
    return request<GraphRelationsResponse>(
      `/v1/graph/relations${buildQuery(params ?? {})}`
    );
  },

  /** 图谱搜索 */
  async searchGraph(data: GraphSearchRequest): Promise<GraphSearchResponse> {
    return request<GraphSearchResponse>("/v1/graph/search", {
      method: "POST",
      body: JSON.stringify(data),
    });
  },

  /** 获取指定用户的子图数据（用于可视化） */
  async getUserGraph(userId: string, limit?: number): Promise<GraphData> {
    const qs = limit ? `?limit=${limit}` : "";
    return request<GraphData>(`/v1/graph/user/${encodeURIComponent(userId)}${qs}`);
  },

  /** 获取全部图谱数据（用于可视化） */
  async getAllGraph(limit?: number): Promise<GraphData> {
    const qs = limit ? `?limit=${limit}` : "";
    return request<GraphData>(`/v1/graph/all${qs}`);
  },

  /** 删除实体及其关联关系 */
  async deleteGraphEntity(
    entityName: string,
    userId?: string
  ): Promise<DeleteResponse> {
    const qs = userId ? `?user_id=${encodeURIComponent(userId)}` : "";
    return request<DeleteResponse>(
      `/v1/graph/entities/${encodeURIComponent(entityName)}${qs}`,
      { method: "DELETE" }
    );
  },

  /** 删除指定关系 */
  async deleteGraphRelation(
    source: string,
    relation: string,
    target: string
  ): Promise<DeleteResponse> {
    const qs = new URLSearchParams({ source, relation, target }).toString();
    return request<DeleteResponse>(`/v1/graph/relations?${qs}`, {
      method: "DELETE",
    });
  },

  /** 检查 Neo4j 图数据库连接状态 */
  async graphHealthCheck(): Promise<GraphHealthResponse> {
    return request<GraphHealthResponse>("/v1/graph/health");
  },
};
