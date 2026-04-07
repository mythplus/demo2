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
});

describe("useMemoriesStore", () => {
  beforeEach(() => {
    jest.resetModules();
  });

  it("应该有正确的初始状态", async () => {
    const { useMemoriesStore } = await import("@/store/memories-store");
    const state = useMemoriesStore.getState();
    expect(state.memories).toEqual([]);
    expect(state.stats).toBeNull();
    expect(state.loading).toBe(false);
    expect(state.error).toBe("");
    expect(state.filters).toEqual({});
  });

  it("应该设置筛选条件", async () => {
    const { useMemoriesStore } = await import("@/store/memories-store");
    useMemoriesStore.getState().setFilters({ user_id: "user1", state: "active" });
    expect(useMemoriesStore.getState().filters).toEqual({ user_id: "user1", state: "active" });
  });

  it("应该重置筛选条件", async () => {
    const { useMemoriesStore } = await import("@/store/memories-store");
    useMemoriesStore.getState().setFilters({ user_id: "user1" });
    useMemoriesStore.getState().resetFilters();
    expect(useMemoriesStore.getState().filters).toEqual({});
  });
});
