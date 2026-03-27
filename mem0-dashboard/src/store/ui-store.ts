/**
 * Zustand 全局状态管理 - UI 状态 Store
 */
import { create } from "zustand";

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
}

export const useUIStore = create<UIState>((set) => ({
  viewMode: "list",
  setViewMode: (mode) => set({ viewMode: mode }),

  sidebarCollapsed: false,
  toggleSidebar: () => set((s) => ({ sidebarCollapsed: !s.sidebarCollapsed })),
  setSidebarCollapsed: (collapsed) => set({ sidebarCollapsed: collapsed }),

  detailPanelOpen: false,
  setDetailPanelOpen: (open) => set({ detailPanelOpen: open }),
}));
