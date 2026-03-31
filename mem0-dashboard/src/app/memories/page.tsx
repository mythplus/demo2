"use client";

import React, { useEffect, useState, useCallback } from "react";
import Link from "next/link";
import {
  Brain,
  Plus,
  Search,
  MoreHorizontal,
  Pencil,
  Trash2,
  Eye,
  RefreshCw,
  ChevronLeft,
  ChevronRight,
  ExternalLink,
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
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { AddMemoryDialog } from "@/components/memories/add-memory-dialog";
import { EditMemoryDialog } from "@/components/memories/edit-memory-dialog";
import { DeleteConfirmDialog } from "@/components/memories/delete-confirm-dialog";
import { MemoryDetailPanel } from "@/components/memories/memory-detail-panel";
import { MemoryFilters } from "@/components/memories/memory-filters";
import { MemoryTable } from "@/components/memories/memory-table";
import { ViewToggle, type ViewMode } from "@/components/memories/view-toggle";
import { PageSizeSelector } from "@/components/memories/page-size-selector";
import { CategoryBadges } from "@/components/memories/category-badge";
import { StateBadge } from "@/components/memories/state-badge";
import { mem0Api } from "@/lib/api";
import type { Memory, FilterParams } from "@/lib/api";
import { usePreferences } from "@/hooks/use-preferences";
import { MemoryListSkeleton } from "@/components/ui/skeleton";

export default function MemoriesPage() {
  // 用户偏好设置
  const { preferences, savePreferences } = usePreferences();
  const sortOrder = preferences.sortOrder;

  // 数据状态
  const [memories, setMemories] = useState<Memory[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  // 筛选状态
  const [searchText, setSearchText] = useState("");
  const [filters, setFilters] = useState<FilterParams>({});
  const [currentPage, setCurrentPage] = useState(1);
  const [pageSize, setPageSize] = useState(preferences.pageSize);
  const [jumpPage, setJumpPage] = useState("");

  // 视图模式
  const [viewMode, setViewMode] = useState<ViewMode>("table");

  // IME 中文输入法组合状态
  const [isComposing, setIsComposing] = useState(false);

  // 弹窗状态
  const [addDialogOpen, setAddDialogOpen] = useState(false);
  const [editDialogOpen, setEditDialogOpen] = useState(false);
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [detailPanelOpen, setDetailPanelOpen] = useState(false);

  // 当前操作的记忆
  const [selectedMemory, setSelectedMemory] = useState<Memory | null>(null);
  const [deleteLoading, setDeleteLoading] = useState(false);

  // 获取记忆列表（通过后端筛选）
  const fetchMemories = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const apiFilters: FilterParams = { ...filters };
      const data = await mem0Api.getMemories(apiFilters);
      setMemories(Array.isArray(data) ? data : []);
    } catch (err) {
      setError(err instanceof Error ? err.message : "获取记忆列表失败");
      setMemories([]);
    } finally {
      setLoading(false);
    }
  }, [filters]);

  useEffect(() => {
    fetchMemories();
  }, [fetchMemories]);

  // 获取所有唯一用户（按名称排序）
  const uniqueUsers = (Array.from(
    new Set(memories.map((m) => m.user_id).filter(Boolean))
  ) as string[]).sort((a, b) => a.localeCompare(b, "zh-CN", { numeric: true }));

  // 本地搜索过滤（在后端筛选结果上再做前端文本搜索）
  const filteredMemories = memories
    .filter((m) => {
      if (!searchText.trim()) return true;
      const keyword = searchText.trim().toLowerCase();
      const memoryText = (m.memory || "").toLowerCase();
      const userId = (m.user_id || "").toLowerCase();
      const id = (m.id || "").toLowerCase();
      return (
        memoryText.includes(keyword) ||
        userId.includes(keyword) ||
        id.includes(keyword)
      );
    })
    // 按偏好排序
    .sort((a, b) => {
      const timeA = a.created_at ? new Date(a.created_at).getTime() : 0;
      const timeB = b.created_at ? new Date(b.created_at).getTime() : 0;
      return sortOrder === "newest" ? timeB - timeA : timeA - timeB;
    });

  // 分页
  const totalPages = Math.ceil(filteredMemories.length / pageSize);
  const paginatedMemories = filteredMemories.slice(
    (currentPage - 1) * pageSize,
    currentPage * pageSize
  );

  // 筛选变化时重置页码
  const handleFiltersChange = (newFilters: FilterParams) => {
    setFilters(newFilters);
    setCurrentPage(1);
  };

  // 删除记忆
  const handleDelete = async () => {
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

  // 操作按钮
  const handleEdit = (memory: Memory) => {
    setSelectedMemory(memory);
    setEditDialogOpen(true);
  };

  const handleDeleteClick = (memory: Memory) => {
    setSelectedMemory(memory);
    setDeleteDialogOpen(true);
  };

  const handleViewDetail = (memory: Memory) => {
    setSelectedMemory(memory);
    setDetailPanelOpen(true);
  };

  return (
    <div className="space-y-6">
      {/* 页面头部 */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h2 className="text-2xl font-bold tracking-tight">记忆管理</h2>
          <p className="text-muted-foreground">
            管理所有存储的记忆条目，支持添加、编辑、删除操作
          </p>
        </div>
        <div className="flex items-center gap-2 shrink-0">
          <Button variant="outline" size="icon" onClick={fetchMemories}>
            <RefreshCw className={`h-4 w-4 ${loading ? "animate-spin" : ""}`} />
          </Button>
          <Button onClick={() => setAddDialogOpen(true)}>
            <Plus className="mr-2 h-4 w-4" />
            <span className="hidden sm:inline">添加记忆</span>
            <span className="sm:hidden">添加</span>
          </Button>
        </div>
      </div>

      {/* 筛选栏 */}
      <Card>
        <CardContent className="pt-6">
          <div className="space-y-3">
            {/* 搜索框 */}
            <div className="flex items-center gap-3">
              <div className="relative flex-1">
                <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
                <Input
                  placeholder="搜索记忆内容、用户 ID..."
                  value={searchText}
                  onChange={(e) => {
                    setSearchText(e.target.value);
                    if (!isComposing) {
                      setCurrentPage(1);
                    }
                  }}
                  onCompositionStart={() => setIsComposing(true)}
                  onCompositionEnd={(e) => {
                    setIsComposing(false);
                    setSearchText((e.target as HTMLInputElement).value);
                    setCurrentPage(1);
                  }}
                  className="pl-9"
                />
              </div>
            </div>

            {/* 视图切换 + 多维筛选器 */}
            <MemoryFilters
              filters={filters}
              onFiltersChange={handleFiltersChange}
              users={uniqueUsers}
              prefix={<ViewToggle mode={viewMode} onChange={setViewMode} className="h-8" />}
            />
          </div>
        </CardContent>
      </Card>

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
          <div className="flex items-center justify-between">
            <div className="space-y-1.5">
              <CardTitle>记忆列表</CardTitle>
              <CardDescription>
                共 <span className="font-semibold text-foreground text-base">{filteredMemories.length}</span> 条记忆
                {searchText && `（搜索: "${searchText}"）`}
              </CardDescription>
            </div>
            <PageSizeSelector
              value={pageSize}
              onChange={(size) => {
                setPageSize(size);
                setCurrentPage(1);
              }}
            />
          </div>
        </CardHeader>
        <CardContent>
          {loading ? (
            <MemoryListSkeleton count={pageSize > 5 ? 5 : pageSize} />
          ) : paginatedMemories.length > 0 ? (
            <div className="space-y-2">
              {/* 表格视图 */}
              {viewMode === "table" ? (
                <MemoryTable
                  memories={paginatedMemories}
                  onView={handleViewDetail}
                  onEdit={handleEdit}
                  onDelete={handleDeleteClick}
                />
              ) : (
                /* 列表视图 */
                paginatedMemories.map((memory) => (
                  <div
                    key={memory.id}
                    className="group flex items-start justify-between rounded-lg border p-4 transition-colors hover:bg-accent/50"
                  >
                    {/* 左侧内容 */}
                    <div
                      className="flex-1 cursor-pointer"
                      onClick={() => handleViewDetail(memory)}
                    >
                      <div className="flex items-center gap-2 mb-1">
                        <StateBadge state={memory.state} />
                      </div>
                      <p className="text-sm leading-relaxed">{memory.memory}</p>
                      <div className="mt-2 flex flex-wrap items-center gap-2">
                        {memory.user_id && (
                          <Badge variant="secondary" className="text-xs">
                            {memory.user_id}
                          </Badge>
                        )}
                        <CategoryBadges categories={memory.categories} max={3} />
                        {memory.created_at && (
                          <span className="text-xs text-muted-foreground">
                            {new Date(memory.created_at).toLocaleString("zh-CN")}
                          </span>
                        )}
                        <Link
                          href={`/memory/${memory.id}`}
                          className="text-xs text-primary hover:underline inline-flex items-center gap-0.5"
                          onClick={(e) => e.stopPropagation()}
                        >
                          详情页
                          <ExternalLink className="h-3 w-3" />
                        </Link>
                      </div>
                    </div>

                    {/* 右侧操作 */}
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
                          onClick={() => handleViewDetail(memory)}
                        >
                          <Eye className="mr-2 h-4 w-4" />
                          查看详情
                        </DropdownMenuItem>
                        <DropdownMenuItem onClick={() => handleEdit(memory)}>
                          <Pencil className="mr-2 h-4 w-4" />
                          编辑
                        </DropdownMenuItem>
                        <DropdownMenuSeparator />
                        <DropdownMenuItem
                          className="text-destructive focus:text-destructive"
                          onClick={() => handleDeleteClick(memory)}
                        >
                          <Trash2 className="mr-2 h-4 w-4" />
                          删除
                        </DropdownMenuItem>
                      </DropdownMenuContent>
                    </DropdownMenu>
                  </div>
                ))
              )}

              {/* 分页 */}
              {totalPages > 1 && (
                <div className="flex items-center justify-between pt-4 flex-wrap gap-3">
                  <p className="text-sm text-muted-foreground">
                    第 {currentPage} / {totalPages} 页，共 {filteredMemories.length} 条
                  </p>
                  <div className="flex items-center gap-1.5 flex-wrap">
                    <Button
                      variant="outline"
                      size="sm"
                      disabled={currentPage <= 1}
                      onClick={() => setCurrentPage((p) => p - 1)}
                    >
                      <ChevronLeft className="h-4 w-4" />
                      上一页
                    </Button>

                    {/* 智能页码显示 */}
                    {(() => {
                      const pages: (number | string)[] = [];
                      if (totalPages <= 7) {
                        for (let i = 1; i <= totalPages; i++) pages.push(i);
                      } else {
                        pages.push(1);
                        if (currentPage > 3) pages.push("...");
                        const start = Math.max(2, currentPage - 1);
                        const end = Math.min(totalPages - 1, currentPage + 1);
                        for (let i = start; i <= end; i++) pages.push(i);
                        if (currentPage < totalPages - 2) pages.push("...");
                        pages.push(totalPages);
                      }
                      return pages.map((page, idx) =>
                        typeof page === "string" ? (
                          <span key={`ellipsis-${idx}`} className="px-1 text-muted-foreground text-sm">
                            ···
                          </span>
                        ) : (
                          <Button
                            key={page}
                            variant={page === currentPage ? "default" : "outline"}
                            size="sm"
                            className="w-8 h-8 p-0"
                            onClick={() => setCurrentPage(page)}
                          >
                            {page}
                          </Button>
                        )
                      );
                    })()}

                    <Button
                      variant="outline"
                      size="sm"
                      disabled={currentPage >= totalPages}
                      onClick={() => setCurrentPage((p) => p + 1)}
                    >
                      下一页
                      <ChevronRight className="h-4 w-4" />
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
                            const page = Math.max(1, Math.min(totalPages, parseInt(jumpPage)));
                            setCurrentPage(page);
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
                            const page = Math.max(1, Math.min(totalPages, parseInt(jumpPage)));
                            setCurrentPage(page);
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
            </div>
          ) : (
            // 空状态
            <div className="flex flex-col items-center justify-center py-12 text-center">
              <Brain className="mb-4 h-16 w-16 text-muted-foreground/30" />
              <p className="text-lg font-medium text-muted-foreground">
                {searchText ? "未找到匹配的记忆" : "暂无记忆数据"}
              </p>
              <p className="mt-1 text-sm text-muted-foreground">
                {searchText
                  ? "尝试修改搜索关键词"
                  : "点击「添加记忆」按钮创建第一条记忆"}
              </p>
              {!searchText && (
                <Button
                  className="mt-4"
                  onClick={() => setAddDialogOpen(true)}
                >
                  <Plus className="mr-2 h-4 w-4" />
                  添加记忆
                </Button>
              )}
            </div>
          )}
        </CardContent>
      </Card>

      {/* 弹窗组件 */}
      <AddMemoryDialog
        open={addDialogOpen}
        onOpenChange={setAddDialogOpen}
        onSuccess={fetchMemories}
      />

      <EditMemoryDialog
        memory={selectedMemory}
        open={editDialogOpen}
        onOpenChange={setEditDialogOpen}
        onSuccess={fetchMemories}
      />

      <DeleteConfirmDialog
        open={deleteDialogOpen}
        onOpenChange={setDeleteDialogOpen}
        onConfirm={handleDelete}
        loading={deleteLoading}
        description={`确定要删除这条记忆吗？\n"${selectedMemory?.memory?.slice(0, 50)}${(selectedMemory?.memory?.length || 0) > 50 ? "..." : ""}"`}
      />

      {/* 详情面板 */}
      <MemoryDetailPanel
        memory={selectedMemory}
        open={detailPanelOpen}
        onClose={() => setDetailPanelOpen(false)}
      />
    </div>
  );
}
