"use client";

import React from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  LayoutDashboard,
  Brain,
  Search,
  Users,
  Settings,
  ChevronLeft,
  ChevronRight,
  Activity,
  Database,
  Network,
  MessageSquare,
  Webhook,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
  TooltipProvider,
} from "@/components/ui/tooltip";

// 导航菜单配置
const navItems = [
  { title: "仪表盘", href: "/", icon: LayoutDashboard },
{ title: "Playground", href: "/playground", icon: MessageSquare },
  { title: "记忆管理", href: "/memories", icon: Brain },
  { title: "语义检索", href: "/search", icon: Search },
  { title: "用户管理", href: "/users", icon: Users },
  { title: "请求日志", href: "/requests", icon: Activity },
  { title: "图谱记忆", href: "/graph-memory", icon: Network },
  { title: "数据导出", href: "/data-transfer", icon: Database },
  { title: "Webhooks", href: "/webhooks", icon: Webhook },
];

const bottomNavItems = [
  { title: "系统设置", href: "/settings", icon: Settings },
];

interface SidebarProps {
  collapsed: boolean;
  onToggle: () => void;
}

function NavLink({
  item,
  isActive,
  collapsed,
}: {
  item: (typeof navItems)[0];
  isActive: boolean;
  collapsed: boolean;
}) {
  const link = (
    <Link
      href={item.href}
      className={cn(
        "group flex items-center gap-3 rounded-lg px-3 py-2 text-[13px] font-medium transition-all duration-200",
        isActive
          ? "bg-primary/10 text-primary"
          : "text-muted-foreground hover:bg-muted hover:text-foreground",
        collapsed && "justify-center px-0 py-2.5"
      )}
    >
      <item.icon
        className={cn(
          "h-[18px] w-[18px] shrink-0 transition-colors duration-200",
          isActive ? "text-primary" : "text-muted-foreground group-hover:text-foreground"
        )}
      />
      {!collapsed && <span>{item.title}</span>}
    </Link>
  );

  if (collapsed) {
    return (
      <Tooltip>
        <TooltipTrigger asChild>{link}</TooltipTrigger>
        <TooltipContent side="right" sideOffset={8}>
          {item.title}
        </TooltipContent>
      </Tooltip>
    );
  }

  return link;
}

export function Sidebar({ collapsed, onToggle }: SidebarProps) {
  const pathname = usePathname();

  return (
    <TooltipProvider delayDuration={0}>
      <aside
        className={cn(
          "flex h-screen flex-col border-r bg-card transition-all duration-300",
          collapsed ? "w-[52px]" : "w-56"
        )}
      >
        {/* Logo */}
        <div className={cn(
          "flex h-12 items-center border-b",
          collapsed ? "justify-center" : "px-4"
        )}>
          <Link href="/" className="flex items-center gap-2.5">
            <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-primary text-primary-foreground">
              <Brain className="h-4 w-4" />
            </div>
            {!collapsed && (
              <span className="text-sm font-semibold tracking-tight">Mem0</span>
            )}
          </Link>
        </div>

        {/* 主导航 */}
        <nav className="flex-1 space-y-0.5 px-2 py-3">
          {navItems.map((item) => {
            const isActive =
              item.href === "/"
                ? pathname === "/"
                : pathname.startsWith(item.href);
            return (
              <NavLink
                key={item.href}
                item={item}
                isActive={isActive}
                collapsed={collapsed}
              />
            );
          })}
        </nav>

        {/* 底部导航 */}
        <div className="border-t px-2 py-2">
          {bottomNavItems.map((item) => {
            const isActive = pathname.startsWith(item.href);
            return (
              <NavLink
                key={item.href}
                item={item}
                isActive={isActive}
                collapsed={collapsed}
              />
            );
          })}
        </div>

        {/* 折叠按钮 */}
        <div className="border-t px-2 py-1.5">
          <Button
            variant="ghost"
            size="sm"
            className={cn(
              "h-8 w-full text-muted-foreground hover:text-foreground",
              collapsed ? "px-0" : "justify-start gap-2 px-3"
            )}
            onClick={onToggle}
          >
            {collapsed ? (
              <ChevronRight className="h-4 w-4" />
            ) : (
              <>
                <ChevronLeft className="h-4 w-4" />
                <span className="text-xs">收起</span>
              </>
            )}
          </Button>
        </div>
      </aside>
    </TooltipProvider>
  );
}
