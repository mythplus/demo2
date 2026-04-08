"use client";

import React, { useEffect, useState, useCallback } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { toast } from "@/hooks/use-toast";
import {
  ArrowLeft,
  Brain,
  Clock,
  RefreshCw,
  Pencil,
  Trash2,
  History,
  Copy,
  CheckCircle,
  Play,
  Pause,
  Archive,
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
import { Separator } from "@/components/ui/separator";
import { CategoryBadge, CategoryBadges } from "@/components/memories/category-badge";
import { getCategoryInfo } from "@/lib/constants";
import { StateBadge } from "@/components/memories/state-badge";
import { EditMemoryDialog } from "@/components/memories/edit-memory-dialog";
import { DeleteConfirmDialog } from "@/components/memories/delete-confirm-dialog";
import { mem0Api } from "@/lib/api";
import type { Memory, MemoryHistory, MemoryState } from "@/lib/api";
import { STATE_LIST } from "@/lib/constants";
import { RelatedMemories } from "@/components/shared/related-memories";
import { AccessLogList } from "@/components/shared/access-log-list";
import { DetailPageSkeleton } from "@/components/ui/skeleton";

export default function MemoryDetailPage() {
  const params = useParams();
  const memoryId = params.id as string;

  const [memory, setMemory] = useState<Memory | null>(null);
  const [history, setHistory] = useState<MemoryHistory[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadingHistory, setLoadingHistory] = useState(true);
  const [error, setError] = useState("");
  const [copied, setCopied] = useState(false);

  // 弹窗状态
  const [editDialogOpen, setEditDialogOpen] = useState(false);
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [deleteLoading, setDeleteLoading] = useState(false);

  const fetchMemory = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const data = await mem0Api.getMemory(memoryId);
      setMemory(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "获取记忆失败");
    } finally {
      setLoading(false);
    }
  }, [memoryId]);

  const fetchHistory = useCallback(async () => {
    setLoadingHistory(true);
    try {
      const data = await mem0Api.getMemoryHistory(memoryId);
      setHistory(Array.isArray(data) ? data : []);
    } catch (err) {
      console.error("获取历史记录失败:", err);
      setHistory([]);
    } finally {
      setLoadingHistory(false);
    }
  }, [memoryId]);

  useEffect(() => {
    fetchMemory();
    fetchHistory();
  }, [fetchMemory, fetchHistory]);

  // 复制 ID
  const handleCopyId = () => {
    navigator.clipboard.writeText(memoryId);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  // 删除
  const handleDelete = async () => {
    setDeleteLoading(true);
    try {
      await mem0Api.deleteMemory(memoryId);
      setDeleteDialogOpen(false);
      // 软删除后刷新数据，让用户看到状态变为"已删除"
      fetchMemory();
      fetchHistory();
    } catch (err) {
      console.error("删除失败:", err);
      toast({ title: "删除失败", description: err instanceof Error ? err.message : "未知错误", variant: "destructive" });
    } finally {
      setDeleteLoading(false);
    }
  };

  // 更改状态
  const handleStateChange = async (newState: MemoryState) => {
    try {
      await mem0Api.updateMemory(memoryId, { state: newState });
      fetchMemory();
    } catch (err) {
      console.error("更新状态失败:", err);
    }
  };

  if (loading) {
    return (
      <div className="space-y-6">
        <div className="flex items-center gap-2">
          <Link href="/memories">
          <Button variant="outline" size="sm">
            <ArrowLeft className="mr-1 h-4 w-4" />
            返回记忆列表
          </Button>
          </Link>
        </div>
        <DetailPageSkeleton />
      </div>
    );
  }

  if (error || !memory) {
    return (
      <div className="space-y-6">
        <div className="flex items-center gap-2">
          <Link href="/memories">
          <Button variant="outline" size="sm">
            <ArrowLeft className="mr-1 h-4 w-4" />
            返回记忆列表
          </Button>
          </Link>
        </div>
        <Card className="border-destructive">
          <CardContent className="flex flex-col items-center justify-center py-12">
            <Brain className="mb-4 h-16 w-16 text-muted-foreground/30" />
            <p className="text-lg font-medium text-destructive">
              {error || "记忆不存在"}
            </p>
            <Link href="/memories">
              <Button className="mt-4" variant="outline">
                返回记忆列表
              </Button>
            </Link>
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* 面包屑导航 */}
      <div className="flex items-center gap-2">
        <Link href="/memories">
          <Button variant="outline" size="sm">
            <ArrowLeft className="mr-1 h-4 w-4" />
            返回记忆列表
          </Button>
        </Link>
      </div>

      {/* 主内容区域：左侧 2/3 + 右侧 1/3 */}
      <div className="grid gap-4 lg:grid-cols-3">
        {/* 左侧：记忆内容 + 分类 + 元数据 + 修改历史 */}
        <div className="lg:col-span-2 space-y-3">
          {/* 记忆内容卡片 */}
          <Card>
            <CardHeader className="px-4 py-3">
              <CardTitle>记忆内容</CardTitle>
            </CardHeader>
            <CardContent className="px-4 pb-3 pt-0">
              <div className="rounded-lg border bg-muted/50 p-3 overflow-hidden">
                <p className="text-sm leading-relaxed whitespace-pre-wrap break-all">
                  {memory.memory}
                </p>
              </div>
            </CardContent>
          </Card>

          {/* 分类标签 */}
          {memory.categories && memory.categories.length > 0 && (
            <Card>
              <CardHeader className="px-4 py-3">
                <CardTitle className="text-base">分类标签</CardTitle>
              </CardHeader>
              <CardContent className="px-4 pb-3 pt-0">
                <CategoryBadges categories={memory.categories} />
              </CardContent>
            </Card>
          )}

          {/* 元数据（过滤掉已单独展示的 categories 和 state） */}
          {memory.metadata && (() => {
            const filteredMetadata = Object.fromEntries(
              Object.entries(memory.metadata).filter(
                ([key]) => key !== "categories" && key !== "state"
              )
            );
            return Object.keys(filteredMetadata).length > 0 ? (
              <Card>
                <CardHeader className="px-4 py-3">
                  <CardTitle className="text-base">元数据</CardTitle>
                </CardHeader>
                <CardContent className="px-4 pb-3 pt-0">
                  <pre className="rounded-lg border bg-muted/50 p-3 text-xs overflow-x-auto font-mono">
                    {JSON.stringify(filteredMetadata, null, 2)}
                  </pre>
                </CardContent>
              </Card>
            ) : null;
          })()}

          {/* 修改历史时间线 */}
          <Card>
            <CardHeader className="px-4 py-3">
              <CardTitle className="flex items-center gap-2 text-base">
                <History className="h-4 w-4" />
                修改历史
              </CardTitle>
              <CardDescription>
                记录该记忆的所有变更操作
              </CardDescription>
            </CardHeader>
            <CardContent className="px-4 pb-3 pt-0">
              {loadingHistory ? (
                <div className="space-y-3">
                  {[1, 2, 3].map((i) => (
                    <div key={i} className="h-16 animate-pulse rounded-md bg-muted" />
                  ))}
                </div>
              ) : history.length > 0 ? (
                <div className="relative space-y-0 max-h-[500px] overflow-y-auto pr-1">
                  {/* 时间线竖线 */}
                  <div className="absolute left-4 top-0 bottom-0 w-px bg-border" />

                  {history.map((item, index) => (
                    <div key={item.id || index} className="relative pl-10 pb-6 last:pb-0">
                      {/* 时间线圆点 */}
                      <div
                        className={`absolute left-2.5 top-1 h-3 w-3 rounded-full border-2 border-background ${
                          item.event === "ADD"
                            ? "bg-green-500"
                            : item.event === "UPDATE"
                            ? "bg-amber-500"
                            : "bg-red-500"
                        }`}
                      />

                      <div className="rounded-lg border p-3 space-y-2">
                        <div className="flex items-center justify-between">
                          <Badge
                            variant={
                              item.event === "ADD"
                                ? "default"
                                : item.event === "UPDATE"
                                ? "default"
                                : "destructive"
                            }
                            className={
                              item.event === "ADD"
                                ? "bg-green-500 text-white hover:bg-green-500/90"
                                : item.event === "UPDATE"
                                ? "bg-amber-500 text-white hover:bg-amber-500/90"
                                : ""
                            }
                          >
                            {item.event === "ADD"
                              ? "新增"
                              : item.event === "UPDATE"
                              ? "更新"
                              : "删除"}
                          </Badge>
                          <span className="text-xs text-muted-foreground">
                            <Clock className="mr-1 inline h-3 w-3" />
                            {new Date(item.created_at).toLocaleString("zh-CN")}
                          </span>
                        </div>

                        {item.event !== "DELETE" && (
                          <>
                            {item.old_memory && (
                              <div className="rounded bg-red-50 dark:bg-red-950/20 p-2">
                                <p className="text-xs text-muted-foreground mb-1">旧内容：</p>
                <p className="text-sm line-through text-muted-foreground break-all whitespace-pre-wrap">
                                  {item.old_memory}
                                </p>
                              </div>
                            )}

                            <div className="rounded bg-green-50 dark:bg-green-950/20 p-2">
                              <p className="text-xs text-muted-foreground mb-1">
                                {item.old_memory ? "新内容：" : "内容："}
                              </p>
                              <p className="text-sm break-all whitespace-pre-wrap">{item.new_memory}</p>
                            </div>
                          </>
                        )}

                        {/* 标签信息 - 对比显示变更 */}
                        {item.event !== "DELETE" && (() => {
                          const oldCats = (item.old_categories || []) as string[];
                          const newCats = (item.categories || []) as string[];
                          const added = newCats.filter((c) => !oldCats.includes(c)) as import("@/lib/api").Category[];
                          const removed = oldCats.filter((c) => !newCats.includes(c)) as import("@/lib/api").Category[];
                          const unchanged = newCats.filter((c) => oldCats.includes(c)) as import("@/lib/api").Category[];
                          const hasChange = added.length > 0 || removed.length > 0;

                          if (item.event === "ADD") {
                            return newCats.length > 0 ? (
                              <div className="pt-1">
                                <p className="text-xs text-muted-foreground mb-1">标签：</p>
                                <CategoryBadges categories={newCats as import("@/lib/api").Category[]} />
                              </div>
                            ) : null;
                          }

                          if (!hasChange && newCats.length > 0) {
                            return (
                              <div className="pt-1">
                                <p className="text-xs text-muted-foreground mb-1">标签：</p>
                                <CategoryBadges categories={newCats as import("@/lib/api").Category[]} />
                              </div>
                            );
                          }

                          if (hasChange) {
                            return (
                              <div className="pt-1 space-y-1.5">
                                <p className="text-xs text-muted-foreground mb-1">标签变更：</p>
                                <div className="flex flex-wrap gap-1.5 items-center">
                                  {removed.map((cat: string) => {
                                    const info = getCategoryInfo(cat as any);
                                    return (
                                      <span
                                        key={`rm-${cat}`}
                                        className="inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium border bg-red-50 dark:bg-red-950/20 text-red-500 dark:text-red-400 border-red-200 dark:border-red-700/40 line-through"
                                      >
                                        {info?.label || cat}
                                      </span>
                                    );
                                  })}
                                  {unchanged.map((cat: string) => (
                                    <CategoryBadge key={`keep-${cat}`} category={cat as any} />
                                  ))}
                                  {added.map((cat: string) => {
                                    const info = getCategoryInfo(cat as any);
                                    return (
                                      <span
                                        key={`add-${cat}`}
                                        className="inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium border bg-green-50 dark:bg-green-950/20 text-green-600 dark:text-green-400 border-green-200 dark:border-green-700/40"
                                      >
                                        + {info?.label || cat}
                                      </span>
                                    );
                                  })}
                                </div>
                              </div>
                            );
                          }

                          return null;
                        })()}
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="flex flex-col items-center justify-center py-4 text-center">
                  <History className="mb-3 h-10 w-10 text-muted-foreground/30" />
                  <p className="text-sm text-muted-foreground">暂无修改历史</p>
                </div>
              )}
            </CardContent>
          </Card>

          {/* 关联记忆 */}
          <RelatedMemories memoryId={memoryId} />

          {/* 访问日志 */}
          <AccessLogList memoryId={memoryId} />
        </div>

        {/* 右侧：元信息 + 操作按钮 */}
        <div className="space-y-3">
          {/* 元信息卡片 */}
          <Card>
            <CardHeader className="px-4 py-3">
              <CardTitle className="text-base">基本信息</CardTitle>
            </CardHeader>
            <CardContent className="px-4 pb-3 pt-0 space-y-3">
              {/* ID */}
              <div className="space-y-1">
                <label className="text-xs font-medium text-muted-foreground">
                  记忆 ID
                </label>
                <div className="flex items-center gap-2">
                  <code className="flex-1 rounded bg-muted px-2 py-1 text-xs font-mono break-all">
                    {memory.id}
                  </code>
                  <Button
                    variant="ghost"
                    size="icon"
                    className="h-7 w-7 shrink-0"
                    onClick={handleCopyId}
                  >
                    {copied ? (
                      <CheckCircle className="h-3.5 w-3.5 text-green-500 dark:text-green-400" />
                    ) : (
                      <Copy className="h-3.5 w-3.5" />
                    )}
                  </Button>
                </div>
              </div>

              <Separator />

              {/* 状态 */}
              <div className="space-y-1">
                <label className="text-xs font-medium text-muted-foreground">
                  状态
                </label>
                <div>
                  <StateBadge state={memory.state} size="md" />
                </div>
              </div>

              {/* 用户 */}
              {memory.user_id && (
                <div className="space-y-1">
                  <label className="text-xs font-medium text-muted-foreground">
                    用户
                  </label>
                  <div className="min-w-0">
                    <Link href={`/users/${encodeURIComponent(memory.user_id)}`}>
                      <Badge variant="secondary" className="max-w-full truncate cursor-pointer hover:bg-secondary/80" title={memory.user_id}>
                        {memory.user_id}
                      </Badge>
                    </Link>
                  </div>
                </div>
              )}

              {/* Agent ID */}
              {memory.agent_id && (
                <div className="space-y-1">
                  <label className="text-xs font-medium text-muted-foreground">
                    Agent ID
                  </label>
                  <div className="min-w-0">
                    <Badge variant="outline" className="max-w-full truncate" title={memory.agent_id}>
                      {memory.agent_id}
                    </Badge>
                  </div>
                </div>
              )}

              <Separator />

              {/* 时间 */}
              {memory.created_at && (
                <div className="space-y-1">
                  <label className="text-xs font-medium text-muted-foreground">
                    创建时间
                  </label>
                  <p className="text-sm">
                    {new Date(memory.created_at).toLocaleString("zh-CN")}
                  </p>
                </div>
              )}

              {memory.updated_at && (
                <div className="space-y-1">
                  <label className="text-xs font-medium text-muted-foreground">
                    最近更新时间
                  </label>
                  <p className="text-sm">
                    {new Date(memory.updated_at).toLocaleString("zh-CN")}
                  </p>
                </div>
              )}

              {memory.hash && (
                <>
                  <Separator />
                  <div className="space-y-1">
                    <label className="text-xs font-medium text-muted-foreground">
                      Hash
                    </label>
                    <p className="text-xs font-mono break-all text-muted-foreground">
                      {memory.hash}
                    </p>
                  </div>
                </>
              )}
            </CardContent>
          </Card>

          {/* 操作按钮 */}
          <Card>
            <CardHeader className="px-4 py-3">
              <CardTitle className="text-base">操作</CardTitle>
            </CardHeader>
            <CardContent className="px-4 pb-3 pt-0 space-y-2">
              <Button
                variant="outline"
                className="w-full justify-start"
                onClick={() => setEditDialogOpen(true)}
                disabled={memory.state === "deleted"}
              >
                <Pencil className="mr-2 h-4 w-4" />
                编辑记忆
              </Button>

              {/* 状态切换按钮 */}
              {memory.state !== "active" && (
                <Button
                  variant="outline"
                  className="w-full justify-start"
                  onClick={() => handleStateChange("active")}
                >
                  <Play className="mr-2 h-4 w-4" />
                  设为活跃
                </Button>
              )}
              {memory.state !== "paused" && memory.state !== "deleted" && (
                <Button
                  variant="outline"
                  className="w-full justify-start"
                  onClick={() => handleStateChange("paused")}
                >
                  <Pause className="mr-2 h-4 w-4" />
                  暂停
                </Button>
              )}

              <Separator />

              <Button
                variant="destructive"
                className="w-full justify-start"
                onClick={() => setDeleteDialogOpen(true)}
                disabled={memory.state === "deleted"}
              >
                <Trash2 className="mr-2 h-4 w-4" />
                删除记忆
              </Button>
            </CardContent>
          </Card>
        </div>
      </div>

      {/* 弹窗 */}
      <EditMemoryDialog
        memory={memory}
        open={editDialogOpen}
        onOpenChange={setEditDialogOpen}
        onSuccess={() => {
          fetchMemory();
          fetchHistory();
        }}
      />

      <DeleteConfirmDialog
        open={deleteDialogOpen}
        onOpenChange={setDeleteDialogOpen}
        onConfirm={handleDelete}
        loading={deleteLoading}
        description={`确定要删除这条记忆吗？此操作不可撤销。`}
      />
    </div>
  );
}
