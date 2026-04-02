"use client";

import React, { useEffect, useState } from "react";
import {
  Settings,
  CheckCircle,
  XCircle,
  Loader2,
  RotateCcw,
  Sun,
  Moon,
  SlidersHorizontal,
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
import { Separator } from "@/components/ui/separator";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { mem0Api } from "@/lib/api";
import { usePreferences } from "@/hooks/use-preferences";

export default function SettingsPage() {
  const { preferences, savePreferences, resetPreferences } = usePreferences();

  // API 连接测试
  const [apiUrl, setApiUrl] = useState("");
  const [testStatus, setTestStatus] = useState<
    "idle" | "testing" | "success" | "error"
  >("idle");
  const [apiInfo, setApiInfo] = useState<string>("");

  useEffect(() => {
    setApiUrl(preferences.apiUrl);
  }, [preferences.apiUrl]);

  // 测试连接
  const handleTestConnection = async () => {
    setTestStatus("testing");
    setApiInfo("");
    try {
      const isConnected = await mem0Api.healthCheck();
      if (isConnected) {
        setTestStatus("success");
        // 尝试获取记忆数量作为额外信息
        try {
          const memories = await mem0Api.getMemories();
          const count = Array.isArray(memories) ? memories.length : 0;
          setApiInfo(`当前共有 ${count} 条记忆数据`);
        } catch {
          setApiInfo("连接成功，但无法获取记忆数据");
        }
      } else {
        setTestStatus("error");
      }
    } catch {
      setTestStatus("error");
    }
  };

  // 主题图标映射
  const themeIcons = {
    light: Sun,
    dark: Moon,
  };

  return (
    <div className="space-y-6">
      {/* 页面头部 */}
      <div>
        <h2 className="text-2xl font-bold tracking-tight">系统设置</h2>
        <p className="text-muted-foreground">
          配置 API 连接、显示偏好
        </p>
      </div>

      {/* API 连接配置 */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Settings className="h-5 w-5" />
            API 连接配置
          </CardTitle>
          <CardDescription>
            配置 Mem0 API Server 的连接地址
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="space-y-2">
            <label className="text-sm font-medium">API 地址</label>
            <div className="flex gap-3">
              <Input
                value={apiUrl}
                onChange={(e) => setApiUrl(e.target.value)}
                placeholder="http://localhost:8080"
                className="flex-1"
              />
              <Button onClick={handleTestConnection} variant="outline">
                {testStatus === "testing" ? (
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                ) : null}
                测试连接
              </Button>
            </div>

            {testStatus === "success" && (
              <div className="space-y-1">
                <div className="flex items-center gap-2 text-sm text-green-600">
                  <CheckCircle className="h-4 w-4" />
                  连接成功！API Server 运行正常
                </div>
                {apiInfo && (
                  <p className="text-xs text-muted-foreground ml-6">
                    {apiInfo}
                  </p>
                )}
              </div>
            )}
            {testStatus === "error" && (
              <div className="flex items-center gap-2 text-sm text-red-600 dark:text-red-400">
                <XCircle className="h-4 w-4" />
                连接失败，请检查 API 地址和服务状态
              </div>
            )}
          </div>

          <Separator />

          <div className="rounded-lg bg-muted px-4 py-3">
            <p className="text-xs text-muted-foreground">
              💡 API 地址通过环境变量{" "}
              <code className="rounded bg-background px-1 py-0.5">
                NEXT_PUBLIC_MEM0_API_URL
              </code>{" "}
              配置。修改后需要重启前端服务才能生效。启动 Mem0 API Server：
              <code className="ml-1 rounded bg-background px-1 py-0.5">
                mem0 server start --port 8080
              </code>
            </p>
          </div>
        </CardContent>
      </Card>

      {/* 显示偏好 */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <SlidersHorizontal className="h-5 w-5" />
            显示偏好
          </CardTitle>
          <CardDescription>
            自定义页面显示方式和默认行为
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-6">
          {/* 每页显示条数 */}
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium">每页显示条数</p>
              <p className="text-xs text-muted-foreground">
                记忆列表每页显示的记录数量
              </p>
            </div>
            <Select
              value={String(preferences.pageSize)}
              onValueChange={(value) =>
                savePreferences({ pageSize: parseInt(value) })
              }
            >
              <SelectTrigger className="w-[120px]">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="5">5 条</SelectItem>
                <SelectItem value="10">10 条</SelectItem>
                <SelectItem value="20">20 条</SelectItem>
                <SelectItem value="50">50 条</SelectItem>
              </SelectContent>
            </Select>
          </div>

          <Separator />

          {/* 默认排序 */}
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium">默认排序方式</p>
              <p className="text-xs text-muted-foreground">
                记忆列表的默认排序规则
              </p>
            </div>
            <Select
              value={preferences.sortOrder}
              onValueChange={(value: "newest" | "oldest") =>
                savePreferences({ sortOrder: value })
              }
            >
              <SelectTrigger className="w-[120px]">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="newest">最新优先</SelectItem>
                <SelectItem value="oldest">最早优先</SelectItem>
              </SelectContent>
            </Select>
          </div>

          <Separator />

          {/* 主题模式 */}
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium">主题模式</p>
              <p className="text-xs text-muted-foreground">
                选择界面的颜色主题
              </p>
            </div>
            <div className="flex gap-1">
              {(["light", "dark"] as const).map((mode) => {
                const Icon = themeIcons[mode];
                const labels = {
                  light: "浅色",
                  dark: "深色",
                };
                return (
                  <Button
                    key={mode}
                    variant={
                      preferences.themeMode === mode ? "default" : "outline"
                    }
                    size="sm"
                    onClick={() => savePreferences({ themeMode: mode })}
                    className="gap-1.5"
                  >
                    <Icon className="h-4 w-4" />
                    {labels[mode]}
                  </Button>
                );
              })}
            </div>
          </div>

          <Separator />

          {/* 重置 */}
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium">重置偏好设置</p>
              <p className="text-xs text-muted-foreground">
                恢复所有设置为默认值
              </p>
            </div>
            <Button variant="outline" size="sm" onClick={resetPreferences}>
              <RotateCcw className="mr-2 h-4 w-4" />
              重置
            </Button>
          </div>
        </CardContent>
      </Card>

      {/* 关于信息 */}
      <Card>
        <CardHeader>
          <CardTitle>关于</CardTitle>
        </CardHeader>
        <CardContent className="space-y-2 text-sm text-muted-foreground">
          <p>
            <strong>图谱记忆</strong> — 基于 Mem0 开源版 API
            的前端管理界面
          </p>
          <p>技术栈：Next.js 14 + shadcn/ui + Tailwind CSS</p>
          <p>
            后端：
            <a
              href="https://github.com/mem0ai/mem0"
              target="_blank"
              rel="noopener noreferrer"
              className="text-primary hover:underline"
            >
              mem0ai/mem0
            </a>{" "}
            (开源版)
          </p>
          <div className="flex gap-2 mt-2">
            <Badge variant="secondary">v1.0.0</Badge>
            <Badge variant="outline">Next.js 14</Badge>
            <Badge variant="outline">TypeScript</Badge>
          </div>
        </CardContent>
      </Card>

    </div>
  );
}
