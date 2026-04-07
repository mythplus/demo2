/**
 * 连接状态 Store 集成测试 - 覆盖 useUIStore 的健康检查轮询逻辑
 */

// Mock mem0Api
jest.mock("@/lib/api/client", () => ({
  mem0Api: {
    healthCheck: jest.fn(),
  },
}));

beforeEach(() => {
  jest.useFakeTimers();
  jest.resetModules();
});

afterEach(() => {
  jest.useRealTimers();
});

describe("useUIStore - 连接状态管理", () => {
  it("初始连接状态应为 checking", async () => {
    const { useUIStore } = await import("@/store/ui-store");
    expect(useUIStore.getState().connectionStatus).toBe("checking");
  });

  it("checkConnection 成功时应设置为 connected", async () => {
    const { mem0Api } = await import("@/lib/api/client");
    (mem0Api.healthCheck as jest.Mock).mockResolvedValueOnce(true);

    const { useUIStore } = await import("@/store/ui-store");
    const result = await useUIStore.getState().checkConnection();

    expect(result).toBe(true);
    expect(useUIStore.getState().connectionStatus).toBe("connected");
  });

  it("checkConnection 失败时应设置为 disconnected", async () => {
    const { mem0Api } = await import("@/lib/api/client");
    (mem0Api.healthCheck as jest.Mock).mockResolvedValueOnce(false);

    const { useUIStore } = await import("@/store/ui-store");
    const result = await useUIStore.getState().checkConnection();

    expect(result).toBe(false);
    expect(useUIStore.getState().connectionStatus).toBe("disconnected");
  });

  it("setConnectionStatus 应直接更新状态", async () => {
    const { useUIStore } = await import("@/store/ui-store");
    useUIStore.getState().setConnectionStatus("connected");
    expect(useUIStore.getState().connectionStatus).toBe("connected");
    useUIStore.getState().setConnectionStatus("disconnected");
    expect(useUIStore.getState().connectionStatus).toBe("disconnected");
  });

  it("startHealthPolling 应立即执行一次检查", async () => {
    const { mem0Api } = await import("@/lib/api/client");
    (mem0Api.healthCheck as jest.Mock).mockResolvedValue(true);

    const { useUIStore } = await import("@/store/ui-store");
    const cleanup = useUIStore.getState().startHealthPolling(10000);

    expect(mem0Api.healthCheck).toHaveBeenCalledTimes(1);
    cleanup();
  });

  it("startHealthPolling 应按间隔定时检查", async () => {
    const { mem0Api } = await import("@/lib/api/client");
    (mem0Api.healthCheck as jest.Mock).mockResolvedValue(true);

    const { useUIStore } = await import("@/store/ui-store");
    const cleanup = useUIStore.getState().startHealthPolling(5000);

    // 初始调用 1 次
    expect(mem0Api.healthCheck).toHaveBeenCalledTimes(1);

    // 推进 5 秒，应再调用 1 次
    jest.advanceTimersByTime(5000);
    expect(mem0Api.healthCheck).toHaveBeenCalledTimes(2);

    // 推进 10 秒，应再调用 2 次
    jest.advanceTimersByTime(10000);
    expect(mem0Api.healthCheck).toHaveBeenCalledTimes(4);

    cleanup();
  });

  it("cleanup 后应停止轮询", async () => {
    const { mem0Api } = await import("@/lib/api/client");
    (mem0Api.healthCheck as jest.Mock).mockResolvedValue(true);

    const { useUIStore } = await import("@/store/ui-store");
    const cleanup = useUIStore.getState().startHealthPolling(5000);

    expect(mem0Api.healthCheck).toHaveBeenCalledTimes(1);

    cleanup();

    // cleanup 后推进时间，不应再调用
    jest.advanceTimersByTime(15000);
    expect(mem0Api.healthCheck).toHaveBeenCalledTimes(1);
  });
});

describe("useUIStore - 视图与面板状态", () => {
  beforeEach(() => {
    jest.resetModules();
  });

  it("应该切换视图模式", async () => {
    const { useUIStore } = await import("@/store/ui-store");
    expect(useUIStore.getState().viewMode).toBe("list");
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

  it("应该设置详情面板状态", async () => {
    const { useUIStore } = await import("@/store/ui-store");
    useUIStore.getState().setDetailPanelOpen(true);
    expect(useUIStore.getState().detailPanelOpen).toBe(true);
    useUIStore.getState().setDetailPanelOpen(false);
    expect(useUIStore.getState().detailPanelOpen).toBe(false);
  });
});
