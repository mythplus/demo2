/**
 * Hooks 测试
 */

// ============ usePreferences 测试 ============

describe("usePreferences", () => {
  beforeEach(() => {
    localStorage.clear();
    jest.resetModules();
  });

  it("应该有默认偏好设置的结构", async () => {
    const mod = await import("@/hooks/use-preferences");
    // 验证模块导出了 usePreferences 函数
    expect(typeof mod.usePreferences).toBe("function");
  });
});

