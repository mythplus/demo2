"use client";

import { QueryClient } from "@tanstack/react-query";

/**
 * 全局 React Query 客户端（单例）
 * - staleTime: 数据在 30 秒内视为新鲜，不会重复请求
 * - refetchOnWindowFocus: 窗口聚焦时自动刷新
 * - retry: 失败最多重试 1 次
 */
let queryClient: QueryClient | null = null;

export function getQueryClient(): QueryClient {
  if (!queryClient) {
    queryClient = new QueryClient({
      defaultOptions: {
        queries: {
          staleTime: 30 * 1000, // 30 秒内数据视为新鲜
          refetchOnWindowFocus: true, // 窗口聚焦时自动刷新
          retry: 1, // 失败重试 1 次
          refetchOnMount: true,
        },
      },
    });
  }
  return queryClient;
}
