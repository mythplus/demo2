"use client";

import React, { useEffect, useState } from "react";
import { usePathname } from "next/navigation";
import { Moon, Sun } from "lucide-react";
import { Button } from "@/components/ui/button";
import { mem0Api } from "@/lib/api";
import type { ConnectionStatus } from "@/lib/api";

// 路径到标题的映射
const pageTitles: Record<string, string> = {
"/": "仪表盘",
  "/memories": "记忆管理",
  "/search": "语义搜索",
  "/users": "用户管理",
"/requests": "请求日志",
"/data-transfer": "数据导出",
  "/settings": "系统设置",
};

function getPageTitle(pathname: string): string {
  if (pageTitles[pathname]) return pageTitles[pathname];
  if (pathname.startsWith("/memory/")) return "记忆详情";
  if (pathname.startsWith("/users/")) return "用户详情";
  return "mem0-dashboard";
}

interface HeaderProps {
  themeMode: "light" | "dark";
  onCycleTheme: () => void;
}

// 主题模式图标和提示
const themeMeta: Record<
  "light" | "dark",
  { icon: React.ElementType; label: string }
> = {
  light: { icon: Sun, label: "浅色模式" },
  dark: { icon: Moon, label: "深色模式" },
};

export function Header({ themeMode, onCycleTheme }: HeaderProps) {
  const pathname = usePathname();
  const title = getPageTitle(pathname);

  const [connectionStatus, setConnectionStatus] =
    useState<ConnectionStatus>("checking");

  // 定期检查连接状态
  useEffect(() => {
    const checkConnection = async () => {
      const isConnected = await mem0Api.healthCheck();
      setConnectionStatus(isConnected ? "connected" : "disconnected");
    };

    checkConnection();
    const interval = setInterval(checkConnection, 30000); // 每 30 秒检查一次
    return () => clearInterval(interval);
  }, []);

  const ThemeIcon = themeMeta[themeMode].icon;
  const themeLabel = themeMeta[themeMode].label;

  return (
    <header className="flex h-14 items-center justify-between border-b bg-background px-6">
      {/* 页面标题 */}
      <div>
        <h1 className="text-lg font-semibold">{title}</h1>
      </div>

      {/* 右侧操作区 */}
      <div className="flex items-center gap-2">
        {/* 主题模式切换（循环：浅色 → 深色 → 跟随系统） */}
        <Button
          variant="ghost"
          size="icon"
          onClick={onCycleTheme}
          title={themeLabel}
        >
          <ThemeIcon className="h-5 w-5" />
        </Button>

        {/* 连接状态指示器 */}
        <div className="flex items-center gap-2 rounded-full border px-3 py-1 text-xs">
          <div
            className={`h-2 w-2 rounded-full ${
              connectionStatus === "connected"
                ? "bg-green-500"
                : connectionStatus === "checking"
                ? "bg-yellow-500 animate-pulse"
                : "bg-red-500"
            }`}
          />
          <span className="text-muted-foreground">
            {connectionStatus === "connected"
              ? "API 已连接"
              : connectionStatus === "checking"
              ? "检查中..."
              : "API 离线"}
          </span>
        </div>
      </div>
    </header>
  );
}
