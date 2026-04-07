/**
 * 记忆组件测试 - CategoryBadge, StateBadge
 */

import React from "react";
import { render } from "@testing-library/react";
import "@testing-library/jest-dom";

// Mock @/lib/utils
jest.mock("@/lib/utils", () => ({
  cn: (...inputs: string[]) => inputs.filter(Boolean).join(" "),
}));

// Mock Radix UI Tooltip
jest.mock("@/components/ui/tooltip", () => ({
  Tooltip: ({ children }: { children: React.ReactNode }) => React.createElement("div", null, children),
  TooltipContent: ({ children }: { children: React.ReactNode }) => React.createElement("div", null, children),
  TooltipTrigger: ({ children }: { children: React.ReactNode }) => React.createElement("div", null, children),
  TooltipProvider: ({ children }: { children: React.ReactNode }) => React.createElement("div", null, children),
}));

describe("CategoryBadge", () => {
  it("应该渲染已知分类的标签", async () => {
    const { CategoryBadge } = await import("@/components/memories/category-badge");
    const { container } = render(
      React.createElement(CategoryBadge, { category: "work" })
    );
    expect(container.textContent).toContain("工作");
  });

  it("应该对未知分类返回 null", async () => {
    const { CategoryBadge } = await import("@/components/memories/category-badge");
    const { container } = render(
      React.createElement(CategoryBadge, { category: "unknown" as never })
    );
    expect(container.innerHTML).toBe("");
  });
});

describe("CategoryBadges", () => {
  it("应该渲染多个分类标签", async () => {
    const { CategoryBadges } = await import("@/components/memories/category-badge");
    const { container } = render(
      React.createElement(CategoryBadges, { categories: ["work", "education", "health"] })
    );
    expect(container.textContent).toContain("工作");
    expect(container.textContent).toContain("教育");
    expect(container.textContent).toContain("健康");
  });

  it("应该限制显示数量并显示 +N", async () => {
    const { CategoryBadges } = await import("@/components/memories/category-badge");
    const { container } = render(
      React.createElement(CategoryBadges, {
        categories: ["work", "education", "health", "travel"],
        max: 2,
      })
    );
    expect(container.textContent).toContain("+2");
  });

  it("空分类列表应该返回 null", async () => {
    const { CategoryBadges } = await import("@/components/memories/category-badge");
    const { container } = render(
      React.createElement(CategoryBadges, { categories: [] })
    );
    expect(container.innerHTML).toBe("");
  });
});

describe("StateBadge", () => {
  it("应该渲染活跃状态", async () => {
    const { StateBadge } = await import("@/components/memories/state-badge");
    const { container } = render(
      React.createElement(StateBadge, { state: "active" })
    );
    expect(container.textContent).toContain("活跃");
  });

  it("应该渲染暂停状态", async () => {
    const { StateBadge } = await import("@/components/memories/state-badge");
    const { container } = render(
      React.createElement(StateBadge, { state: "paused" })
    );
    expect(container.textContent).toContain("暂停");
  });

  it("应该渲染已删除状态", async () => {
    const { StateBadge } = await import("@/components/memories/state-badge");
    const { container } = render(
      React.createElement(StateBadge, { state: "deleted" })
    );
    expect(container.textContent).toContain("已删除");
  });

  it("默认应该渲染活跃状态", async () => {
    const { StateBadge } = await import("@/components/memories/state-badge");
    const { container } = render(
      React.createElement(StateBadge, {})
    );
    expect(container.textContent).toContain("活跃");
  });
});
