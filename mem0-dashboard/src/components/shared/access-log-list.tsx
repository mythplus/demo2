"use client";

import React, { useEffect, useState } from "react";
import { Clock, Eye, Search, Pencil, ScrollText } from "lucide-react";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { mem0Api } from "@/lib/api";
import type { AccessLog } from "@/lib/api";

const ACTION_CONFIG = {
  view: { label: "查看", icon: Eye, color: "text-blue-600 dark:text-blue-400" },
  search: { label: "搜索", icon: Search, color: "text-green-600 dark:text-green-400" },
  edit: { label: "编辑", icon: Pencil, color: "text-orange-600 dark:text-orange-400" },
} as const;

interface AccessLogListProps {
  memoryId: string;
  className?: string;
}

export function AccessLogList({ memoryId, className }: AccessLogListProps) {
  const [logs, setLogs] = useState<AccessLog[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    mem0Api
      .getAccessLogs(memoryId, 10)
      .then((res) => {
        if (!cancelled) setLogs(res.logs || []);
      })
      .catch(() => {
        if (!cancelled) setLogs([]);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => { cancelled = true; };
  }, [memoryId]);

  return (
    <Card className={className}>
      <CardHeader className="px-4 py-3">
        <CardTitle className="flex items-center gap-2 text-base">
          <ScrollText className="h-4 w-4" />
          访问日志
        </CardTitle>
        <CardDescription>记录该记忆的访问历史</CardDescription>
      </CardHeader>
      <CardContent className="px-4 pb-3 pt-0">
        {loading ? (
          <div className="space-y-2">
            {[1, 2, 3].map((i) => (
              <div key={i} className="h-10 animate-pulse rounded bg-muted" />
            ))}
          </div>
        ) : logs.length > 0 ? (
          <div className="space-y-1 max-h-[400px] overflow-y-auto">
            {logs.map((log) => {
              const config = ACTION_CONFIG[log.action as keyof typeof ACTION_CONFIG] || ACTION_CONFIG.view;
              const ActionIcon = config.icon;
              return (
                <div
                  key={log.id}
                  className="flex items-center gap-3 rounded-md px-2 py-1.5 text-sm hover:bg-muted/50"
                >
                  <ActionIcon className={`h-3.5 w-3.5 shrink-0 ${config.color}`} />
                  <span className={`text-xs font-medium ${config.color} w-8`}>
                    {config.label}
                  </span>
                  {log.memory_preview && (
                    <span className="flex-1 truncate text-xs text-muted-foreground">
                      {log.memory_preview}
                    </span>
                  )}
                  <span className="shrink-0 text-xs text-muted-foreground">
                    <Clock className="mr-1 inline h-3 w-3" />
                    {new Date(log.timestamp).toLocaleString("zh-CN", {
                      month: "2-digit",
                      day: "2-digit",
                      hour: "2-digit",
                      minute: "2-digit",
                    })}
                  </span>
                </div>
              );
            })}
          </div>
        ) : (
          <div className="flex flex-col items-center justify-center py-3 text-center">
            <ScrollText className="mb-2 h-8 w-8 text-muted-foreground/30" />
            <p className="text-sm text-muted-foreground">暂无访问记录</p>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
