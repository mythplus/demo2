"use client";

import { useQuery } from "@tanstack/react-query";
import { mem0Api } from "@/lib/api";
import type { MemorySummaryResponse, StatsResponse, RequestLogsStats } from "@/lib/api";

/**
 * 仪表盘数据 React Query Hook
 * - 自动缓存，30 秒内切换页面不会重复请求
 * - 窗口聚焦时自动刷新
 * - 每 60 秒自动轮询刷新
 */
export function useDashboardData(enabled: boolean) {
  // 首页摘要查询（最近记忆 + 活跃用户）
  const summaryQuery = useQuery<MemorySummaryResponse | null>({
    queryKey: ["dashboard", "summary"],
    queryFn: async () => {
      try {
        return await mem0Api.getMemorySummary({ recent_limit: 5, top_users_limit: 10 });
      } catch {
        return null;
      }
    },
    enabled,
    refetchInterval: 60 * 1000,
    staleTime: 30 * 1000,
  });

  // 统计数据查询
  const statsQuery = useQuery<StatsResponse | null>({
    queryKey: ["dashboard", "stats"],
    queryFn: async () => {
      try {
        return await mem0Api.getStats();
      } catch {
        return null;
      }
    },
    enabled,
    refetchInterval: 60 * 1000,
    staleTime: 30 * 1000,
  });

  // 请求日志统计查询（用于仪表盘请求趋势图）
  const requestStatsQuery = useQuery<RequestLogsStats | null>({
    queryKey: ["dashboard", "requestStats"],
    queryFn: async () => {
      try {
        return await mem0Api.getRequestLogsStats();
      } catch {
        return null;
      }
    },
    enabled,
    refetchInterval: 60 * 1000,
    staleTime: 30 * 1000,
  });

  const summary = summaryQuery.data ?? null;
  const stats = statsQuery.data ?? null;
  const requestStats = requestStatsQuery.data ?? null;
  const loading = summaryQuery.isLoading || statsQuery.isLoading;
  const error = summaryQuery.error?.message || statsQuery.error?.message || "";

  // 手动刷新（使所有查询同时失效并重新获取）
  const refetch = () => {
    summaryQuery.refetch();
    statsQuery.refetch();
    requestStatsQuery.refetch();
  };

  return { summary, stats, requestStats, loading, error, refetch };
}
