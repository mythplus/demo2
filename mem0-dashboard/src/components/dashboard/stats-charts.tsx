"use client";

import React, { useState } from "react";
import Link from "next/link";
import { ArrowRight } from "lucide-react";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from "recharts";

/* eslint-disable @typescript-eslint/no-explicit-any */
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Switch } from "@/components/ui/switch";
import type { StatsResponse, RequestLogsStats } from "@/lib/api";

// ============ 旧英文类型 → 中文映射（兼容历史数据） ============
const LEGACY_TYPE_MAP: Record<string, string> = {
  "POST": "添加",
  "GET": "获取全部",
  "PUT": "更新",
  "DELETE": "删除",
};

/** 将可能的旧英文类型名归一化为中文 */
function normalizeType(type: string): string {
  return LEGACY_TYPE_MAP[type] || type;
}

// ============ 请求类型颜色 ============
const REQUEST_TYPE_COLORS: Record<string, string> = {
  "添加": "#22c55e",
  "搜索": "#3b82f6",
  "获取全部": "#94a3b8",
  "删除": "#ef4444",
  "更新": "#f59e0b",
  "对话": "#8b5cf6",
};

// ============ 工具函数 ============
function formatDate(dateStr: string): string {
  if (!dateStr) return "";
  // "2026-04-15" → "04/15"  or  "2026-04-15T10:30" → "04/15 10:30"
  const d = dateStr.slice(5, 10).replace("-", "/");
  return d;
}

// ============ 通用 Tooltip 样式 ============
const tooltipStyle = {
  borderRadius: "8px",
  border: "1px solid hsl(var(--border))",
  background: "hsl(var(--background))",
  color: "hsl(var(--foreground))",
  fontSize: "12px",
};

// ============ 接口 ============
interface StatsChartsProps {
  stats: StatsResponse;
  requestStats?: RequestLogsStats | null;
}

export function StatsCharts({ stats, requestStats }: StatsChartsProps) {
  const [showRequestDetail, setShowRequestDetail] = useState(false);

  // ============ 请求趋势数据（归一化旧英文类型名） ============
  const requestTotal = requestStats?.total ?? 0;
  const rawTypes = requestStats?.types ?? [];
  // 去重归一化：将旧英文类型映射为中文后去重
  const requestTypes = [...new Set(rawTypes.map(normalizeType))];
  const requestTrend = (requestStats?.daily_trend ?? []).map((d: any) => {
    const row: any = { date: formatDate(d.date || d.time || "") };
    // 将旧英文 key 的值合并到中文 key 上
    for (const rawKey of Object.keys(d)) {
      if (rawKey === "date" || rawKey === "time") continue;
      const normalized = normalizeType(rawKey);
      row[normalized] = (row[normalized] || 0) + Number(d[rawKey] || 0);
    }
    // 计算 total：所有类型字段求和
    if (!row.total) {
      let sum = 0;
      for (const t of requestTypes) {
        sum += Number(row[t] || 0);
      }
      row.total = sum;
    }
    return row;
  });

  // ============ 新增记忆趋势数据 ============
  const memoryTrend = (stats.daily_trend || []).slice(-30).map((d) => ({
    date: formatDate(d.date),
    count: d.count,
  }));
  const memoryTotal = memoryTrend.reduce((sum, d) => sum + d.count, 0);

  return (
    <div className="grid gap-4 md:grid-cols-2">
      {/* 左：新增记忆趋势 */}
      <Card>
        <CardHeader className="flex flex-row items-center justify-between pb-2">
          <div>
            <CardTitle className="text-base">新增记忆</CardTitle>
            <p className="text-2xl font-semibold mt-1">{memoryTotal}</p>
          </div>
          <Link href="/memories">
            <Button variant="outline" size="sm" className="h-7 text-xs gap-1">
              查看记忆
              <ArrowRight className="h-3 w-3" />
            </Button>
          </Link>
        </CardHeader>
        <CardContent>
          {memoryTrend.some((d) => d.count > 0) ? (
            <ResponsiveContainer width="100%" height={220}>
              <LineChart data={memoryTrend} margin={{ top: 5, right: 10, bottom: 0, left: -20 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
                <XAxis
                  dataKey="date"
                  tick={{ fontSize: 10, fill: "hsl(var(--muted-foreground))" }}
                  tickLine={false}
                  axisLine={{ stroke: "hsl(var(--border))" }}
                />
                <YAxis
                  allowDecimals={false}
                  tick={{ fontSize: 10, fill: "hsl(var(--muted-foreground))" }}
                  tickLine={false}
                  axisLine={{ stroke: "hsl(var(--border))" }}
                />
                <Tooltip
                  formatter={(value: any) => [`${value} 条`, "新增"]}
                  labelFormatter={(label: any) => `日期: ${label}`}
                  contentStyle={tooltipStyle}
                />
                <Line
                  type="monotone"
                  dataKey="count"
                  name="新增记忆"
                  stroke="hsl(var(--primary))"
                  strokeWidth={2}
                  dot={{ fill: "hsl(var(--primary))", strokeWidth: 0, r: 3 }}
                  activeDot={{ r: 5, strokeWidth: 0 }}
                />
              </LineChart>
            </ResponsiveContainer>
          ) : (
            <div className="flex items-center justify-center h-[220px] text-sm text-muted-foreground">
              暂无趋势数据
            </div>
          )}
        </CardContent>
      </Card>

      {/* 右：请求趋势 */}
      <Card>
        <CardHeader className="flex flex-row items-center justify-between pb-2">
          <div>
            <CardTitle className="text-base">请求</CardTitle>
            <p className="text-2xl font-semibold mt-1">{requestTotal}</p>
          </div>
          <Link href="/requests">
            <Button variant="outline" size="sm" className="h-7 text-xs gap-1">
              查看请求
              <ArrowRight className="h-3 w-3" />
            </Button>
          </Link>
        </CardHeader>
        <CardContent>
          {requestTrend.length > 0 ? (
            <ResponsiveContainer width="100%" height={220}>
              <LineChart data={requestTrend} margin={{ top: 5, right: 10, bottom: 0, left: -20 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
                <XAxis
                  dataKey="date"
                  tick={{ fontSize: 10, fill: "hsl(var(--muted-foreground))" }}
                  tickLine={false}
                  axisLine={{ stroke: "hsl(var(--border))" }}
                />
                <YAxis
                  allowDecimals={false}
                  tick={{ fontSize: 10, fill: "hsl(var(--muted-foreground))" }}
                  tickLine={false}
                  axisLine={{ stroke: "hsl(var(--border))" }}
                />
                <Tooltip contentStyle={tooltipStyle} />
                {!showRequestDetail ? (
                  <Line
                    type="monotone"
                    dataKey="total"
                    name="总请求数"
                    stroke="#22c55e"
                    strokeWidth={2}
                    dot={false}
                    activeDot={{ r: 4, strokeWidth: 0 }}
                  />
                ) : (
                  requestTypes.map((type) => (
                    <Line
                      key={type}
                      type="monotone"
                      dataKey={type}
                      name={type}
                      stroke={REQUEST_TYPE_COLORS[type] || "#94a3b8"}
                      strokeWidth={2}
                      dot={false}
                      activeDot={{ r: 4, strokeWidth: 0 }}
                    />
                  ))
                )}
              </LineChart>
            </ResponsiveContainer>
          ) : (
            <div className="flex items-center justify-center h-[220px] text-sm text-muted-foreground">
              暂无请求数据
            </div>
          )}
          {/* 底部：类型标签 + 查看细分开关 */}
          <div className="flex items-center justify-between mt-2 pt-2 border-t">
            <div className="flex items-center gap-3 flex-wrap">
              {showRequestDetail && requestTypes.map((type) => (
                <div key={type} className="flex items-center gap-1">
                  <span
                    className="inline-block h-2 w-2 rounded-full"
                    style={{ background: REQUEST_TYPE_COLORS[type] || "#94a3b8" }}
                  />
                  <span className="text-xs text-muted-foreground">{type}</span>
                </div>
              ))}
              {!showRequestDetail && (
                <div className="flex items-center gap-1">
                  <span className="inline-block h-2 w-2 rounded-full" style={{ background: "#22c55e" }} />
                  <span className="text-xs text-muted-foreground">总请求数</span>
                </div>
              )}
            </div>
            <div className="flex items-center gap-2 shrink-0">
              <span className="text-xs text-muted-foreground">查看细分</span>
              <Switch
                checked={showRequestDetail}
                onCheckedChange={setShowRequestDetail}
                className="scale-75"
              />
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
