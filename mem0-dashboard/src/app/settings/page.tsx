"use client";

import React, { useEffect, useState, useCallback } from "react";
import {
  Settings,
  CheckCircle,
  XCircle,
  Loader2,
  RotateCcw,
  Sun,
  Moon,
  SlidersHorizontal,
  Brain,
  Cpu,
  Database,
  Network,
  Zap,
  RefreshCw,
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
import type { ConfigInfoResponse, ServiceTestResponse } from "@/lib/api";
import { usePreferences } from "@/hooks/use-preferences";

export default function SettingsPage() {
  const { preferences, savePreferences, resetPreferences } = usePreferences();
  const apiUrl = process.env.NEXT_PUBLIC_MEM0_API_URL || "http://localhost:8080";

  // API 连接测试
  const [testStatus, setTestStatus] = useState<
    "idle" | "testing" | "success" | "error"
  >("idle");
  const [apiInfo, setApiInfo] = useState<string>("");

  // 模型与服务配置
  const [configInfo, setConfigInfo] = useState<ConfigInfoResponse | null>(null);
  const [configLoading, setConfigLoading] = useState(false);
  const [llmTestStatus, setLlmTestStatus] = useState<"idle" | "testing" | "success" | "error">("idle");
  const [llmTestResult, setLlmTestResult] = useState<ServiceTestResponse | null>(null);
  const [embedderTestStatus, setEmbedderTestStatus] = useState<"idle" | "testing" | "success" | "error">("idle");
  const [embedderTestResult, setEmbedderTestResult] = useState<ServiceTestResponse | null>(null);

  // 获取配置信息
  const fetchConfigInfo = useCallback(async () => {
    setConfigLoading(true);
    // 刷新时重置测试状态
    setLlmTestStatus("idle");
    setLlmTestResult(null);
    setEmbedderTestStatus("idle");
    setEmbedderTestResult(null);
    try {
      const info = await mem0Api.getConfigInfo();
      setConfigInfo(info);
    } catch {
      setConfigInfo(null);
    } finally {
      setConfigLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchConfigInfo();
  }, [fetchConfigInfo]);

  // 测试 LLM 连接
  const handleTestLLM = async () => {
    setLlmTestStatus("testing");
    setLlmTestResult(null);
    try {
      const result = await mem0Api.testLLMConnection();
      setLlmTestResult(result);
      setLlmTestStatus(result.status === "connected" ? "success" : "error");
    } catch {
      setLlmTestStatus("error");
      setLlmTestResult(null);
    }
  };

  // 测试 Embedder 连接
  const handleTestEmbedder = async () => {
    setEmbedderTestStatus("testing");
    setEmbedderTestResult(null);
    try {
      const result = await mem0Api.testEmbedderConnection();
      setEmbedderTestResult(result);
      setEmbedderTestStatus(result.status === "connected" ? "success" : "error");
    } catch {
      setEmbedderTestStatus("error");
      setEmbedderTestResult(null);
    }
  };

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
        <p className="text-sm text-muted-foreground">
          查看 API 连接信息、显示偏好
        </p>
      </div>

      {/* API 连接配置 */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Settings className="h-5 w-5" />
            API 连接信息
          </CardTitle>
          <CardDescription>
            查看前端当前使用的 Mem0 API Server 连接地址，并验证服务连通性
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="space-y-2">
            <label className="text-sm font-medium">当前 API 地址</label>
            <div className="flex gap-3">
              <Input
                value={apiUrl}
                readOnly
                title={apiUrl}
                className="flex-1 bg-muted"
              />
              <Button onClick={handleTestConnection} variant="outline">
                {testStatus === "testing" ? (
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                ) : (
                  <Zap className="mr-2 h-4 w-4" />
                )}
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
                连接失败，请检查环境变量配置和服务状态
              </div>
            )}
          </div>

          <Separator />

          <div className="rounded-lg bg-muted px-4 py-3">
            <p className="text-xs text-muted-foreground">
              💡 当前地址由环境变量{" "}
              <code className="rounded bg-background px-1 py-0.5">
                NEXT_PUBLIC_MEM0_API_URL
              </code>{" "}
              控制。如需修改，请调整环境变量并重启前端服务。启动 Mem0 API Server：
              <code className="ml-1 rounded bg-background px-1 py-0.5">
                mem0 server start --port 8080
              </code>
            </p>
          </div>
        </CardContent>
      </Card>

      {/* 模型与服务配置 */}
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <div>
              <CardTitle className="flex items-center gap-2">
                <Cpu className="h-5 w-5" />
                模型与服务配置
              </CardTitle>
              <CardDescription>
                当前后端使用的大模型、嵌入模型及存储服务配置
              </CardDescription>
            </div>
            <Button variant="outline" size="sm" onClick={fetchConfigInfo} disabled={configLoading}>
              <RefreshCw className={`mr-2 h-4 w-4 ${configLoading ? "animate-spin" : ""}`} />
              刷新
            </Button>
          </div>
        </CardHeader>
        <CardContent className="space-y-5">
          {configLoading && !configInfo ? (
            <div className="flex items-center justify-center py-8">
              <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
            </div>
          ) : !configInfo ? (
            <div className="text-center py-8 text-sm text-muted-foreground">
              无法获取配置信息，请确认后端服务已启动
            </div>
          ) : (
            <>
              {/* LLM 大模型 */}
              <div className="rounded-lg border p-4 space-y-4">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <Brain className="h-5 w-5 text-purple-500" />
                    <span className="text-base font-semibold">LLM 大语言模型</span>
                  </div>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={handleTestLLM}
                    disabled={llmTestStatus === "testing"}
                  >
                    {llmTestStatus === "testing" ? (
                      <Loader2 className="mr-2 h-3.5 w-3.5 animate-spin" />
                    ) : (
                      <Zap className="mr-2 h-3.5 w-3.5" />
                    )}
                    测试连接
                  </Button>
                </div>
                <div className="grid grid-cols-2 gap-x-4 gap-y-3 text-sm">
                  <p><span className="text-muted-foreground">提供商：</span><Badge variant="secondary" className="font-mono text-sm px-2.5 py-0.5">{configInfo.llm.provider}</Badge></p>
                  <p><span className="text-muted-foreground">模型名称：</span><Badge variant="outline" className="font-mono text-sm px-2.5 py-0.5">{configInfo.llm.model}</Badge></p>
                  <p className="truncate" title={configInfo.llm.base_url}><span className="text-muted-foreground">服务地址：</span><span className="font-mono">{configInfo.llm.base_url || "-"}</span></p>
                  <p><span className="text-muted-foreground">Temperature：</span><span className="font-mono">{configInfo.llm.temperature}</span></p>
                </div>
                {llmTestStatus === "success" && llmTestResult && (
                  <div className="space-y-1">
                    <div className="flex items-center gap-2 text-sm text-green-600 dark:text-green-400">
                      <CheckCircle className="h-3.5 w-3.5" />
                      {llmTestResult.message}
                    </div>
                    {llmTestResult.test_response && (
                      <p className="text-xs text-muted-foreground ml-5.5 bg-muted rounded px-2 py-1">
                        测试响应: {llmTestResult.test_response}
                      </p>
                    )}
                  </div>
                )}
                {llmTestStatus === "error" && (
                  <div className="flex items-center gap-2 text-sm text-red-600 dark:text-red-400">
                    <XCircle className="h-3.5 w-3.5" />
                    {llmTestResult?.message || "LLM 连接测试失败"}
                  </div>
                )}
              </div>

              {/* Embedder 嵌入模型 */}
              <div className="rounded-lg border p-4 space-y-4">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <Database className="h-5 w-5 text-blue-500" />
                    <span className="text-base font-semibold">Embedder 嵌入模型</span>
                  </div>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={handleTestEmbedder}
                    disabled={embedderTestStatus === "testing"}
                  >
                    {embedderTestStatus === "testing" ? (
                      <Loader2 className="mr-2 h-3.5 w-3.5 animate-spin" />
                    ) : (
                      <Zap className="mr-2 h-3.5 w-3.5" />
                    )}
                    测试连接
                  </Button>
                </div>
                <div className="grid grid-cols-2 gap-x-4 gap-y-3 text-sm">
                  <p><span className="text-muted-foreground">提供商：</span><Badge variant="secondary" className="font-mono text-sm px-2.5 py-0.5">{configInfo.embedder.provider}</Badge></p>
                  <p><span className="text-muted-foreground">模型名称：</span><Badge variant="outline" className="font-mono text-sm px-2.5 py-0.5">{configInfo.embedder.model}</Badge></p>
                  <p className="col-span-2 truncate" title={configInfo.embedder.base_url}><span className="text-muted-foreground">服务地址：</span><span className="font-mono">{configInfo.embedder.base_url || "-"}</span></p>
                </div>
                {embedderTestStatus === "success" && embedderTestResult && (
                  <div className="flex items-center gap-2 text-sm text-green-600 dark:text-green-400">
                    <CheckCircle className="h-3.5 w-3.5" />
                    {embedderTestResult.message}
                  </div>
                )}
                {embedderTestStatus === "error" && (
                  <div className="flex items-center gap-2 text-sm text-red-600 dark:text-red-400">
                    <XCircle className="h-3.5 w-3.5" />
                    {embedderTestResult?.message || "Embedder 连接测试失败"}
                  </div>
                )}
              </div>

              {/* 存储服务概览 */}
              <div className="grid grid-cols-2 gap-4">
                <div className="rounded-lg border p-4 space-y-3">
                  <div className="flex items-center gap-2">
                    <Database className="h-5 w-5 text-orange-500" />
                    <span className="text-base font-semibold">向量数据库</span>
                  </div>
                  <div className="text-sm space-y-2">
                    <p><span className="text-muted-foreground">类型：</span><Badge variant="secondary" className="font-mono text-sm px-2.5 py-0.5">{configInfo.vector_store.provider}</Badge></p>
                    <p><span className="text-muted-foreground">集合：</span><span className="font-mono">{configInfo.vector_store.collection_name}</span></p>
                    <p><span className="text-muted-foreground">维度：</span><span className="font-mono">{configInfo.vector_store.embedding_model_dims}</span></p>
                  </div>
                </div>
                <div className="rounded-lg border p-4 space-y-3">
                  <div className="flex items-center gap-2">
                    <Network className="h-5 w-5 text-green-500" />
                    <span className="text-base font-semibold">图数据库</span>
                  </div>
                  <div className="text-sm space-y-2">
                    <p><span className="text-muted-foreground">类型：</span><Badge variant="secondary" className="font-mono text-sm px-2.5 py-0.5">{configInfo.graph_store.provider}</Badge></p>
                    <p className="truncate" title={configInfo.graph_store.url}><span className="text-muted-foreground">地址：</span><span className="font-mono">{configInfo.graph_store.url || "-"}</span></p>
                  </div>
                </div>
              </div>
            </>
          )}
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
            <strong>mem0-dashboard</strong> — 基于 Mem0 开源版 API
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
