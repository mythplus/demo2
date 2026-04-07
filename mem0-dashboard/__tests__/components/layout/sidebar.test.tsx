/**
 * 布局组件测试 - Sidebar
 */

import React from "react";
import { render, screen } from "@testing-library/react";
import "@testing-library/jest-dom";

// Mock lucide-react 图标
jest.mock("lucide-react", () => {
  const icons: Record<string, React.FC> = {};
  const iconNames = [
    "LayoutDashboard", "Brain", "Search", "Users", "Settings",
    "ChevronLeft", "ChevronRight", "Activity", "Database", "Network",
    "Moon", "Sun",
  ];
  iconNames.forEach((name) => {
    icons[name] = (props: Record<string, unknown>) =>
      React.createElement("svg", { "data-testid": `icon-${name}`, ...props });
  });
  return icons;
});

// Mock @/lib/utils
jest.mock("@/lib/utils", () => ({
  cn: (...inputs: string[]) => inputs.filter(Boolean).join(" "),
}));

// Mock Radix UI 组件
jest.mock("@/components/ui/button", () => ({
  Button: ({ children, ...props }: { children: React.ReactNode; [key: string]: unknown }) =>
    React.createElement("button", props, children),
}));

jest.mock("@/components/ui/tooltip", () => ({
  Tooltip: ({ children }: { children: React.ReactNode }) => React.createElement("div", null, children),
  TooltipContent: ({ children }: { children: React.ReactNode }) => React.createElement("div", null, children),
  TooltipTrigger: ({ children }: { children: React.ReactNode }) => React.createElement("div", null, children),
  TooltipProvider: ({ children }: { children: React.ReactNode }) => React.createElement("div", null, children),
}));

jest.mock("@/components/ui/separator", () => ({
  Separator: () => React.createElement("hr"),
}));

describe("Sidebar", () => {
  it("应该导出 Sidebar 组件", async () => {
    const mod = await import("@/components/layout/sidebar");
    expect(mod.Sidebar).toBeDefined();
    expect(typeof mod.Sidebar).toBe("function");
  });

  it("应该渲染导航菜单项", async () => {
    const { Sidebar } = await import("@/components/layout/sidebar");
    const { container } = render(
      React.createElement(Sidebar, { collapsed: false, onToggle: jest.fn() })
    );
    // 验证导航链接存在
    const links = container.querySelectorAll("a");
    expect(links.length).toBeGreaterThan(0);
  });

  it("折叠状态下应该有折叠样式", async () => {
    const { Sidebar } = await import("@/components/layout/sidebar");
    const { container } = render(
      React.createElement(Sidebar, { collapsed: true, onToggle: jest.fn() })
    );
    // 折叠状态下 aside 应该有 w-16 样式
    const aside = container.querySelector("aside");
    expect(aside?.className).toContain("w-16");
  });

  it("展开状态下应该显示文字", async () => {
    const { Sidebar } = await import("@/components/layout/sidebar");
    const { container } = render(
      React.createElement(Sidebar, { collapsed: false, onToggle: jest.fn() })
    );
    expect(container.textContent).toContain("记忆管理");
    expect(container.textContent).toContain("仪表盘");
  });
});
