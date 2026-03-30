"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import { X, Clock, FileText, History, ExternalLink } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { cn } from "@/lib/utils";
import { mem0Api } from "@/lib/api";
import type { Memory, MemoryHistory } from "@/lib/api";
import { CategoryBadges } from "./category-badge";
import { StateBadge } from "./state-badge";

interface MemoryDetailPanelProps {
  memory: Memory | null;
  open: boolean;
  onClose: () => void;
}

export function MemoryDetailPanel({
  memory,
  open,
  onClose,
}: MemoryDetailPanelProps) {
  const [history, setHistory] = useState<MemoryHistory[]>([]);
  const [loadingHistory, setLoadingHistory] = useState(false);

  useEffect(() => {
    if (memory && open) {
      loadHistory(memory.id);
    }
  }, [memory, open]);

  const loadHistory = async (memoryId: string) => {
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
  };

  if (!memory) return null;

  return (
    <>
      {/* 遮罩层 - 顶部与 Header 底部边框线重合 */}
      {open && (
        <div
          className="fixed inset-0 top-[3.5rem] z-40 bg-black/50"
          onClick={onClose}
        />
      )}

      {/* 侧边面板 */}
      <div
        className={cn(
          "fixed right-0 top-[3.5rem] z-50 h-[calc(100%-3.5rem)] w-full sm:w-[480px] transform border-l bg-background shadow-xl transition-transform duration-300",
          open ? "translate-x-0" : "translate-x-full"
        )}
      >
        {/* 头部 */}
        <div className="flex items-center justify-between border-b p-4">
          <h3 className="text-lg font-semibold">记忆详情</h3>
          <div className="flex items-center gap-1">
            <Link href={`/memory/${memory.id}`}>
              <Button variant="ghost" size="icon" title="在详情页打开" onClick={onClose}>
                <ExternalLink className="h-4 w-4" />
              </Button>
            </Link>
            <Button variant="ghost" size="icon" onClick={onClose}>
              <X className="h-4 w-4" />
            </Button>
          </div>
        </div>

        {/* 内容区域 */}
        <div className="h-[calc(100%-57px)] overflow-y-auto">
          <Tabs defaultValue="info" className="w-full">
            <TabsList className="w-full justify-start rounded-none border-b bg-transparent px-4">
              <TabsTrigger value="info" className="gap-1.5">
                <FileText className="h-4 w-4" />
                基本信息
              </TabsTrigger>
              <TabsTrigger value="history" className="gap-1.5">
                <History className="h-4 w-4" />
                修改历史
              </TabsTrigger>
            </TabsList>

            {/* 基本信息 Tab */}
            <TabsContent value="info" className="p-4 space-y-4">
              {/* 1. 状态 */}
              <div className="space-y-1.5">
                <label className="text-xs font-medium text-muted-foreground">
                  状态
                </label>
                <div>
                  <StateBadge state={memory.state} size="md" />
                </div>
              </div>

              <Separator />

              {/* 2. 记忆 ID */}
              <div className="space-y-1.5">
                <label className="text-xs font-medium text-muted-foreground">
                  记忆 ID
                </label>
                <p className="text-sm font-mono break-all">{memory.id}</p>
              </div>

              <Separator />

              {/* 3. 用户 ID */}
              {memory.user_id && (
                <>
                  <div className="space-y-1.5">
                    <label className="text-xs font-medium text-muted-foreground">
                      用户 ID
                    </label>
                    <div>
                      <Badge variant="secondary">{memory.user_id}</Badge>
                    </div>
                  </div>
                  <Separator />
                </>
              )}

              {/* 4. 分类标签 */}
              {memory.categories && memory.categories.length > 0 && (
                <>
                  <div className="space-y-1.5">
                    <label className="text-xs font-medium text-muted-foreground">
                      分类标签
                    </label>
                    <CategoryBadges categories={memory.categories} />
                  </div>
                  <Separator />
                </>
              )}

              {/* 5. 记忆内容 */}
              <div className="space-y-1.5">
                <label className="text-xs font-medium text-muted-foreground">
                  记忆内容
                </label>
                <div className="rounded-lg border bg-muted/50 p-4">
                  <p className="text-sm leading-relaxed">{memory.memory}</p>
                </div>
              </div>

              <Separator />

              {/* 6. Hash */}
              {memory.hash && (
                <div className="space-y-1.5">
                  <label className="text-xs font-medium text-muted-foreground">
                    Hash
                  </label>
                  <p className="text-sm font-mono break-all text-muted-foreground">
                    {memory.hash}
                  </p>
                </div>
              )}

              {/* 时间信息 */}
              <Separator />
              <div className="grid grid-cols-2 gap-4">
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
                      更新时间
                    </label>
                    <p className="text-sm">
                      {new Date(memory.updated_at).toLocaleString("zh-CN")}
                    </p>
                  </div>
                )}
              </div>

              {/* Agent ID */}
              {memory.agent_id && (
                <>
                  <Separator />
                  <div className="space-y-1.5">
                    <label className="text-xs font-medium text-muted-foreground">
                      Agent ID
                    </label>
                    <div>
                      <Badge variant="outline">{memory.agent_id}</Badge>
                    </div>
                  </div>
                </>
              )}

              {/* 元数据 */}
              {memory.metadata &&
                Object.keys(memory.metadata).length > 0 && (
                  <>
                    <Separator />
                    <div className="space-y-1.5">
                      <label className="text-xs font-medium text-muted-foreground">
                        元数据
                      </label>
                      <pre className="rounded-lg border bg-muted/50 p-3 text-xs overflow-x-auto">
                        {JSON.stringify(memory.metadata, null, 2)}
                      </pre>
                    </div>
                  </>
                )}
            </TabsContent>

            {/* 修改历史 Tab */}
            <TabsContent value="history" className="p-4">
              {loadingHistory ? (
                <div className="space-y-3">
                  {[1, 2, 3].map((i) => (
                    <div
                      key={i}
                      className="h-16 animate-pulse rounded-md bg-muted"
                    />
                  ))}
                </div>
              ) : history.length > 0 ? (
                <div className="space-y-3">
                  {history.map((item, index) => (
                    <div
                      key={item.id || index}
                      className="rounded-lg border p-3 space-y-2"
                    >
                      <div className="flex items-center justify-between">
                        <Badge
                          variant={
                            item.event === "ADD"
                              ? "default"
                              : item.event === "UPDATE"
                              ? "secondary"
                              : "destructive"
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

                      {item.old_memory && (
                        <div className="rounded bg-red-50 dark:bg-red-950/20 p-2">
                          <p className="text-xs text-muted-foreground mb-1">
                            旧内容：
                          </p>
                          <p className="text-sm line-through text-muted-foreground">
                            {item.old_memory}
                          </p>
                        </div>
                      )}

                      <div className="rounded bg-green-50 dark:bg-green-950/20 p-2">
                        <p className="text-xs text-muted-foreground mb-1">
                          {item.old_memory ? "新内容：" : "内容："}
                        </p>
                        <p className="text-sm">{item.new_memory}</p>
                      </div>

                      {/* 标签信息 */}
                      {item.categories && item.categories.length > 0 && (
                        <div className="pt-1">
                          <p className="text-xs text-muted-foreground mb-1">标签：</p>
                          <CategoryBadges categories={item.categories} />
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              ) : (
                <div className="flex flex-col items-center justify-center py-8 text-center">
                  <History className="mb-3 h-10 w-10 text-muted-foreground/30" />
                  <p className="text-sm text-muted-foreground">
                    暂无修改历史
                  </p>
                </div>
              )}
            </TabsContent>
          </Tabs>
        </div>
      </div>
    </>
  );
}
