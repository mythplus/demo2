"use client";

import React, { useState } from "react";
import dynamic from "next/dynamic";
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
import { CategoryBadges } from "@/components/memories/category-badge";
import { formatDateTime } from "@/lib/utils";
import { useUIStore } from "@/store";
import { useDashboardData } from "@/hooks/use-dashboard-data";

// 懒加载重型组件：图表库 recharts 体积较大，首屏只需统计卡片
const StatsCharts = dynamic(
  () => import("@/components/dashboard/stats-charts").then((m) => ({ default: m.StatsCharts })),
  { ssr: false, loading: () => <div className="h-[300px] animate-pulse rounded-lg bg-muted" /> }
);

// 懒加载弹窗组件：用户点击时才需要
const AddMemoryDialog = dynamic(
  () => import("@/components/memories/add-memory-dialog").then((m) => ({ default: m.AddMemoryDialog })),
  { ssr: false }
);

/* ============================================================
 * 统计卡片 — 简约风格
 * ============================================================ */
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
    <Card className="transition-shadow duration-200 hover:shadow-sm">
      <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
        <CardTitle className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
          {title}
        </CardTitle>
        <Icon className="h-4 w-4 text-muted-foreground/60" />
      </CardHeader>
      <CardContent>
        {trend ? (
          <div className="text-2xl font-semibold text-emerald-600 dark:text-emerald-400">
            {trend}
          </div>
        ) : (
          <div className="text-2xl font-semibold">{value}</div>
        )}
        <p className="mt-1 text-xs text-muted-foreground">{description}</p>
      </CardContent>
    </Card>
  );
}

/* ============================================================
 * 骨架屏
 * ============================================================ */
function StatsCardSkeleton() {
  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
        <div className="h-3 w-16 animate-pulse rounded bg-muted" />
        <div className="h-4 w-4 animate-pulse rounded bg-muted" />
      </CardHeader>
      <CardContent>
        <div className="h-7 w-20 animate-pulse rounded bg-muted" />
        <div className="mt-2 h-3 w-28 animate-pulse rounded bg-muted" />
      </CardContent>
    </Card>
  );
}

/* ============================================================
 * Dashboard 主页面
 * ============================================================ */
export default function DashboardPage() {
  const [addDialogOpen, setAddDialogOpen] = useState(false);
  const connectionStatus = useUIStore((s) => s.connectionStatus);
  const { summary, stats, requestStats, loading, refetch } = useDashboardData(
    connectionStatus === "connected"
  );

  const totalMemories = stats?.total_memories ?? 0;
  const uniqueUserCount = stats?.total_users ?? summary?.top_users?.length ?? 0;

  const todayStr = new Date().toISOString().slice(0, 10);
  const todayCount =
    stats?.daily_trend?.find((d) => d.date === todayStr)?.count ?? 0;

  const recentMemories = summary?.recent_memories ?? [];
  const topUsers = summary?.top_users ?? [];

  return (
    <div className="space-y-4">
      {/* 页面标题区域 */}
      <div>
        <h2 className="text-xl font-bold tracking-tight">仪表盘</h2>
        <p className="text-sm text-muted-foreground">系统概览与核心指标</p>
      </div>

      {/* 连接状态提示 */}
      {connectionStatus === "disconnected" && (
        <div className="flex items-center justify-between rounded-lg border border-destructive/50 bg-destructive/5 px-4 py-3">
          <div className="flex items-center gap-3">
            <div className="h-2 w-2 rounded-full bg-red-500" />
            <div>
              <p className="text-sm font-medium">无法连接到 API Server</p>
              <p className="text-xs text-muted-foreground">
                请确保已运行{" "}
                <code className="rounded bg-muted px-1 py-0.5 text-xs">
                  python server.py
                </code>
              </p>
            </div>
          </div>
          <Link href="/settings">
            <Button variant="outline" size="sm">
              设置
            </Button>
          </Link>
        </div>
      )}

      {connectionStatus === "checking" && (
        <div className="flex items-center gap-3 rounded-lg border px-4 py-3">
          <div className="h-2 w-2 animate-pulse rounded-full bg-amber-500" />
          <p className="text-sm text-muted-foreground">
            正在检查 API 连接状态...
          </p>
        </div>
      )}

      {/* 统计卡片 */}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {loading ? (
          <>
            <StatsCardSkeleton />
            <StatsCardSkeleton />
            <StatsCardSkeleton />
            <StatsCardSkeleton />
          </>
        ) : (
          <>
            <StatsCard
              title="记忆总数"
              value={totalMemories}
              description="所有存储的记忆条目"
              icon={Brain}
            />
            <StatsCard
              title="用户总数"
              value={uniqueUserCount}
              description="拥有记忆的独立用户"
              icon={Users}
            />
            <StatsCard
              title="今日新增"
              value={todayCount}
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
          </>
        )}
      </div>

      {/* 统计图表 */}
      {stats && <StatsCharts stats={stats} requestStats={requestStats} />}

      {/* 最近记忆 + 用户排行 */}
      <div className="grid gap-4 lg:grid-cols-3">
        {/* 最近记忆 */}
        <Card className="lg:col-span-2">
          <CardHeader className="flex flex-row items-center justify-between pb-3">
            <div>
              <CardTitle className="text-base">最近记忆</CardTitle>
              <CardDescription className="text-xs">
                最新添加的记忆条目
              </CardDescription>
            </div>
            <Link href="/memories">
              <Button variant="ghost" size="sm" className="h-8 text-xs">
                查看全部
                <ArrowRight className="ml-1 h-3.5 w-3.5" />
              </Button>
            </Link>
          </CardHeader>
          <CardContent>
            {loading ? (
              <div className="space-y-2">
                {[1, 2, 3].map((i) => (
                  <div
                    key={i}
                    className="h-14 animate-pulse rounded-lg bg-muted"
                  />
                ))}
              </div>
            ) : recentMemories.length > 0 ? (
              <div className="space-y-1">
                {recentMemories.map((memory) => (
                  <Link
                    key={memory.id}
                    href={`/memory/${memory.id}`}
                    className="group flex items-start justify-between rounded-lg p-3 transition-colors duration-150 hover:bg-muted/50"
                  >
                    <div className="flex-1 min-w-0">
                      <p className="text-sm leading-snug line-clamp-1">
                        {memory.memory}
                      </p>
                      <div className="mt-1.5 flex items-center gap-2 flex-wrap">
                        {memory.user_id && (
                          <span className="text-[11px] text-muted-foreground max-w-[160px] truncate" title={memory.user_id}>
                            {memory.user_id}
                          </span>
                        )}
                        <CategoryBadges
                          categories={memory.categories}
                          max={2}
                        />
                        {memory.created_at && (
                          <span className="text-[11px] text-muted-foreground/70">
                            <Clock className="mr-0.5 inline h-3 w-3" />
                            {formatDateTime(memory.created_at)}
                          </span>
                        )}
                      </div>
                    </div>
                    <ArrowRight className="ml-2 mt-1 h-3.5 w-3.5 text-muted-foreground/40 opacity-0 transition-opacity group-hover:opacity-100" />
                  </Link>
                ))}
              </div>
            ) : (
              <div className="flex flex-col items-center justify-center py-12 text-center">
                <Brain className="mb-3 h-10 w-10 text-muted-foreground/30" />
                <p className="text-sm text-muted-foreground">暂无记忆数据</p>
                <p className="mt-1 text-xs text-muted-foreground/70">
                  通过 API 添加记忆后，数据将显示在这里
                </p>
              </div>
            )}
          </CardContent>
        </Card>

        {/* 用户排行 */}
        <Card className="flex flex-col">
          <CardHeader className="flex flex-row items-center justify-between pb-3">
            <div>
              <CardTitle className="text-base">活跃用户</CardTitle>
              <CardDescription className="text-xs">
                按记忆数量排序
              </CardDescription>
            </div>
            <Link href="/users">
              <Button variant="ghost" size="sm" className="h-8 text-xs">
                全部
                <ArrowRight className="ml-1 h-3.5 w-3.5" />
              </Button>
            </Link>
          </CardHeader>
          <CardContent
            className="flex-1 overflow-y-auto"
            style={{ maxHeight: "480px" }}
          >
            {loading ? (
              <div className="space-y-2">
                {[1, 2, 3].map((i) => (
                  <div
                    key={i}
                    className="h-10 animate-pulse rounded-lg bg-muted"
                  />
                ))}
              </div>
            ) : topUsers.length > 0 ? (
              <div className="space-y-0.5">
                {topUsers.map((user, index) => (
                  <Link
                    key={user.user_id}
                    href={`/users/${encodeURIComponent(user.user_id)}`}
                    className="flex items-center gap-3 rounded-lg p-2 transition-colors duration-150 hover:bg-muted/50"
                  >
                    <span className="flex h-6 w-6 items-center justify-center rounded-full bg-primary/8 text-[11px] font-semibold text-primary">
                      {index + 1}
                    </span>
                    <div className="flex-1 min-w-0">
                      <p className="text-sm truncate">{user.user_id}</p>
                    </div>
                    <span className="text-xs font-medium text-muted-foreground tabular-nums">
                      {user.memory_count}
                    </span>
                  </Link>
                ))}
              </div>
            ) : (
              <div className="flex flex-col items-center justify-center py-8 text-center">
                <Users className="mb-2 h-8 w-8 text-muted-foreground/30" />
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
