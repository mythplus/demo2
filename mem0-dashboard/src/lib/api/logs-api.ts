/**
 * Mem0 API - 日志与统计接口
 */

import type {
  StatsResponse,
  RequestLogsResponse,
  RequestLogsStats,
} from "./types";
import { request, buildQuery } from "./http-client";

export const logsApi = {
  /** 获取统计数据（分类分布、状态分布、每日趋势） */
  async getStats(): Promise<StatsResponse> {
    return request<StatsResponse>("/v1/stats/");
  },

  /** 获取请求日志列表 */
  async getRequestLogs(params?: {
    request_type?: string;
    since?: string;
    until?: string;
    limit?: number;
    offset?: number;
  }): Promise<RequestLogsResponse> {
    return request<RequestLogsResponse>(
      `/v1/request-logs/${buildQuery(params ?? {})}`
    );
  },

  /** 获取请求日志统计 */
  async getRequestLogsStats(
    since?: string,
    until?: string
  ): Promise<RequestLogsStats> {
    return request<RequestLogsStats>(
      `/v1/request-logs/stats/${buildQuery({ since, until })}`
    );
  },
};
