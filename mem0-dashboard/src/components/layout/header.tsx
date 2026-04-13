"use client";

import React from "react";
import { usePathname } from "next/navigation";
import { Moon, Sun } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useUIStore } from "@/store";

// 路径到标题的映射
const pageTitles: Record<string, string> = {
  "/": "仪表盘",
  "/memories": "记忆管理",
  "/search": "语义检索",
  "/users": "用户管理",
  "/requests": "请求日志",
  "/data-transfer": "数据导出",
  "/graph-memory": "图谱记忆",
  "/settings": "系统设置",
"/playground": "Playground",
  "/webhooks": "Webhooks",
};

function getPageTitle(pathname: string): string {
  if (pageTitles[pathname]) return pageTitles[pathname];
  if (pathname.startsWith("/memory/")) return "记忆详情";
  if (pathname.startsWith("/users/")) return "用户详情";
  return "Mem0 Dashboard";
}

interface HeaderProps {
  themeMode: "light" | "dark";
  onCycleTheme: () => void;
}

export function Header({ themeMode, onCycleTheme }: HeaderProps) {
  const pathname = usePathname();
  const title = getPageTitle(pathname);
  const connectionStatus = useUIStore((s) => s.connectionStatus);

  return (
    <header className="flex h-12 items-center justify-between border-b bg-card/80 backdrop-blur-sm px-6">
      {/* 页面标题 */}
      <h1 className="text-sm font-medium text-foreground">{title}</h1>

      {/* 右侧操作区 */}
      <div className="flex items-center gap-3">
        {/* 连接状态 */}
        <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
          <div
            className={`h-1.5 w-1.5 rounded-full ${
              connectionStatus === "connected"
                ? "bg-emerald-500"
                : connectionStatus === "checking"
                ? "bg-amber-500 animate-pulse"
                : "bg-red-500"
            }`}
          />
          <span>
            {connectionStatus === "connected"
              ? "已连接"
              : connectionStatus === "checking"
              ? "连接中"
              : "离线"}
          </span>
        </div>

        {/* 分隔 */}
        <div className="h-4 w-px bg-border" />

        {/* 主题切换 */}
        <Button
          variant="ghost"
          size="icon"
          className="h-8 w-8 text-muted-foreground hover:text-foreground"
          onClick={onCycleTheme}
          title={themeMode === "light" ? "切换到深色模式" : "切换到浅色模式"}
        >
          {themeMode === "light" ? (
            <Sun className="h-4 w-4" />
          ) : (
            <Moon className="h-4 w-4" />
          )}
        </Button>
      </div>
    </header>
  );
}
