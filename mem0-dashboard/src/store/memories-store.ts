/**
 * Zustand 全局状态管理 - 记忆数据 Store
 */
import { create } from "zustand";
import type { Memory, FilterParams, StatsResponse } from "@/lib/api/types";
import { mem0Api } from "@/lib/api/client";

interface MemoriesState {
  // 数据
  memories: Memory[];
  stats: StatsResponse | null;
  loading: boolean;
  error: string;

  // 筛选
  filters: FilterParams;

  // 操作
  fetchMemories: () => Promise<void>;
  fetchStats: () => Promise<void>;
  setFilters: (filters: FilterParams) => void;
  resetFilters: () => void;
  invalidate: () => void;
}

export const useMemoriesStore = create<MemoriesState>((set, get) => ({
  memories: [],
  stats: null,
  loading: false,
  error: "",
  filters: {},

  fetchMemories: async () => {
    set({ loading: true, error: "" });
    try {
      const data = await mem0Api.getMemories(get().filters);
      set({ memories: Array.isArray(data) ? data : [], loading: false });
    } catch (err) {
      set({
        error: err instanceof Error ? err.message : "获取记忆列表失败",
        memories: [],
        loading: false,
      });
    }
  },

  fetchStats: async () => {
    try {
      const stats = await mem0Api.getStats();
      set({ stats });
    } catch {
      // 统计失败不阻塞
    }
  },

  setFilters: (filters: FilterParams) => {
    set({ filters });
  },

  resetFilters: () => {
    set({ filters: {} });
  },

  invalidate: () => {
    // 标记数据需要刷新，下次 fetchMemories 时重新加载
    get().fetchMemories();
    get().fetchStats();
  },
}));
