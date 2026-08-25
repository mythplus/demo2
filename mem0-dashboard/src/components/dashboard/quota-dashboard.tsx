"use client";

import React, { useState, useEffect, useCallback } from "react";
import { Activity, Database, Zap, TrendingUp } from "lucide-react";
import { getQuotaUsageApi, type QuotaUsage } from "@/lib/api/quota-api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";

export function QuotaDashboard() {
  const [usage, setUsage] = useState<QuotaUsage | null>(null);
  const [loading, setLoading] = useState(true);

  const fetchUsage = useCallback(async () => {
    try {
      const data = await getQuotaUsageApi();
      setUsage(data);
    } catch {
      // 静默失败（可能未启用认证）
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchUsage();
    const interval = setInterval(fetchUsage, 30000);
    return () => clearInterval(interval);
  }, [fetchUsage]);

  if (loading || !usage) {
    return null;
  }

  const apiPercent = usage.limits.max_api_calls_per_day > 0
    ? Math.min((usage.today_api_call_count / usage.limits.max_api_calls_per_day) * 100, 100)
    : 0;

  return (
    <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
      {/* 今日API调用 */}
      <Card>
        <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
          <CardTitle className="text-sm font-medium text-muted-foreground">
            今日 API 调用
          </CardTitle>
          <Zap className="h-4 w-4 text-muted-foreground" />
        </CardHeader>
        <CardContent>
          <div className="text-2xl font-bold">{usage.today_api_call_count}</div>
          <div className="mt-2">
            <Progress value={apiPercent} className="h-1.5" />
            <p className="mt-1 text-xs text-muted-foreground">
              上限 {usage.limits.max_api_calls_per_day} · {apiPercent.toFixed(0)}%
            </p>
          </div>
        </CardContent>
      </Card>

      {/* 今日记忆写入 */}
      <Card>
        <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
          <CardTitle className="text-sm font-medium text-muted-foreground">
            今日记忆写入
          </CardTitle>
          <Database className="h-4 w-4 text-muted-foreground" />
        </CardHeader>
        <CardContent>
          <div className="text-2xl font-bold">{usage.today_memory_count}</div>
          <p className="mt-1 text-xs text-muted-foreground">
            上限 {usage.limits.max_memories}
          </p>
        </CardContent>
      </Card>

      {/* 总API调用 */}
      <Card>
        <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
          <CardTitle className="text-sm font-medium text-muted-foreground">
            总 API 调用
          </CardTitle>
          <TrendingUp className="h-4 w-4 text-muted-foreground" />
        </CardHeader>
        <CardContent>
          <div className="text-2xl font-bold">{usage.total_api_call_count}</div>
          <p className="mt-1 text-xs text-muted-foreground">累计统计</p>
        </CardContent>
      </Card>

      {/* 套餐信息 */}
      <Card>
        <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
          <CardTitle className="text-sm font-medium text-muted-foreground">
            当前套餐
          </CardTitle>
          <Activity className="h-4 w-4 text-muted-foreground" />
        </CardHeader>
        <CardContent>
          <div className="text-2xl font-bold uppercase">{usage.limits.plan}</div>
          <p className="mt-1 text-xs text-muted-foreground">
            限流 {usage.limits.rate_limit_per_minute}/min
          </p>
        </CardContent>
      </Card>
    </div>
  );
}
