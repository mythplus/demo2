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
import { Input } from "@/components/ui/input";
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

// 请求类型 Tailwind 颜色（只有4种业务类型）
const TYPE_COLORS: Record<string, { bg: string; text: string }> = {
  "添加": { bg: "bg-green-100 dark:bg-green-900/30", text: "text-green-700 dark:text-green-300" },
  "搜索": { bg: "bg-blue-100 dark:bg-blue-900/30", text: "text-blue-700 dark:text-blue-300" },
  "删除": { bg: "bg-red-100 dark:bg-red-900/30", text: "text-red-700 dark:text-red-300" },
  "更新": { bg: "bg-orange-100 dark:bg-orange-900/30", text: "text-orange-700 dark:text-orange-300" },
};

// 请求类型 hex 颜色（给 recharts 柱状图和统计概览用）
const TYPE_HEX: Record<string, string> = {
  "添加": "#22c55e",
  "搜索": "#3b82f6",
  "删除": "#ef4444",
  "更新": "#f97316",
};

// 默认业务类型（筛选下拉用）
const DEFAULT_TYPES = ["添加", "搜索", "删除", "更新"];

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

// 时间范围选项
const TIME_RANGES = [
  { value: "1h", label: "过去1小时", hours: 1 },
  { value: "6h", label: "过去6小时", hours: 6 },
  { value: "12h", label: "过去12小时", hours: 12 },
  { value: "1d", label: "过去1天", hours: 24 },
  { value: "7d", label: "过去7天", hours: 24 * 7 },
  { value: "14d", label: "过去14天", hours: 24 * 14 },
  { value: "30d", label: "过去30天", hours: 24 * 30 },
  { value: "all", label: "所有时间", hours: 0 },
] as const;

function getSinceISO(rangeValue: string): string | undefined {
  const range = TIME_RANGES.find((r) => r.value === rangeValue);
  if (!range || range.hours === 0) return undefined;
  return new Date(Date.now() - range.hours * 3600000).toISOString();
}

export default function RequestsPage() {
  const [logs, setLogs] = useState<RequestLog[]>([]);
  const [stats, setStats] = useState<RequestLogsStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [total, setTotal] = useState(0);
  const [filterType, setFilterType] = useState<string>("all");
  const [timeRange, setTimeRange] = useState<string>("all");
  const [page, setPage] = useState(0);
  const [jumpPage, setJumpPage] = useState("");
  const pageSize = 20;

  const fetchLogs = useCallback(async () => {
    setLoading(true);
    const since = getSinceISO(timeRange);
    try {
      const [logsRes, statsRes] = await Promise.all([
        mem0Api.getRequestLogs({
          request_type: filterType === "all" ? undefined : filterType,
          since,
          limit: pageSize,
          offset: page * pageSize,
        }),
        page === 0 ? mem0Api.getRequestLogsStats(since).catch(() => null) : Promise.resolve(stats),
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
  }, [filterType, timeRange, page]);

  useEffect(() => {
    fetchLogs();
  }, [fetchLogs]);

  const totalPages = Math.ceil(total / pageSize);

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
          <div className="flex items-center gap-2 shrink-0">
            <Select
              value={timeRange}
              onValueChange={(v) => { setTimeRange(v); setPage(0); }}
            >
              <SelectTrigger className="w-[140px] h-8">
                <Clock className="mr-1.5 h-3.5 w-3.5 text-muted-foreground" />
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {TIME_RANGES.map((r) => (
                  <SelectItem key={r.value} value={r.value}>
                    {r.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            <Button variant="outline" size="icon" onClick={fetchLogs}>
              <RefreshCw className={`h-4 w-4 ${loading ? "animate-spin" : ""}`} />
            </Button>
          </div>
        </div>

        {/* 统计概览：总数 + 各类型紧凑排列 */}
        {stats && (
          <Card>
            <CardContent className="py-4">
              <div className="flex flex-wrap items-center gap-4">
                {/* 总请求数 */}
                <div className="flex items-center gap-2 pr-4 border-r">
                  <Activity className="h-4 w-4 text-muted-foreground" />
                  <span className="text-sm text-muted-foreground">总请求</span>
                  <span className="text-lg font-bold">{stats.total}</span>
                </div>
                {/* 各类型 */}
                {Object.entries(stats.type_distribution)
                  .sort((a, b) => b[1] - a[1])
                  .map(([type, count]) => (
                    <div key={type} className="flex items-center gap-1.5">
                      <span
                        className="h-2.5 w-2.5 rounded-sm shrink-0"
                        style={{ background: TYPE_HEX[type] || "#94a3b8" }}
                      />
                      <span className="text-sm text-muted-foreground">{type}</span>
                      <span className="text-sm font-bold">{count}</span>
                    </div>
                  ))}
              </div>
            </CardContent>
          </Card>
        )}

        {/* 趋势图 - 单色柱状图，tooltip 显示各类型明细 */}
        {stats && stats.daily_trend && stats.daily_trend.length > 0 && (
          <Card>
            <CardHeader>
              <CardTitle className="text-base">请求趋势</CardTitle>
              <CardDescription>近 14 天每日请求数</CardDescription>
            </CardHeader>
            <CardContent>
              <ResponsiveContainer width="100%" height={220}>
                <BarChart data={stats.daily_trend.map((d: any) => {
                  // 计算每天总数
                  const total = (stats.types || []).reduce((sum: number, t: string) => sum + (Number(d[t]) || 0), 0);
                  return { ...d, date: String(d.date || "").slice(5), _total: total };
                })}>
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
                    content={({ active, payload, label }: any) => {
                      if (!active || !payload || !payload[0]) return null;
                      const data = payload[0].payload;
                      const types = stats.types || [];
                      const totalCount = data._total || 0;
                      return (
                        <div className="rounded-lg border bg-background p-3 shadow-md">
                          <p className="text-xs text-muted-foreground mb-2">{label}</p>
                          <div className="flex items-center gap-2 mb-1.5">
                            <span className="h-2.5 w-2.5 rounded-sm" style={{ background: "#a78bfa" }} />
                            <span className="text-sm font-medium">REQUESTS</span>
                            <span className="text-sm font-bold ml-auto">{totalCount}</span>
                          </div>
                          {types.map((t: string) => {
                            const count = Number(data[t]) || 0;
                            if (count === 0) return null;
                            return (
                              <div key={t} className="flex items-center gap-2">
                                <span className="h-2.5 w-2.5 rounded-sm" style={{ background: TYPE_HEX[t] || "#94a3b8" }} />
                                <span className="text-xs text-muted-foreground">{t}</span>
                                <span className="text-xs font-medium ml-auto">{count}</span>
                              </div>
                            );
                          })}
                        </div>
                      );
                    }}
                  />
                  <Bar dataKey="_total" fill="#a78bfa" radius={[4, 4, 0, 0]} />
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
              {/* 合并默认类型 + stats 中实际出现的类型，去重 */}
              {(() => {
                const statsTypes = stats?.types || [];
                const merged = Array.from(new Set([...DEFAULT_TYPES, ...statsTypes]));
                return merged.map((t) => (
                  <SelectItem key={t} value={t}>
                    <span className="flex items-center gap-2">
                      <span
                        className="inline-block h-2 w-2 rounded-sm shrink-0"
                        style={{ background: TYPE_HEX[t] || "#94a3b8" }}
                      />
                      {t}
                    </span>
                  </SelectItem>
                ));
              })()}
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
                  <div className="flex items-center justify-between border-t px-4 py-3 flex-wrap gap-3">
                    <p className="text-sm text-muted-foreground">
                      第 {page + 1} / {totalPages} 页，共 {total} 条
                    </p>
                    <div className="flex items-center gap-1.5">
                      <Button
                        variant="outline"
                        size="sm"
                        disabled={page <= 0}
                        onClick={() => setPage((p) => p - 1)}
                      >
                        <ChevronLeft className="h-4 w-4 mr-1" />
                        上一页
                      </Button>

                      {/* 智能页码显示 */}
                      {(() => {
                        const pages: (number | string)[] = [];
                        const current = page + 1; // 显示用的页码从1开始
                        if (totalPages <= 7) {
                          for (let i = 1; i <= totalPages; i++) pages.push(i);
                        } else {
                          pages.push(1);
                          if (current > 3) pages.push("...");
                          const start = Math.max(2, current - 1);
                          const end = Math.min(totalPages - 1, current + 1);
                          for (let i = start; i <= end; i++) pages.push(i);
                          if (current < totalPages - 2) pages.push("...");
                          pages.push(totalPages);
                        }
                        return pages.map((p, idx) =>
                          typeof p === "string" ? (
                            <span key={`ellipsis-${idx}`} className="px-1 text-muted-foreground text-sm">
                              ···
                            </span>
                          ) : (
                            <Button
                              key={p}
                              variant={p === page + 1 ? "default" : "outline"}
                              size="sm"
                              className="w-8 h-8 p-0"
                              onClick={() => setPage(p - 1)}
                            >
                              {p}
                            </Button>
                          )
                        );
                      })()}

                      <Button
                        variant="outline"
                        size="sm"
                        disabled={page >= totalPages - 1}
                        onClick={() => setPage((p) => p + 1)}
                      >
                        下一页
                        <ChevronRight className="h-4 w-4 ml-1" />
                      </Button>

                      {/* 跳转到指定页 */}
                      <div className="flex items-center gap-1.5 ml-3">
                        <span className="text-sm text-muted-foreground whitespace-nowrap">跳转到</span>
                        <Input
                          className="w-16 h-8 text-center text-sm"
                          value={jumpPage}
                          placeholder="页码"
                          onChange={(e) => {
                            const val = e.target.value;
                            if (val === "" || /^\d+$/.test(val)) {
                              setJumpPage(val);
                            }
                          }}
                          onKeyDown={(e) => {
                            if (e.key === "Enter" && jumpPage) {
                              const target = Math.max(1, Math.min(totalPages, parseInt(jumpPage)));
                              setPage(target - 1);
                              setJumpPage("");
                            }
                          }}
                        />
                        <span className="text-sm text-muted-foreground">页</span>
                        <Button
                          variant="outline"
                          size="sm"
                          className="h-8"
                          onClick={() => {
                            if (jumpPage) {
                              const target = Math.max(1, Math.min(totalPages, parseInt(jumpPage)));
                              setPage(target - 1);
                              setJumpPage("");
                            }
                          }}
                        >
                          确定
                        </Button>
                      </div>
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
