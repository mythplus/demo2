/**
 * API 类型定义测试
 * 验证类型导出的完整性
 */

describe("API Types", () => {
  it("应该导出所有必要的类型", async () => {
    const types = await import("@/lib/api/types");
    // 验证模块可以正常导入
    expect(types).toBeDefined();
  });

  it("应该导出 mem0Api 和类型", async () => {
    const api = await import("@/lib/api");
    expect(api.mem0Api).toBeDefined();
    expect(typeof api.mem0Api.addMemory).toBe("function");
    expect(typeof api.mem0Api.getMemories).toBe("function");
    expect(typeof api.mem0Api.searchMemories).toBe("function");
    expect(typeof api.mem0Api.deleteMemory).toBe("function");
    expect(typeof api.mem0Api.updateMemory).toBe("function");
    expect(typeof api.mem0Api.getStats).toBe("function");
    expect(typeof api.mem0Api.healthCheck).toBe("function");
    expect(typeof api.mem0Api.getGraphStats).toBe("function");
    expect(typeof api.mem0Api.getConfigInfo).toBe("function");
  });
});

describe("Data Transfer Utils", () => {
  it("应该导出导出工具函数", async () => {
    const mod = await import("@/lib/data-transfer");
    expect(typeof mod.exportToJSON).toBe("function");
    expect(typeof mod.exportToCSV).toBe("function");
  });
});
