/**
 * Zustand 全局状态管理 - UI 状态 + 连接状态 Store
 */
import { create } from "zustand";
import { mem0Api } from "@/lib/api/client";
import type { ConnectionStatus } from "@/lib/api/types";

export type ViewMode = "list" | "table";

interface UIState {
  // 视图模式
  viewMode: ViewMode;
  setViewMode: (mode: ViewMode) => void;

  // 侧边栏
  sidebarCollapsed: boolean;
  toggleSidebar: () => void;
  setSidebarCollapsed: (collapsed: boolean) => void;

  // 详情面板
  detailPanelOpen: boolean;
  setDetailPanelOpen: (open: boolean) => void;

  // 全局 API 连接状态（Header 和仪表盘共用，避免重复轮询）
  connectionStatus: ConnectionStatus;
  setConnectionStatus: (status: ConnectionStatus) => void;
  checkConnection: () => Promise<boolean>;
  /** 启动定时健康检查（返回清理函数） */
  startHealthPolling: (intervalMs?: number) => () => void;
}

// 轮询引用计数，确保多个组件共享同一个定时器
let pollingRefCount = 0;
let pollingTimer: ReturnType<typeof setInterval> | null = null;

export const useUIStore = create<UIState>((set, get) => ({
  viewMode: "list",
  setViewMode: (mode) => set({ viewMode: mode }),

  sidebarCollapsed: false,
  toggleSidebar: () => set((s) => ({ sidebarCollapsed: !s.sidebarCollapsed })),
  setSidebarCollapsed: (collapsed) => set({ sidebarCollapsed: collapsed }),

  detailPanelOpen: false,
  setDetailPanelOpen: (open) => set({ detailPanelOpen: open }),

  connectionStatus: "checking",
  setConnectionStatus: (status) => set({ connectionStatus: status }),

  checkConnection: async () => {
    const isConnected = await mem0Api.healthCheck();
    set({ connectionStatus: isConnected ? "connected" : "disconnected" });
    return isConnected;
  },

  startHealthPolling: (intervalMs = 30000) => {
    // 首次立即检查
    get().checkConnection();

    pollingRefCount++;
    // 只有第一个订阅者创建定时器
    if (pollingRefCount === 1) {
      pollingTimer = setInterval(() => {
        get().checkConnection();
      }, intervalMs);
    }

    // 返回清理函数
    return () => {
      pollingRefCount--;
      if (pollingRefCount <= 0 && pollingTimer) {
        clearInterval(pollingTimer);
        pollingTimer = null;
        pollingRefCount = 0;
      }
    };
  },
}));
