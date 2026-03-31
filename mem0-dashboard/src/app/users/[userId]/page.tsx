"use client";

import React, { useEffect, useState, useCallback } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import {
  ArrowLeft,
  Brain,
  RefreshCw,
  Trash2,
  MoreHorizontal,
  Pencil,
  Eye,
  Clock,
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
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { EditMemoryDialog } from "@/components/memories/edit-memory-dialog";
import { DeleteConfirmDialog } from "@/components/memories/delete-confirm-dialog";
import { MemoryDetailPanel } from "@/components/memories/memory-detail-panel";
import { CategoryBadges } from "@/components/memories/category-badge";
import { mem0Api } from "@/lib/api";
import type { Memory } from "@/lib/api";

export default function UserDetailPage() {
  const params = useParams();
  const router = useRouter();
  const userId = decodeURIComponent(params.userId as string);

  const [memories, setMemories] = useState<Memory[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  // 弹窗状态
  const [editDialogOpen, setEditDialogOpen] = useState(false);
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [deleteAllDialogOpen, setDeleteAllDialogOpen] = useState(false);
  const [detailPanelOpen, setDetailPanelOpen] = useState(false);
  const [selectedMemory, setSelectedMemory] = useState<Memory | null>(null);
  const [deleteLoading, setDeleteLoading] = useState(false);

  const fetchMemories = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const data = await mem0Api.getMemories(userId);
      setMemories(Array.isArray(data) ? data : []);
    } catch (err) {
      setError(err instanceof Error ? err.message : "获取记忆失败");
    } finally {
      setLoading(false);
    }
  }, [userId]);

  useEffect(() => {
    fetchMemories();
  }, [fetchMemories]);

  // 删除单条记忆
  const handleDeleteMemory = async () => {
    if (!selectedMemory) return;
    setDeleteLoading(true);
    try {
      await mem0Api.deleteMemory(selectedMemory.id);
      setDeleteDialogOpen(false);
      setSelectedMemory(null);
      fetchMemories();
    } catch (err) {
      console.error("删除失败:", err);
    } finally {
      setDeleteLoading(false);
    }
  };

  // 删除所有记忆
  const handleDeleteAll = async () => {
    setDeleteLoading(true);
    try {
      await mem0Api.deleteAllMemories(userId);
      setDeleteAllDialogOpen(false);
      router.push("/users");
    } catch (err) {
      console.error("删除失败:", err);
    } finally {
      setDeleteLoading(false);
    }
  };

  return (
    <div className="space-y-6">
      {/* 面包屑导航 */}
      <div className="flex items-center gap-2">
        <Link href="/users">
          <Button variant="ghost" size="sm">
            <ArrowLeft className="mr-1 h-4 w-4" />
            返回用户列表
          </Button>
        </Link>
      </div>

      {/* 用户信息头部 */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-4">
          <div className="flex h-14 w-14 items-center justify-center rounded-full bg-primary/10 text-primary text-xl font-bold">
            {userId.charAt(0).toUpperCase()}
          </div>
          <div>
            <h2 className="text-2xl font-bold tracking-tight">{userId}</h2>
            <p className="text-muted-foreground">
              共 {memories.length} 条记忆
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="outline" size="icon" onClick={fetchMemories}>
            <RefreshCw
              className={`h-4 w-4 ${loading ? "animate-spin" : ""}`}
            />
          </Button>
          <Button
            variant="destructive"
            size="sm"
            onClick={() => setDeleteAllDialogOpen(true)}
          >
            <Trash2 className="mr-2 h-4 w-4" />
            删除所有记忆
          </Button>
        </div>
      </div>

      {/* 错误提示 */}
      {error && (
        <Card className="border-destructive">
          <CardContent className="flex items-center gap-3 p-4">
            <div className="h-3 w-3 rounded-full bg-red-500" />
            <p className="text-sm text-destructive">{error}</p>
          </CardContent>
        </Card>
      )}

      {/* 记忆列表 */}
      <Card>
        <CardHeader>
          <CardTitle>记忆列表</CardTitle>
          <CardDescription>
            用户 {userId} 的所有记忆条目
          </CardDescription>
        </CardHeader>
        <CardContent>
          {loading ? (
            <div className="space-y-3">
              {[1, 2, 3].map((i) => (
                <div
                  key={i}
                  className="h-16 animate-pulse rounded-lg bg-muted"
                />
              ))}
            </div>
          ) : memories.length > 0 ? (
            <div className="space-y-2">
              {memories.map((memory) => (
                <div
                  key={memory.id}
                  className="group flex items-start justify-between rounded-lg border p-4 transition-colors hover:bg-accent/50"
                >
                  <div
                    className="flex-1 cursor-pointer"
                    onClick={() => {
                      setSelectedMemory(memory);
                      setDetailPanelOpen(true);
                    }}
                  >
                    <p className="text-sm leading-relaxed">{memory.memory}</p>
                    <div className="mt-2 flex flex-wrap items-center gap-2">
                      <CategoryBadges categories={memory.categories} />
                      {memory.created_at && (
                        <span className="text-xs text-muted-foreground">
                          <Clock className="mr-1 inline h-3 w-3" />
                          {new Date(memory.created_at).toLocaleString("zh-CN")}
                        </span>
                      )}
                    </div>
                  </div>

                  <DropdownMenu>
                    <DropdownMenuTrigger asChild>
                      <Button
                        variant="ghost"
                        size="icon"
                        className="ml-2 shrink-0 opacity-0 group-hover:opacity-100 transition-opacity"
                      >
                        <MoreHorizontal className="h-4 w-4" />
                      </Button>
                    </DropdownMenuTrigger>
                    <DropdownMenuContent align="end">
                      <DropdownMenuItem
                        onClick={() => {
                          setSelectedMemory(memory);
                          setDetailPanelOpen(true);
                        }}
                      >
                        <Eye className="mr-2 h-4 w-4" />
                        查看详情
                      </DropdownMenuItem>
                      <DropdownMenuItem
                        onClick={() => {
                          setSelectedMemory(memory);
                          setEditDialogOpen(true);
                        }}
                      >
                        <Pencil className="mr-2 h-4 w-4" />
                        编辑
                      </DropdownMenuItem>
                      <DropdownMenuSeparator />
                      <DropdownMenuItem
                        className="text-destructive focus:text-destructive"
                        onClick={() => {
                          setSelectedMemory(memory);
                          setDeleteDialogOpen(true);
                        }}
                      >
                        <Trash2 className="mr-2 h-4 w-4" />
                        删除
                      </DropdownMenuItem>
                    </DropdownMenuContent>
                  </DropdownMenu>
                </div>
              ))}
            </div>
          ) : (
            <div className="flex flex-col items-center justify-center py-12 text-center">
              <Brain className="mb-4 h-16 w-16 text-muted-foreground/30" />
              <p className="text-lg font-medium text-muted-foreground">
                该用户暂无记忆
              </p>
            </div>
          )}
        </CardContent>
      </Card>

      {/* 弹窗组件 */}
      <EditMemoryDialog
        memory={selectedMemory}
        open={editDialogOpen}
        onOpenChange={setEditDialogOpen}
        onSuccess={fetchMemories}
      />

      <DeleteConfirmDialog
        open={deleteDialogOpen}
        onOpenChange={setDeleteDialogOpen}
        onConfirm={handleDeleteMemory}
        loading={deleteLoading}
        description={`确定要删除这条记忆吗？`}
      />

      <DeleteConfirmDialog
        open={deleteAllDialogOpen}
        onOpenChange={setDeleteAllDialogOpen}
        onConfirm={handleDeleteAll}
        loading={deleteLoading}
        title="删除所有记忆"
        description={`确定要删除用户 "${userId}" 的所有记忆吗？此操作不可撤销！`}
      />

      <MemoryDetailPanel
        memory={selectedMemory}
        open={detailPanelOpen}
        onClose={() => setDetailPanelOpen(false)}
      />
    </div>
  );
}
