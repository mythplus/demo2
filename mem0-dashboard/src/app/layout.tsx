"use client";

import React, { useState, useEffect } from "react";
import { Inter } from "next/font/google";
import { Sidebar } from "@/components/layout/sidebar";
import { Header } from "@/components/layout/header";
import { usePreferences } from "@/hooks/use-preferences";
import "./globals.css";

const inter = Inter({ subsets: ["latin"] });

/**
 * 根据主题模式和系统偏好，计算实际是否应用深色
 */
function resolveTheme(
  themeMode: "light" | "dark" | "system",
  systemPrefersDark: boolean
): boolean {
  if (themeMode === "dark") return true;
  if (themeMode === "light") return false;
  return systemPrefersDark; // system 模式跟随系统
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const { preferences, loaded, savePreferences } = usePreferences();

  // 系统深色偏好检测
  const [systemPrefersDark, setSystemPrefersDark] = useState(false);

  // 监听系统主题偏好变化
  useEffect(() => {
    const mediaQuery = window.matchMedia("(prefers-color-scheme: dark)");
    setSystemPrefersDark(mediaQuery.matches);

    const handler = (e: MediaQueryListEvent) => {
      setSystemPrefersDark(e.matches);
    };
    mediaQuery.addEventListener("change", handler);
    return () => mediaQuery.removeEventListener("change", handler);
  }, []);

  // 根据主题模式应用 dark class
  useEffect(() => {
    if (!loaded) return;
    const isDark = resolveTheme(preferences.themeMode, systemPrefersDark);
    if (isDark) {
      document.documentElement.classList.add("dark");
    } else {
      document.documentElement.classList.remove("dark");
    }
  }, [preferences.themeMode, systemPrefersDark, loaded]);

  // 从 localStorage 恢复侧边栏状态
  useEffect(() => {
    const savedCollapsed = localStorage.getItem("mem0-sidebar-collapsed");
    if (savedCollapsed === "true") setSidebarCollapsed(true);
  }, []);

  // 保存侧边栏状态
  useEffect(() => {
    localStorage.setItem("mem0-sidebar-collapsed", String(sidebarCollapsed));
  }, [sidebarCollapsed]);

  // 主题模式切换（在 header 中循环切换：light -> dark -> system -> light）
  const handleCycleTheme = () => {
    const order: Array<"light" | "dark" | "system"> = [
      "light",
      "dark",
      "system",
    ];
    const currentIndex = order.indexOf(preferences.themeMode);
    const nextMode = order[(currentIndex + 1) % order.length];
    savePreferences({ themeMode: nextMode });
  };

  return (
    <html lang="zh-CN" suppressHydrationWarning>
      <body className={inter.className}>
        <div className="flex h-screen overflow-hidden">
          {/* 侧边栏 */}
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

            {/* 页面内容 */}
            <main className="flex-1 overflow-y-auto p-6">{children}</main>
          </div>
        </div>
      </body>
    </html>
  );
}
