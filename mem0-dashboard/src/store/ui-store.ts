/**
 * Zustand 全局状态管理 - UI 状态 + 连接状态 Store
 */
import { create } from "zustand";
import { mem0Api } from "@/lib/api/client";
import type { ConnectionStatus } from "@/lib/api/types";

export type ViewMode = "list" | "table";

const SIDEBAR_STORAGE_KEY = "mem0-sidebar-collapsed";
const VIEW_MODE_STORAGE_KEY = "mem0-view-mode";

interface UIState {
  hydrated: boolean;
  hydratePersistedState: () => void;

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
  hydrated: false,
  hydratePersistedState: () => {
    if (get().hydrated || typeof window === "undefined") {
      return;
    }

    const updates: Partial<UIState> = { hydrated: true };

    try {
      const savedSidebar = localStorage.getItem(SIDEBAR_STORAGE_KEY);
      if (savedSidebar === "true") {
        updates.sidebarCollapsed = true;
      }

      const savedViewMode = localStorage.getItem(VIEW_MODE_STORAGE_KEY);
      if (savedViewMode === "list" || savedViewMode === "table") {
        updates.viewMode = savedViewMode;
      }
    } catch {
      // 忽略持久化读取失败，继续使用默认值
    }

    set(updates);
  },

  viewMode: "table",
  setViewMode: (mode) => {
    if (typeof window !== "undefined") {
      localStorage.setItem(VIEW_MODE_STORAGE_KEY, mode);
    }
    set({ viewMode: mode });
  },

  sidebarCollapsed: false,
  toggleSidebar: () =>
    set((state) => {
      const nextCollapsed = !state.sidebarCollapsed;
      if (typeof window !== "undefined") {
        localStorage.setItem(SIDEBAR_STORAGE_KEY, String(nextCollapsed));
      }
      return { sidebarCollapsed: nextCollapsed };
    }),
  setSidebarCollapsed: (collapsed) => {
    if (typeof window !== "undefined") {
      localStorage.setItem(SIDEBAR_STORAGE_KEY, String(collapsed));
    }
    set({ sidebarCollapsed: collapsed });
  },

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
    void get().checkConnection();

    pollingRefCount++;
    if (pollingRefCount === 1) {
      pollingTimer = setInterval(() => {
        void get().checkConnection();
      }, intervalMs);
    }

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
