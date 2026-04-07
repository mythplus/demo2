"use client";

import { useQuery } from "@tanstack/react-query";
import { mem0Api } from "@/lib/api";
import type { Memory, StatsResponse } from "@/lib/api";

/**
 * 仪表盘数据 React Query Hook
 * - 自动缓存，30 秒内切换页面不会重复请求
 * - 窗口聚焦时自动刷新
 * - 每 60 秒自动轮询刷新
 */
export function useDashboardData(enabled: boolean) {
  // 记忆列表查询
  const memoriesQuery = useQuery<Memory[]>({
    queryKey: ["dashboard", "memories"],
    queryFn: async () => {
      const data = await mem0Api.getMemories();
      return Array.isArray(data) ? data : [];
    },
    enabled,
    refetchInterval: 60 * 1000, // 每 60 秒自动刷新
    staleTime: 30 * 1000, // 30 秒内视为新鲜
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

  const memories = memoriesQuery.data ?? [];
  const stats = statsQuery.data ?? null;
  const loading = memoriesQuery.isLoading || statsQuery.isLoading;
  const error = memoriesQuery.error?.message || statsQuery.error?.message || "";

  // 手动刷新（使两个查询同时失效并重新获取）
  const refetch = () => {
    memoriesQuery.refetch();
    statsQuery.refetch();
  };

  return { memories, stats, loading, error, refetch };
}
