/**
 * Zustand Store 测试
 */

describe("useUIStore", () => {
  beforeEach(() => {
    jest.resetModules();
  });

  it("应该有正确的初始状态", async () => {
    const { useUIStore } = await import("@/store/ui-store");
    const state = useUIStore.getState();
    expect(state.viewMode).toBe("list");
    expect(state.sidebarCollapsed).toBe(false);
    expect(state.detailPanelOpen).toBe(false);
    expect(state.connectionStatus).toBe("checking");
  });

  it("应该切换视图模式", async () => {
    const { useUIStore } = await import("@/store/ui-store");
    useUIStore.getState().setViewMode("table");
    expect(useUIStore.getState().viewMode).toBe("table");
  });

  it("应该切换侧边栏折叠状态", async () => {
    const { useUIStore } = await import("@/store/ui-store");
    expect(useUIStore.getState().sidebarCollapsed).toBe(false);
    useUIStore.getState().toggleSidebar();
    expect(useUIStore.getState().sidebarCollapsed).toBe(true);
    useUIStore.getState().toggleSidebar();
    expect(useUIStore.getState().sidebarCollapsed).toBe(false);
  });

  it("应该设置侧边栏折叠状态", async () => {
    const { useUIStore } = await import("@/store/ui-store");
    useUIStore.getState().setSidebarCollapsed(true);
    expect(useUIStore.getState().sidebarCollapsed).toBe(true);
  });

  it("应该设置详情面板状态", async () => {
    const { useUIStore } = await import("@/store/ui-store");
    useUIStore.getState().setDetailPanelOpen(true);
    expect(useUIStore.getState().detailPanelOpen).toBe(true);
  });

  it("应该设置连接状态", async () => {
    const { useUIStore } = await import("@/store/ui-store");
    useUIStore.getState().setConnectionStatus("connected");
    expect(useUIStore.getState().connectionStatus).toBe("connected");
    useUIStore.getState().setConnectionStatus("disconnected");
    expect(useUIStore.getState().connectionStatus).toBe("disconnected");
  });
});
