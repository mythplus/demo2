"use client";

import { Loader2 } from "lucide-react";

/**
 * 全局页面切换加载状态
 * Next.js App Router 会在页面导航时自动显示此组件
 */
export default function Loading() {
  return (
    <div className="flex h-[60vh] flex-col items-center justify-center gap-3">
      <Loader2 className="h-8 w-8 animate-spin text-primary" />
      <p className="text-sm text-muted-foreground">加载中...</p>
    </div>
  );
}
