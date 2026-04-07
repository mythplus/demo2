/**
 * 常量和工具函数测试
 */

import { getCategoryInfo, getStateInfo, CATEGORY_LIST, STATE_LIST } from "@/lib/constants";

describe("getCategoryInfo", () => {
  it("应该返回已知分类的信息", () => {
    const info = getCategoryInfo("work");
    expect(info).toBeDefined();
    expect(info?.label).toBe("工作");
    expect(info?.value).toBe("work");
  });

  it("应该返回所有 20 种分类", () => {
    expect(CATEGORY_LIST).toHaveLength(20);
  });

  it("每个分类应该有完整的颜色信息", () => {
    for (const cat of CATEGORY_LIST) {
      expect(cat.color).toBeTruthy();
      expect(cat.lightBg).toBeTruthy();
      expect(cat.lightText).toBeTruthy();
      expect(cat.darkBg).toBeTruthy();
      expect(cat.darkText).toBeTruthy();
    }
  });

  it("应该返回 undefined 对于未知分类", () => {
    const info = getCategoryInfo("unknown" as never);
    expect(info).toBeUndefined();
  });
});

describe("getStateInfo", () => {
  it("应该返回已知状态的信息", () => {
    const info = getStateInfo("active");
    expect(info).toBeDefined();
    expect(info?.label).toBe("活跃");
  });

  it("应该返回所有 3 种状态", () => {
    expect(STATE_LIST).toHaveLength(3);
  });

  it("应该包含 active、paused、deleted 三种状态", () => {
    const values = STATE_LIST.map((s) => s.value);
    expect(values).toContain("active");
    expect(values).toContain("paused");
    expect(values).toContain("deleted");
  });

  it("应该返回 undefined 对于未知状态", () => {
    const info = getStateInfo("unknown" as never);
    expect(info).toBeUndefined();
  });
});
