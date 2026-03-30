"use client";

import React from "react";
import {
  PieChart,
  Pie,
  Cell,
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
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import type { StatsResponse } from "@/lib/api";
import { CATEGORY_LIST, STATE_LIST } from "@/lib/constants";

// 分类对应的 hex 颜色
const CATEGORY_COLORS: Record<string, string> = {
  personal: "#3b82f6",
  work: "#a855f7",
  health: "#22c55e",
  finance: "#f97316",
  travel: "#06b6d4",
  education: "#6366f1",
  preferences: "#ec4899",
  relationships: "#ef4444",
};

const STATE_COLORS: Record<string, string> = {
  active: "#22c55e",
  paused: "#eab308",
  deleted: "#ef4444",
};

interface StatsChartsProps {
  stats: StatsResponse;
}

export function StatsCharts({ stats }: StatsChartsProps) {
  // 分类饼图数据
  const categoryData = CATEGORY_LIST
    .map((cat) => ({
      name: cat.label,
      value: stats.category_distribution[cat.value] || 0,
      color: CATEGORY_COLORS[cat.value] || "#94a3b8",
    }))
    .filter((d) => d.value > 0);

  // 状态饼图数据
  const stateData = STATE_LIST
    .map((s) => ({
      name: s.label,
      value: stats.state_distribution[s.value] || 0,
      color: STATE_COLORS[s.value] || "#94a3b8",
    }))
    .filter((d) => d.value > 0);

  // 趋势数据 - 截取最近 14 天并格式化日期
  const trendData = (stats.daily_trend || []).slice(-14).map((d) => ({
    date: d.date.slice(5), // "2026-03-27" → "03-27"
    count: d.count,
  }));

  const hasAnyCategoryData = categoryData.length > 0;
  const hasAnyStateData = stateData.length > 0;
  const hasAnyTrendData = trendData.some((d) => d.count > 0);

  return (
    <div className="grid gap-6 md:grid-cols-2">
      {/* 分类分布饼图 */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base">分类分布</CardTitle>
          <CardDescription>各分类的记忆占比</CardDescription>
        </CardHeader>
        <CardContent>
          {hasAnyCategoryData ? (
            <div className="flex items-center gap-4">
              <div className="w-[180px] shrink-0">
                <ResponsiveContainer width="100%" height={180}>
                  <PieChart>
                    <Pie
                      data={categoryData}
                      cx="50%"
                      cy="50%"
                      innerRadius={45}
                      outerRadius={75}
                      paddingAngle={3}
                      dataKey="value"
                    >
                      {categoryData.map((entry, index) => (
                        <Cell key={`cat-${index}`} fill={entry.color} />
                      ))}
                    </Pie>
                    <Tooltip
                      formatter={(value: any, name: any) => [`${value} 条`, name]}
                      contentStyle={{
                        borderRadius: "8px",
                        border: "1px solid hsl(var(--border))",
                        background: "hsl(var(--background))",
                        color: "hsl(var(--foreground))",
                      }}
                    />
                  </PieChart>
                </ResponsiveContainer>
              </div>
              {/* 右侧两列图例 */}
              <div className="grid grid-cols-2 gap-x-4 gap-y-1 flex-1 min-w-0">
                {categoryData.map((entry, index) => (
                  <div key={`legend-${index}`} className="flex items-center gap-1.5">
                    <span
                      className="inline-block h-2 w-2 rounded-sm shrink-0"
                      style={{ background: entry.color }}
                    />
                    <span className="text-xs text-muted-foreground truncate">
                      {entry.name} ({entry.value})
                    </span>
                  </div>
                ))}
              </div>
            </div>
          ) : (
            <div className="flex items-center justify-center h-[220px] text-sm text-muted-foreground">
              暂无分类数据
            </div>
          )}
        </CardContent>
      </Card>

      {/* 状态分布饼图 */}
      {hasAnyStateData && (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">状态分布</CardTitle>
            <CardDescription>各状态的记忆数量</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="flex items-center gap-4">
              <div className="w-[180px] shrink-0">
                <ResponsiveContainer width="100%" height={180}>
                  <PieChart>
                    <Pie
                      data={stateData}
                      cx="50%"
                      cy="50%"
                      innerRadius={45}
                      outerRadius={75}
                      paddingAngle={3}
                      dataKey="value"
                    >
                      {stateData.map((entry, index) => (
                        <Cell key={`state-${index}`} fill={entry.color} />
                      ))}
                    </Pie>
                    <Tooltip
                      formatter={(value: any, name: any) => [`${value} 条`, name]}
                      contentStyle={{
                        borderRadius: "8px",
                        border: "1px solid hsl(var(--border))",
                        background: "hsl(var(--background))",
                        color: "hsl(var(--foreground))",
                      }}
                    />
                  </PieChart>
                </ResponsiveContainer>
              </div>
              {/* 右侧图例 */}
              <div className="space-y-2 flex-1">
                {stateData.map((entry, index) => (
                  <div key={`slegend-${index}`} className="flex items-center gap-2">
                    <span
                      className="inline-block h-2.5 w-2.5 rounded-sm shrink-0"
                      style={{ background: entry.color }}
                    />
                    <span className="text-sm text-muted-foreground">
                      {entry.name} ({entry.value})
                    </span>
                  </div>
                ))}
              </div>
            </div>
          </CardContent>
        </Card>
      )}

      {/* 记忆增长趋势折线图 */}
      <Card className="md:col-span-2">
        <CardHeader>
          <CardTitle className="text-base">增长趋势</CardTitle>
          <CardDescription>近 14 天每日新增记忆</CardDescription>
        </CardHeader>
        <CardContent>
          {hasAnyTrendData ? (
            <ResponsiveContainer width="100%" height={220}>
              <LineChart data={trendData}>
                <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
                <XAxis
                  dataKey="date"
                  tick={{ fontSize: 11, fill: "hsl(var(--muted-foreground))" }}
                  tickLine={false}
                  axisLine={{ stroke: "hsl(var(--border))" }}
                />
                <YAxis
                  allowDecimals={false}
                  tick={{ fontSize: 11, fill: "hsl(var(--muted-foreground))" }}
                  tickLine={false}
                  axisLine={{ stroke: "hsl(var(--border))" }}
                />
                <Tooltip
                  formatter={(value: any) => [`${value} 条`, "新增"]}
                  labelFormatter={(label: any) => `日期: ${label}`}
                  contentStyle={{
                    borderRadius: "8px",
                    border: "1px solid hsl(var(--border))",
                    background: "hsl(var(--background))",
                    color: "hsl(var(--foreground))",
                  }}
                />
                <Line
                  type="monotone"
                  dataKey="count"
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
    </div>
  );
}
