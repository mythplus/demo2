"use client";

import React, { useEffect, useState, useCallback } from "react";
import {
  RefreshCw,
  Clock,
  CheckCircle,
  XCircle,
  ChevronLeft,
  ChevronRight,
  LayoutGrid,
  PlusCircle,
  Search,
  Trash2,
  Edit3,
  User,
  ListOrdered,
  SlidersHorizontal,
  Timer,
  CalendarDays,
  X,
} from "lucide-react";
import {
  Card,
  CardContent,
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

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

// 请求类型 hex 颜色（给 recharts 柱状图和统计概览用）
const TYPE_HEX: Record<string, string> = {
  "添加": "#22c55e",
  "搜索": "#3b82f6",
  "删除": "#ef4444",
  "更新": "#f97316",
};

// Tab 类型配置
const TAB_ITEMS = [
  { value: "all", label: "概览", icon: LayoutGrid },
  { value: "添加", label: "添加", icon: PlusCircle },
  { value: "搜索", label: "搜索", icon: Search },
  { value: "更新", label: "更新", icon: Edit3 },
  { value: "删除", label: "删除", icon: Trash2 },
];

// 请求类型 Badge 样式
const TYPE_BADGE_STYLES: Record<string, string> = {
  "添加": "bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-300",
  "搜索": "bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-300",
  "删除": "bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-300",
  "更新": "bg-orange-100 text-orange-700 dark:bg-orange-900/30 dark:text-orange-300",
};

function formatLatency(ms: number): string {
  if (ms < 1000) return `${ms.toFixed(2)} ms`;
  return `${(ms / 1000).toFixed(2)} s`;
}

function formatRelativeTime(timestamp: string): string {
  const diff = Date.now() - new Date(timestamp).getTime();
  const minutes = Math.floor(diff / 60000);
  if (minutes < 1) return "刚刚";
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  return `${days}d ago`;
}

// 格式化日期为 "MM-DD" 数字日期格式（直接从字符串提取，避免时区偏移）
function formatChartDate(dateStr: string): string {
  // 后端返回格式: "YYYY-MM-DD" 或 "YYYY-MM-DD HH:MM"
  const parts = dateStr.split("-");
  if (parts.length >= 3) {
    const month = parts[1];
    const day = parts[2].split(" ")[0]; // 去掉可能的时间部分
    return `${month}-${day}`;
  }
  // fallback: 使用 Date 对象
  const date = new Date(dateStr);
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  return `${month}-${day}`;
}



// 根据粒度格式化图表X轴标签
function formatChartLabel(dateStr: string, granularity: string): string {
  if (granularity === "hour") {
    // dateStr 格式: "2026-04-02 14:00"
    try {
      const parts = dateStr.split(" ");
      if (parts.length < 2) return dateStr;
      const timeParts = parts[1].split(":");
      return `${timeParts[0]}:00`; // 显示 "14:00" 格式
    } catch {
      return dateStr;
    }
  }
  // 天粒度："MM-DD" 数字日期格式
  return formatChartDate(dateStr);
}

export default function RequestsPage() {
  const [logs, setLogs] = useState<RequestLog[]>([]);
  const [stats, setStats] = useState<RequestLogsStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [total, setTotal] = useState(0);
  const [filterType, setFilterType] = useState<string>("all");
  const [page, setPage] = useState(0);
  const [jumpPage, setJumpPage] = useState("");
  const [showFilter, setShowFilter] = useState(false);
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");
  const [activeQuick, setActiveQuick] = useState<string>("");
  const pageSize = 20;

  // 快捷时间按钮处理
  const handleQuickDate = (type: string) => {
    const now = new Date();
    const toStr = now.toISOString().slice(0, 10);
    let fromStr = toStr;
    if (type === "today") {
      fromStr = toStr;
    } else if (type === "7d") {
      const d = new Date(now);
      d.setDate(d.getDate() - 6);
      fromStr = d.toISOString().slice(0, 10);
    } else if (type === "30d") {
      const d = new Date(now);
      d.setDate(d.getDate() - 29);
      fromStr = d.toISOString().slice(0, 10);
    }
    setDateFrom(fromStr);
    setDateTo(toStr);
    setActiveQuick(type);
    setPage(0);
  };

  // 清除日期筛选
  const clearDateFilter = () => {
    setDateFrom("");
    setDateTo("");
    setActiveQuick("");
    setPage(0);
  };

  // 判断是否有日期筛选激活
  const hasDateFilter = dateFrom !== "" || dateTo !== "";

  const fetchLogs = useCallback(async () => {
    setLoading(true);
    try {
      // 构建时间范围参数
      const sinceParam = dateFrom ? `${dateFrom}T00:00:00` : undefined;
      const untilParam = dateTo ? `${dateTo}T23:59:59` : undefined;

      const [logsRes, statsRes] = await Promise.all([
        mem0Api.getRequestLogs({
          request_type: filterType === "all" ? undefined : filterType,
          since: sinceParam,
          until: untilParam,
          limit: pageSize,
          offset: page * pageSize,
        }),
        page === 0 ? mem0Api.getRequestLogsStats(sinceParam, untilParam).catch(() => null) : Promise.resolve(stats),
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
  }, [filterType, page, dateFrom, dateTo]);

  useEffect(() => {
    fetchLogs();
  }, [fetchLogs]);

  const totalPages = Math.ceil(total / pageSize);

  // 准备图表数据（根据后端返回的粒度动态格式化标签）
  const granularity = stats?.granularity || "day";
  const chartData = stats?.daily_trend?.map((d: any) => {
    const total = (stats.types || []).reduce(
      (sum: number, t: string) => sum + (Number(d[t]) || 0),
      0
    );
    return {
      ...d,
      dateLabel: formatChartLabel(String(d.date || ""), granularity),
      _total: total,
    };
  }) || [];

  return (
    <TooltipProvider>
      <div className="space-y-6">
        {/* ===== 页面头部：标题 + 时间范围 ===== */}
        <div>
          <h2 className="text-2xl font-bold tracking-tight">请求日志</h2>
          <p className="text-sm text-muted-foreground mt-1">查看所有 API 请求记录，包括类型、耗时和状态等详细信息</p>
        </div>

        {/* ===== Tab 筛选栏 ===== */}
        <div className="flex items-center justify-between">
          {/* 左侧 Tab 按钮组 */}
          <div className="flex items-center gap-2">
            {TAB_ITEMS.map((tab) => {
              const Icon = tab.icon;
              const isActive = filterType === tab.value;
              return (
                <button
                  key={tab.value}
                  onClick={() => { setFilterType(tab.value); setPage(0); }}
                  className={`
                    inline-flex items-center gap-1.5 px-3.5 py-2 rounded-lg text-sm font-medium
                    transition-all duration-150 border
                    ${isActive
                      ? "bg-blue-600 text-white border-blue-600 shadow-sm dark:bg-blue-800 dark:border-blue-800"
                      : "bg-background text-muted-foreground border-border hover:bg-muted hover:text-foreground"
                    }
                  `}
                >
                  <Icon className="h-3.5 w-3.5" />
                  {tab.label}
                </button>
              );
            })}
          </div>

          {/* 右侧操作按钮 */}
          <div className="flex items-center gap-2">
            <Button
              variant="outline"
              size="sm"
              className={`h-9 gap-1.5 ${
                showFilter || hasDateFilter
                  ? "border-blue-500 text-blue-600 bg-blue-50 dark:border-blue-400 dark:text-blue-400 dark:bg-blue-950/30"
                  : ""
              }`}
              onClick={() => setShowFilter((v) => !v)}
            >
              <SlidersHorizontal className="h-3.5 w-3.5" />
              筛选
              {hasDateFilter && (
                <span className="ml-1 h-1.5 w-1.5 rounded-full bg-blue-500 dark:bg-blue-400" />
              )}
            </Button>
            <Button
              variant="outline"
              size="sm"
              className="h-9 gap-1.5"
              onClick={fetchLogs}
            >
              <RefreshCw className={`h-3.5 w-3.5 ${loading ? "animate-spin" : ""}`} />
              刷新
            </Button>
          </div>
        </div>

        {/* ===== 时间范围筛选面板 ===== */}
        {showFilter && (
          <div className="rounded-lg border bg-card p-4 shadow-sm animate-in slide-in-from-top-2 duration-200">
            <div className="flex items-center gap-2 mb-3">
              <CalendarDays className="h-4 w-4 text-muted-foreground" />
              <span className="text-sm font-medium text-muted-foreground">时间范围</span>
            </div>
            <div className="flex items-center gap-3 flex-wrap">
              {/* 起始日期 */}
              <input
                type="date"
                value={dateFrom}
                onChange={(e) => {
                  setDateFrom(e.target.value);
                  setActiveQuick("");
                  setPage(0);
                }}
                className="h-9 rounded-md border border-input bg-background px-3 text-sm shadow-sm transition-colors focus:outline-none focus:ring-1 focus:ring-ring"
                placeholder="年/月/日"
              />
              <span className="text-sm text-muted-foreground">至</span>
              {/* 结束日期 */}
              <input
                type="date"
                value={dateTo}
                onChange={(e) => {
                  setDateTo(e.target.value);
                  setActiveQuick("");
                  setPage(0);
                }}
                className="h-9 rounded-md border border-input bg-background px-3 text-sm shadow-sm transition-colors focus:outline-none focus:ring-1 focus:ring-ring"
                placeholder="年/月/日"
              />

              {/* 快捷按钮 */}
              <div className="flex items-center gap-2 ml-2">
                {[
                  { key: "today", label: "今天" },
                  { key: "7d", label: "近7天" },
                  { key: "30d", label: "近30天" },
                ].map((item) => (
                  <button
                    key={item.key}
                    onClick={() => handleQuickDate(item.key)}
                    className={`
                      inline-flex items-center px-3 py-1.5 rounded-md text-sm font-medium
                      transition-all duration-150 border
                      ${activeQuick === item.key
                        ? "bg-blue-600 text-white border-blue-600 dark:bg-blue-800 dark:border-blue-800"
                        : "bg-background text-foreground border-border hover:bg-muted"
                      }
                    `}
                  >
                    {item.label}
                  </button>
                ))}
                {/* 清除按钮 */}
                {hasDateFilter && (
                  <button
                    onClick={clearDateFilter}
                    className="inline-flex items-center gap-1 px-3 py-1.5 rounded-md text-sm font-medium border border-border bg-background text-muted-foreground hover:bg-muted hover:text-foreground transition-all duration-150"
                  >
                    <X className="h-3.5 w-3.5" />
                    清除
                  </button>
                )}
              </div>
            </div>
          </div>
        )}

        {/* ===== 柱状图（无 Card 包裹，扁平嵌入） ===== */}
        {chartData.length > 0 && (
          <div className="w-full pt-2 pb-4">
            <ResponsiveContainer width="100%" height={180}>
              <BarChart data={chartData} barCategoryGap="60%">
                <CartesianGrid
                  strokeDasharray="3 3"
                  stroke="hsl(var(--border))"
                  vertical={false}
                />
                <XAxis
                  dataKey="dateLabel"
                  tick={{ fontSize: 11, fill: "hsl(var(--muted-foreground))" }}
                  tickLine={false}
                  axisLine={{ stroke: "hsl(var(--border))" }}
                  interval={chartData.length > 14 ? Math.ceil(chartData.length / 10) - 1 : 0}
                />
                <YAxis
                  allowDecimals={false}
                  tick={{ fontSize: 11, fill: "hsl(var(--muted-foreground))" }}
                  tickLine={false}
                  axisLine={false}
                  width={30}
                />
                <RechartsTooltip
                  cursor={{ fill: "hsl(var(--muted))", opacity: 0.3 }}
                  content={({ active, payload }: any) => {
                    if (!active || !payload || !payload[0]) return null;
                    const data = payload[0].payload;
                    const rawDate = data.date;
                    const types = stats?.types || [];
                    const totalCount = data._total || 0;

                    // 格式化日期为 dd/MM/yyyy
                    let formattedDate = rawDate;
                    try {
                      const d = new Date(rawDate);
                      formattedDate = `${String(d.getDate()).padStart(2, "0")}/${String(d.getMonth() + 1).padStart(2, "0")}/${d.getFullYear()}`;
                    } catch { /* keep raw */ }

                    return (
                      <div className="rounded-lg border bg-background p-3 shadow-lg min-w-[160px]">
                        <p className="text-xs text-muted-foreground mb-2.5 font-medium">
                          {formattedDate}
                        </p>
                        {/* 总请求数 */}
                        <div className="flex items-center justify-between gap-4 mb-1.5">
                          <div className="flex items-center gap-2">
                            <span
                              className="h-2.5 w-2.5 rounded-sm shrink-0"
                              style={{ background: "#a78bfa" }}
                            />
                            <span className="text-sm font-medium">总请求</span>
                          </div>
                          <span className="text-sm font-bold">{totalCount}</span>
                        </div>
                        {/* 各类型明细 */}
                        {types.map((t: string) => {
                          const count = Number(data[t]) || 0;
                          if (count === 0) return null;
                          return (
                            <div
                              key={t}
                              className="flex items-center justify-between gap-4"
                            >
                              <div className="flex items-center gap-2">
                                <span
                                  className="h-2.5 w-2.5 rounded-sm shrink-0"
                                  style={{ background: TYPE_HEX[t] || "#94a3b8" }}
                                />
                                <span className="text-xs text-muted-foreground">
                                  {t}
                                </span>
                              </div>
                              <span className="text-xs font-medium">{count}</span>
                            </div>
                          );
                        })}
                      </div>
                    );
                  }}
                />
                <Bar
                  dataKey="_total"
                  fill="#a78bfa"
                  radius={[3, 3, 0, 0]}
                  maxBarSize={40}
                />
              </BarChart>
            </ResponsiveContainer>
          </div>
        )}

        {/* ===== 请求日志表格 ===== */}
        <Card className="border shadow-sm">
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
                    <TableRow className="hover:bg-transparent">
                      <TableHead className="w-[140px]">
                        <div className="flex items-center gap-1.5">
                          <Clock className="h-3.5 w-3.5 text-muted-foreground" />
                          <span>时间</span>
                        </div>
                      </TableHead>
                      <TableHead className="w-[120px]">
                        <div className="flex items-center gap-1.5">
                          <SlidersHorizontal className="h-3.5 w-3.5 text-muted-foreground" />
                          <span>类型</span>
                        </div>
                      </TableHead>
                      <TableHead className="w-[200px]">
                        <div className="flex items-center gap-1.5">
                          <User className="h-3.5 w-3.5 text-muted-foreground" />
                          <span>实体</span>
                        </div>
                      </TableHead>
                      <TableHead className="w-[120px]">
                        <div className="flex items-center gap-1.5">
                          <ListOrdered className="h-3.5 w-3.5 text-muted-foreground" />
                          <span>事件</span>
                        </div>
                      </TableHead>
                      <TableHead className="w-[140px]">
                        <div className="flex items-center gap-1.5">
                          <Timer className="h-3.5 w-3.5 text-muted-foreground" />
                          <span>耗时</span>
                        </div>
                      </TableHead>
                      <TableHead className="w-[80px] text-center">
                        <div className="flex items-center justify-center gap-1.5">
                          <CheckCircle className="h-3.5 w-3.5 text-muted-foreground" />
                          <span>状态</span>
                        </div>
                      </TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {logs.map((log) => {
                      const badgeStyle = TYPE_BADGE_STYLES[log.request_type] || "bg-muted text-muted-foreground";
                      const isSuccess = log.status_code >= 200 && log.status_code < 400;
                      // 判断事件类型：添加类型显示 +1，其他显示 —
                      const eventDisplay = log.request_type === "添加" ? (
                        <span className="inline-flex items-center gap-0.5 text-sm text-muted-foreground border rounded-md px-2 py-0.5">
                          + 1
                        </span>
                      ) : (
                        <span className="text-sm text-muted-foreground">—</span>
                      );

                      return (
                        <TableRow key={log.id}>
                          {/* Time */}
                          <TableCell>
                            <Tooltip>
                              <TooltipTrigger asChild>
                                <span className="text-sm text-muted-foreground cursor-help">
                                  {formatRelativeTime(log.timestamp)}
                                </span>
                              </TooltipTrigger>
                              <TooltipContent>
                                {new Date(log.timestamp).toLocaleString("zh-CN")}
                              </TooltipContent>
                            </Tooltip>
                          </TableCell>
                          {/* Type */}
                          <TableCell>
                            <span className={`inline-flex items-center rounded px-2.5 py-1 text-xs font-semibold ${badgeStyle}`}>
                              {log.request_type}
                            </span>
                          </TableCell>
                          {/* Entities */}
                          <TableCell>
                            {log.user_id ? (
                              <div className="flex items-center gap-1.5">
                                <User className="h-3.5 w-3.5 text-muted-foreground" />
                                <span className="text-sm">{log.user_id}</span>
                              </div>
                            ) : (
                              <span className="text-sm text-muted-foreground">—</span>
                            )}
                          </TableCell>
                          {/* Event */}
                          <TableCell>
                            {eventDisplay}
                          </TableCell>
                          {/* Latency */}
                          <TableCell>
                            <span className={`text-sm ${
                              log.latency_ms > 5000 ? "text-red-600 dark:text-red-400" :
                              log.latency_ms > 1000 ? "text-yellow-600 dark:text-yellow-400" :
                              "text-muted-foreground"
                            }`}>
                              {formatLatency(log.latency_ms)}
                            </span>
                          </TableCell>
                          {/* Status */}
                          <TableCell className="text-center">
                            {isSuccess ? (
                              <CheckCircle className="h-4 w-4 text-green-500 dark:text-green-400 mx-auto" />
                            ) : (
                              <Tooltip>
                                <TooltipTrigger asChild>
                                  <XCircle className="h-4 w-4 text-red-500 dark:text-red-400 mx-auto cursor-help" />
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

                      <span className="text-sm font-medium px-2">
                        {page + 1} / {totalPages}
                      </span>

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
                <LayoutGrid className="mb-4 h-16 w-16 text-muted-foreground/30" />
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
