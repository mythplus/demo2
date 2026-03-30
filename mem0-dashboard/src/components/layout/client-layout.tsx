"use client";

import React, { useState, useEffect } from "react";
import { Sidebar } from "@/components/layout/sidebar";
import { Header } from "@/components/layout/header";
import { usePreferences } from "@/hooks/use-preferences";

/**
 * 根据主题模式计算实际是否应用深色
 */
function resolveTheme(themeMode: "light" | "dark"): boolean {
  return themeMode === "dark";
}

export function ClientLayout({ children }: { children: React.ReactNode }) {
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const { preferences, loaded, savePreferences } = usePreferences();

  // 根据主题模式应用 dark class
  useEffect(() => {
    if (!loaded) return;
    const isDark = resolveTheme(preferences.themeMode);
    if (isDark) {
      document.documentElement.classList.add("dark");
    } else {
      document.documentElement.classList.remove("dark");
    }
  }, [preferences.themeMode, loaded]);

  // 从 localStorage 恢复侧边栏状态
  useEffect(() => {
    const savedCollapsed = localStorage.getItem("mem0-sidebar-collapsed");
    if (savedCollapsed === "true") setSidebarCollapsed(true);
  }, []);

  // 保存侧边栏状态
  useEffect(() => {
    localStorage.setItem("mem0-sidebar-collapsed", String(sidebarCollapsed));
  }, [sidebarCollapsed]);

  // 窗口宽度变小时自动收起侧边栏，变大时自动展开
  useEffect(() => {
    const mql = window.matchMedia("(max-width: 768px)");
    const handleChange = (e: MediaQueryListEvent | MediaQueryList) => {
      setSidebarCollapsed(e.matches);
    };
    // 初始化
    handleChange(mql);
    mql.addEventListener("change", handleChange);
    return () => mql.removeEventListener("change", handleChange);
  }, []);

  // 主题模式切换（在 header 中切换：light <-> dark）
  const handleCycleTheme = () => {
    const nextMode = preferences.themeMode === "light" ? "dark" : "light";
    savePreferences({ themeMode: nextMode });
  };

  return (
    <div className="flex h-screen overflow-hidden">
      {/* 侧边栏 - 始终显示，窄屏自动收起 */}
      <Sidebar
        collapsed={sidebarCollapsed}
        onToggle={() => setSidebarCollapsed(!sidebarCollapsed)}
      />

      {/* 主内容区域 */}
      <div className="flex flex-1 flex-col overflow-hidden">
        {/* 顶部栏 */}
        <Header
          themeMode={preferences.themeMode}
          onCycleTheme={handleCycleTheme}
        />

        {/* 页面内容 - 响应式 padding */}
        <main className="flex-1 overflow-y-auto p-3 sm:p-4 md:p-6">
          {children}
        </main>
      </div>
    </div>
  );
}
