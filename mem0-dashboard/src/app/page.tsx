"use client";

import React, { useState } from "react";
import Link from "next/link";
import {
  Brain,
  Users,
  TrendingUp,
  Activity,
  ArrowRight,
  Clock,
} from "lucide-react";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { AddMemoryDialog } from "@/components/memories/add-memory-dialog";
import { CategoryBadges } from "@/components/memories/category-badge";
import { StateBadge } from "@/components/memories/state-badge";
import { useUIStore } from "@/store";
import { useDashboardData } from "@/hooks/use-dashboard-data";
import { StatsCharts } from "@/components/dashboard/stats-charts";
import { StatsCardSkeleton } from "@/components/ui/skeleton";

// 统计卡片组件
function StatsCard({
  title,
  value,
  description,
  icon: Icon,
  trend,
}: {
  title: string;
  value: string | number;
  description: string;
  icon: React.ElementType;
  trend?: string;
}) {
  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
        <CardTitle className="text-sm font-medium">{title}</CardTitle>
        <Icon className="h-4 w-4 text-muted-foreground" />
      </CardHeader>
      <CardContent>
        {trend ? (
          <div className="text-2xl font-bold text-green-600 dark:text-green-400">{trend}</div>
        ) : (
          <div className="text-2xl font-bold">{value}</div>
        )}
        <p className="text-xs text-muted-foreground">
          {description}
        </p>
      </CardContent>
    </Card>
  );
}

export default function DashboardPage() {
  const [addDialogOpen, setAddDialogOpen] = useState(false);

  // 使用全局 Store 的连接状态（由 ClientLayout 统一轮询）
  const connectionStatus = useUIStore((s) => s.connectionStatus);

  // 使用 React Query 管理仪表盘数据（自动缓存 + 60 秒轮询 + 窗口聚焦刷新）
  const { memories, stats, loading, refetch } = useDashboardData(
    connectionStatus === "connected"
  );

  // 排除已删除记忆，仪表盘只展示活跃记忆数据
  const activeMemories = memories.filter((m) => m.state !== "deleted");

  // 统计数据
  const totalMemories = stats?.total_memories ?? activeMemories.length;
  const uniqueUserCount = stats?.total_users ?? new Set(activeMemories.map((m) => m.user_id).filter(Boolean)).size;

  // 今日新增（从 stats.daily_trend 取今天的数据，避免时区问题）
  const todayStr = new Date().toISOString().slice(0, 10); // "2026-03-30"
  const todayCount = stats?.daily_trend?.find((d) => d.date === todayStr)?.count ?? 0;

  // 最近记忆（按时间排序，排除已删除记忆）
  const recentMemories = [...activeMemories]
    .sort((a, b) => {
      const timeA = a.created_at ? new Date(a.created_at).getTime() : 0;
      const timeB = b.created_at ? new Date(b.created_at).getTime() : 0;
      return timeB - timeA;
    })
    .slice(0, 5);

  // 用户记忆排行（排除已删除记忆）
  const userMemoryCount = new Map<string, number>();
  activeMemories.forEach((m) => {
    if (m.user_id) {
      userMemoryCount.set(
        m.user_id,
        (userMemoryCount.get(m.user_id) || 0) + 1
      );
    }
  });
  const topUsers = Array.from(userMemoryCount.entries())
    .sort((a, b) => b[1] - a[1]);

  return (
    <div className="space-y-6">
      {/* 连接状态提示 */}
      {connectionStatus === "disconnected" && (
        <Card className="border-destructive">
          <CardContent className="flex items-center justify-between p-4">
            <div className="flex items-center gap-3">
              <div className="h-3 w-3 rounded-full bg-red-500" />
              <div>
                <p className="text-sm font-medium text-destructive">
                  无法连接到 Mem0 API Server
                </p>
                <p className="text-xs text-muted-foreground">
                  请确保已运行{" "}
                  <code className="rounded bg-muted px-1">
                    mem0 server start --port 8080
                  </code>
                </p>
              </div>
            </div>
            <Link href="/settings">
              <Button variant="outline" size="sm">
                前往设置
              </Button>
            </Link>
          </CardContent>
        </Card>
      )}

      {connectionStatus === "checking" && (
        <Card>
          <CardContent className="flex items-center gap-3 p-4">
            <div className="h-3 w-3 animate-pulse rounded-full bg-yellow-500" />
            <p className="text-sm text-muted-foreground">
              正在检查 API 连接状态...
            </p>
          </CardContent>
        </Card>
      )}

      {/* 统计卡片 */}
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
        <StatsCard
          title="记忆总数"
          value={loading ? "..." : totalMemories}
          description="所有存储的记忆条目"
          icon={Brain}
        />
        <StatsCard
          title="用户总数"
          value={loading ? "..." : uniqueUserCount}
          description="拥有记忆的独立用户"
          icon={Users}
        />
        <StatsCard
          title="今日新增"
          value={loading ? "..." : todayCount}
          description="今日新增记忆数量"
          icon={TrendingUp}
          trend={todayCount > 0 ? `+${todayCount}` : undefined}
        />
        <StatsCard
          title="系统状态"
          value={
            connectionStatus === "connected"
              ? "正常"
              : connectionStatus === "checking"
              ? "检查中"
              : "离线"
          }
          description="API Server 连接状态"
          icon={Activity}
        />
      </div>

      {/* 统计图表（recharts） */}
      {stats && <StatsCharts stats={stats} />}

      <div className="grid gap-6 lg:grid-cols-3">
        {/* 最近记忆 - 占 2 列 */}
        <Card className="lg:col-span-2">
          <CardHeader className="flex flex-row items-center justify-between">
            <div>
              <CardTitle>最近操作</CardTitle>
              <CardDescription>最近操作记录</CardDescription>
            </div>
            <Link href="/memories">
              <Button variant="ghost" size="sm">
                查看全部
                <ArrowRight className="ml-1 h-4 w-4" />
              </Button>
            </Link>
          </CardHeader>
          <CardContent>
            {loading ? (
              <div className="space-y-3">
                {[1, 2, 3].map((i) => (
                  <div
                    key={i}
                    className="h-14 animate-pulse rounded-md bg-muted"
                  />
                ))}
              </div>
            ) : recentMemories.length > 0 ? (
              <div className="space-y-3">
                {recentMemories.map((memory) => (
                  <Link
                    key={memory.id}
                    href={`/memory/${memory.id}`}
                    className="flex items-start justify-between rounded-lg border p-3 transition-colors hover:bg-accent/50"
                  >
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-1.5 mb-1">
                        <StateBadge state={memory.state} />
                      </div>
                      <p className="text-sm truncate">{memory.memory}</p>
                      <div className="mt-1 flex items-center gap-2">
                        {memory.user_id && (
                          <Badge variant="secondary" className="text-xs">
                            {memory.user_id}
                          </Badge>
                        )}
                        <CategoryBadges categories={memory.categories} max={2} />
                        {memory.created_at && (
                          <span className="text-xs text-muted-foreground">
                            <Clock className="mr-1 inline h-3 w-3" />
                            {new Date(memory.created_at).toLocaleString(
                              "zh-CN"
                            )}
                          </span>
                        )}
                      </div>
                    </div>
                  </Link>
                ))}
              </div>
            ) : (
              <div className="flex flex-col items-center justify-center py-8 text-center">
                <Brain className="mb-3 h-12 w-12 text-muted-foreground/50" />
                <p className="text-sm text-muted-foreground">暂无记忆数据</p>
                <p className="text-xs text-muted-foreground">
                  通过 API 添加记忆后，数据将显示在这里
                </p>
              </div>
            )}
          </CardContent>
        </Card>

        {/* 用户排行 - 占 1 列 */}
        <Card className="flex flex-col">
          <CardHeader className="flex flex-row items-center justify-between">
            <div>
              <CardTitle>活跃用户</CardTitle>
              <CardDescription>按记忆数量排序</CardDescription>
            </div>
            <Link href="/users">
              <Button variant="ghost" size="sm">
                全部
                <ArrowRight className="ml-1 h-4 w-4" />
              </Button>
            </Link>
          </CardHeader>
          <CardContent className="flex-1 overflow-y-auto" style={{ maxHeight: "480px" }}>
            {loading ? (
              <div className="space-y-3">
                {[1, 2, 3].map((i) => (
                  <div
                    key={i}
                    className="h-10 animate-pulse rounded-md bg-muted"
                  />
                ))}
              </div>
            ) : topUsers.length > 0 ? (
              <div className="space-y-1">
                {topUsers.map(([uid, count], index) => (
                  <Link
                    key={uid}
                    href={`/users/${encodeURIComponent(uid)}`}
                    className="flex items-center gap-3 rounded-lg p-2 transition-colors hover:bg-accent/50"
                  >
                    <span className="flex h-7 w-7 items-center justify-center rounded-full bg-primary/10 text-xs font-bold text-primary">
                      {index + 1}
                    </span>
                    <div className="flex-1 min-w-0">
                      <p className="text-sm font-medium truncate">{uid}</p>
                    </div>
                    <Badge variant="secondary">{count}</Badge>
                  </Link>
                ))}
              </div>
            ) : (
              <div className="flex flex-col items-center justify-center py-6 text-center">
                <Users className="mb-2 h-8 w-8 text-muted-foreground/50" />
                <p className="text-xs text-muted-foreground">暂无用户数据</p>
              </div>
            )}
          </CardContent>
        </Card>
      </div>

      {/* 添加记忆弹窗 */}
      <AddMemoryDialog
        open={addDialogOpen}
        onOpenChange={setAddDialogOpen}
        onSuccess={refetch}
      />
    </div>
  );
}
