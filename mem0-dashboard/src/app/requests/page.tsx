"use client";

import React, { useEffect, useState, useCallback } from "react";
import {
  Activity,
  RefreshCw,
  Filter,
  Clock,
  CheckCircle,
  XCircle,
  ChevronLeft,
  ChevronRight,
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
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
  TooltipProvider,
} from "@/components/ui/tooltip";
import { mem0Api } from "@/lib/api";
import type { RequestLog, RequestLogsStats } from "@/lib/api";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip as RechartsTooltip,
  ResponsiveContainer,
} from "recharts";

/* eslint-disable @typescript-eslint/no-explicit-any */

// 请求类型颜色
const TYPE_COLORS: Record<string, { bg: string; text: string }> = {
  "添加": { bg: "bg-green-100 dark:bg-green-900/30", text: "text-green-700 dark:text-green-300" },
  "搜索": { bg: "bg-blue-100 dark:bg-blue-900/30", text: "text-blue-700 dark:text-blue-300" },
  "删除": { bg: "bg-red-100 dark:bg-red-900/30", text: "text-red-700 dark:text-red-300" },
  "更新": { bg: "bg-orange-100 dark:bg-orange-900/30", text: "text-orange-700 dark:text-orange-300" },
  "查询": { bg: "bg-purple-100 dark:bg-purple-900/30", text: "text-purple-700 dark:text-purple-300" },
  "获取全部": { bg: "bg-indigo-100 dark:bg-indigo-900/30", text: "text-indigo-700 dark:text-indigo-300" },
  "统计": { bg: "bg-cyan-100 dark:bg-cyan-900/30", text: "text-cyan-700 dark:text-cyan-300" },
  "关联": { bg: "bg-pink-100 dark:bg-pink-900/30", text: "text-pink-700 dark:text-pink-300" },
  "历史": { bg: "bg-gray-100 dark:bg-gray-800/30", text: "text-gray-600 dark:text-gray-400" },
};

const ALL_TYPES = ["添加", "搜索", "删除", "更新", "查询", "获取全部", "统计", "关联", "历史"];

function formatLatency(ms: number): string {
  if (ms < 1000) return `${ms.toFixed(0)}ms`;
  return `${(ms / 1000).toFixed(2)}s`;
}

function formatRelativeTime(timestamp: string): string {
  const diff = Date.now() - new Date(timestamp).getTime();
  const minutes = Math.floor(diff / 60000);
  if (minutes < 1) return "刚刚";
  if (minutes < 60) return `${minutes}分钟前`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}小时前`;
  const days = Math.floor(hours / 24);
  return `${days}天前`;
}

export default function RequestsPage() {
  const [logs, setLogs] = useState<RequestLog[]>([]);
  const [stats, setStats] = useState<RequestLogsStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [total, setTotal] = useState(0);
  const [filterType, setFilterType] = useState<string>("all");
  const [page, setPage] = useState(0);
  const pageSize = 20;

  const fetchLogs = useCallback(async () => {
    setLoading(true);
    try {
      const [logsRes, statsRes] = await Promise.all([
        mem0Api.getRequestLogs({
          request_type: filterType === "all" ? undefined : filterType,
          limit: pageSize,
          offset: page * pageSize,
        }),
        page === 0 ? mem0Api.getRequestLogsStats().catch(() => null) : Promise.resolve(stats),
      ]);
      setLogs(logsRes.logs || []);
      setTotal(logsRes.total || 0);
      if (statsRes) setStats(statsRes);
    } catch (err) {
      console.error("获取请求日志失败:", err);
      setLogs([]);
    } finally {
      setLoading(false);
    }
  }, [filterType, page]);

  useEffect(() => {
    fetchLogs();
  }, [fetchLogs]);

  const totalPages = Math.ceil(total / pageSize);

  // 趋势图数据
  const trendData = (stats?.daily_trend || []).map((d) => ({
    date: d.date.slice(5),
    count: d.count,
  }));

  return (
    <TooltipProvider>
      <div className="space-y-6">
        {/* 页面头部 */}
        <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <h2 className="text-2xl font-bold tracking-tight">请求监控</h2>
            <p className="text-muted-foreground">
              记录所有 API 请求的类型、延迟、状态等信息
            </p>
          </div>
          <Button variant="outline" size="icon" onClick={fetchLogs}>
            <RefreshCw className={`h-4 w-4 ${loading ? "animate-spin" : ""}`} />
          </Button>
        </div>

        {/* 统计概览 */}
        {stats && (
          <div className="grid gap-4 md:grid-cols-4">
            <Card>
              <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                <CardTitle className="text-sm font-medium">总请求数</CardTitle>
                <Activity className="h-4 w-4 text-muted-foreground" />
              </CardHeader>
              <CardContent>
                <div className="text-2xl font-bold">{stats.total}</div>
              </CardContent>
            </Card>
            {/* 类型分布 top 3 */}
            {Object.entries(stats.type_distribution)
              .sort((a, b) => b[1] - a[1])
              .slice(0, 3)
              .map(([type, count]) => {
                const colors = TYPE_COLORS[type] || TYPE_COLORS["查询"];
                return (
                  <Card key={type}>
                    <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                      <CardTitle className="text-sm font-medium">{type}</CardTitle>
                      <span className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${colors.bg} ${colors.text}`}>
                        {type}
                      </span>
                    </CardHeader>
                    <CardContent>
                      <div className="text-2xl font-bold">{count}</div>
                    </CardContent>
                  </Card>
                );
              })}
          </div>
        )}

        {/* 趋势图 */}
        {stats && trendData.some((d) => d.count > 0) && (
          <Card>
            <CardHeader>
              <CardTitle className="text-base">请求趋势</CardTitle>
              <CardDescription>近 14 天每日请求数</CardDescription>
            </CardHeader>
            <CardContent>
              <ResponsiveContainer width="100%" height={180}>
                <BarChart data={trendData}>
                  <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
                  <XAxis
                    dataKey="date"
                    tick={{ fontSize: 11, fill: "hsl(var(--muted-foreground))" }}
                    tickLine={false}
                  />
                  <YAxis
                    allowDecimals={false}
                    tick={{ fontSize: 11, fill: "hsl(var(--muted-foreground))" }}
                    tickLine={false}
                  />
                  <RechartsTooltip
                    formatter={(value: any) => [`${value} 次`, "请求"]}
                    contentStyle={{
                      borderRadius: "8px",
                      border: "1px solid hsl(var(--border))",
                      background: "hsl(var(--background))",
                      color: "hsl(var(--foreground))",
                    }}
                  />
                  <Bar dataKey="count" fill="hsl(var(--primary))" radius={[4, 4, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </CardContent>
          </Card>
        )}

        {/* 筛选栏 */}
        <div className="flex items-center gap-3">
          <Filter className="h-4 w-4 text-muted-foreground" />
          <Select
            value={filterType}
            onValueChange={(v) => { setFilterType(v); setPage(0); }}
          >
            <SelectTrigger className="w-[160px]">
              <SelectValue placeholder="全部类型" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">全部类型</SelectItem>
              {ALL_TYPES.map((t) => (
                <SelectItem key={t} value={t}>{t}</SelectItem>
              ))}
            </SelectContent>
          </Select>
          <span className="text-sm text-muted-foreground">
            共 {total} 条记录
          </span>
        </div>

        {/* 请求日志表格 */}
        <Card>
          <CardContent className="p-0">
            {loading ? (
              <div className="space-y-2 p-4">
                {[1, 2, 3, 4, 5].map((i) => (
                  <div key={i} className="h-12 animate-pulse rounded bg-muted" />
                ))}
              </div>
            ) : logs.length > 0 ? (
              <>
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead className="w-[130px]">时间</TableHead>
                      <TableHead className="w-[80px]">类型</TableHead>
                      <TableHead className="w-[100px]">用户</TableHead>
                      <TableHead className="w-[90px]">延迟</TableHead>
                      <TableHead>请求载荷</TableHead>
                      <TableHead className="w-[60px] text-center">状态</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {logs.map((log) => {
                      const colors = TYPE_COLORS[log.request_type] || { bg: "bg-muted", text: "text-muted-foreground" };
                      const isSuccess = log.status_code >= 200 && log.status_code < 400;
                      return (
                        <TableRow key={log.id}>
                          <TableCell>
                            <Tooltip>
                              <TooltipTrigger asChild>
                                <span className="text-xs text-muted-foreground cursor-help">
                                  {formatRelativeTime(log.timestamp)}
                                </span>
                              </TooltipTrigger>
                              <TooltipContent>
                                {new Date(log.timestamp).toLocaleString("zh-CN")}
                              </TooltipContent>
                            </Tooltip>
                          </TableCell>
                          <TableCell>
                            <span className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${colors.bg} ${colors.text}`}>
                              {log.request_type}
                            </span>
                          </TableCell>
                          <TableCell>
                            {log.user_id ? (
                              <Badge variant="secondary" className="text-xs">
                                {log.user_id}
                              </Badge>
                            ) : (
                              <span className="text-xs text-muted-foreground">—</span>
                            )}
                          </TableCell>
                          <TableCell>
                            <span className={`text-xs font-mono ${
                              log.latency_ms > 5000 ? "text-red-600 dark:text-red-400" :
                              log.latency_ms > 1000 ? "text-yellow-600 dark:text-yellow-400" :
                              "text-muted-foreground"
                            }`}>
                              {formatLatency(log.latency_ms)}
                            </span>
                          </TableCell>
                          <TableCell>
                            {log.payload_summary ? (
                              <Tooltip>
                                <TooltipTrigger asChild>
                                  <span className="text-xs text-muted-foreground font-mono truncate block max-w-[300px] cursor-help">
                                    {log.payload_summary}
                                  </span>
                                </TooltipTrigger>
                                <TooltipContent side="bottom" className="max-w-md">
                                  <pre className="text-xs whitespace-pre-wrap break-all">
                                    {log.payload_summary}
                                  </pre>
                                </TooltipContent>
                              </Tooltip>
                            ) : (
                              <span className="text-xs text-muted-foreground">—</span>
                            )}
                          </TableCell>
                          <TableCell className="text-center">
                            {isSuccess ? (
                              <CheckCircle className="h-4 w-4 text-green-500 mx-auto" />
                            ) : (
                              <Tooltip>
                                <TooltipTrigger asChild>
                                  <XCircle className="h-4 w-4 text-red-500 mx-auto cursor-help" />
                                </TooltipTrigger>
                                <TooltipContent>
                                  {log.status_code} {log.error || ""}
                                </TooltipContent>
                              </Tooltip>
                            )}
                          </TableCell>
                        </TableRow>
                      );
                    })}
                  </TableBody>
                </Table>

                {/* 分页 */}
                {totalPages > 1 && (
                  <div className="flex items-center justify-between border-t px-4 py-3">
                    <p className="text-sm text-muted-foreground">
                      第 {page + 1} / {totalPages} 页
                    </p>
                    <div className="flex items-center gap-2">
                      <Button
                        variant="outline"
                        size="sm"
                        disabled={page <= 0}
                        onClick={() => setPage((p) => p - 1)}
                      >
                        <ChevronLeft className="h-4 w-4" />
                      </Button>
                      <Button
                        variant="outline"
                        size="sm"
                        disabled={page >= totalPages - 1}
                        onClick={() => setPage((p) => p + 1)}
                      >
                        <ChevronRight className="h-4 w-4" />
                      </Button>
                    </div>
                  </div>
                )}
              </>
            ) : (
              <div className="flex flex-col items-center justify-center py-16 text-center">
                <Activity className="mb-4 h-16 w-16 text-muted-foreground/30" />
                <p className="text-lg font-medium text-muted-foreground">暂无请求记录</p>
                <p className="mt-1 text-sm text-muted-foreground">
                  API 请求将自动记录在这里
                </p>
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </TooltipProvider>
  );
}
