"use client";

import { useEffect } from "react";
import { AlertTriangle, RotateCcw, Home } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";

export default function GlobalError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    // 生产环境可对接错误上报服务（如 Sentry）
    console.error("页面渲染错误:", error);
  }, [error]);

  return (
    <div className="flex min-h-[60vh] items-center justify-center p-6">
      <Card className="w-full max-w-md border-destructive/50">
        <CardContent className="flex flex-col items-center gap-4 pt-8 pb-6 text-center">
          <div className="flex h-16 w-16 items-center justify-center rounded-full bg-destructive/10">
            <AlertTriangle className="h-8 w-8 text-destructive" />
          </div>
          <div className="space-y-2">
            <h2 className="text-xl font-semibold">页面出错了</h2>
            <p className="text-sm text-muted-foreground">
              抱歉，页面渲染时发生了意外错误。您可以尝试重新加载页面。
            </p>
            {error?.message && (
              <p className="mt-2 rounded-md bg-muted px-3 py-2 text-xs font-mono text-muted-foreground break-all">
                {error.message}
              </p>
            )}
          </div>
          <div className="flex gap-3 mt-2">
            <Button variant="outline" onClick={() => (window.location.href = "/")}>
              <Home className="mr-2 h-4 w-4" />
              返回首页
            </Button>
            <Button onClick={reset}>
              <RotateCcw className="mr-2 h-4 w-4" />
              重试
            </Button>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
