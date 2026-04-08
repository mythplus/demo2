"use client";

import React from "react";
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
  CheckSquare,
  X,
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
import { ViewToggle } from "@/components/memories/view-toggle";
import { PageSizeSelector } from "@/components/memories/page-size-selector";
import { CategoryBadges } from "@/components/memories/category-badge";
import { StateBadge } from "@/components/memories/state-badge";
import { Checkbox } from "@/components/ui/checkbox";
import { MemoryListSkeleton } from "@/components/ui/skeleton";
import { useMemoriesPage } from "@/hooks/use-memories-page";

export default function MemoriesPage() {
  const {
    // 数据
    loading,
    error,
    filteredMemories,
    paginatedMemories,
    uniqueUsers,
    // 筛选 & 分页
    searchText,
    filters,
    currentPage,
    pageSize,
    jumpPage,
    totalPages,
    setJumpPage,
    setCurrentPage,
    handleSearchChange,
    handleCompositionStart,
    handleCompositionEnd,
    handleFiltersChange,
    handlePageSizeChange,
    handleJumpPage,
    // 视图
    viewMode,
    setViewMode,
    // 弹窗
    addDialogOpen,
    setAddDialogOpen,
    editDialogOpen,
    setEditDialogOpen,
    deleteDialogOpen,
    setDeleteDialogOpen,
    detailPanelOpen,
    setDetailPanelOpen,
    batchDeleteDialogOpen,
    setBatchDeleteDialogOpen,
    // 当前操作
    selectedMemory,
    deleteLoading,
    batchDeleteLoading,
    // 操作方法
    fetchMemories,
    handleDelete,
    handleEdit,
    handleDeleteClick,
    handleViewDetail,
    // 多选
    selectionMode,
    selectedIds,
    handleToggleSelectionMode,
    handleToggleSelect,
    handleToggleAll,
    handleTogglePageAll,
    handleInvertSelection,
    handleClearSelection,
    handleBatchDelete,
  } = useMemoriesPage();

  return (
    <div className="space-y-6">
      {/* 页面头部 */}
      <div>
        <h2 className="text-2xl font-bold tracking-tight">记忆管理</h2>
        <p className="text-sm text-muted-foreground">
          管理所有存储的记忆条目，支持添加、编辑、删除操作
        </p>
      </div>

      {/* 筛选栏 */}
      <Card>
        <CardContent className="pt-6">
          <div className="space-y-3">
            {/* 搜索框 */}
            <div className="relative">
              <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
              <Input
                placeholder="搜索记忆内容、用户 ID..."
                value={searchText}
                onChange={(e) => handleSearchChange(e.target.value)}
                onCompositionStart={handleCompositionStart}
                onCompositionEnd={(e) =>
                  handleCompositionEnd((e.target as HTMLInputElement).value)
                }
                className="pl-9"
              />
            </div>

            {/* 视图切换 + 多维筛选器 + 操作按钮 */}
            <div className="flex items-start gap-2">
              <div className="flex-1 min-w-0">
                <MemoryFilters
                  filters={filters}
                  onFiltersChange={handleFiltersChange}
                  users={uniqueUsers}
                  prefix={<ViewToggle mode={viewMode} onChange={setViewMode} className="h-8" />}
                />
              </div>
              <div className="flex items-center gap-2 shrink-0">
                <Button variant="outline" size="sm" onClick={fetchMemories} className="h-8 gap-1.5">
                  <RefreshCw className={`h-4 w-4 ${loading ? "animate-spin" : ""}`} />
                  刷新
                </Button>
                <Button
                  variant={selectionMode ? "secondary" : "outline"}
                  onClick={handleToggleSelectionMode}
                  size="sm"
                  className={selectionMode ? "border-primary text-primary" : ""}
                >
                  <CheckSquare className="mr-1.5 h-4 w-4" />
                  <span className="hidden sm:inline">{selectionMode ? "退出多选" : "多选操作"}</span>
                  <span className="sm:hidden">{selectionMode ? "退出" : "多选"}</span>
                </Button>
                <Button size="sm" onClick={() => setAddDialogOpen(true)}>
                  <Plus className="mr-1.5 h-4 w-4" />
                  <span className="hidden sm:inline">添加记忆</span>
                  <span className="sm:hidden">添加</span>
                </Button>
              </div>
            </div>
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

      {/* 多选操作栏 */}
      {selectionMode && (
        <Card className="border-primary/30">
          <CardContent className="flex items-center justify-between py-3 px-4">
            <div className="flex items-center gap-3">
              <CheckSquare className="h-4 w-4 text-primary" />
              <span className="text-base font-medium">
                已选择 <span className="text-primary font-bold text-lg">{selectedIds.size}</span> 条记忆
              </span>
              <Button variant="outline" size="sm" className="text-sm" onClick={() => handleToggleAll(true)}>
                全选
              </Button>
              <Button variant="outline" size="sm" className="text-sm" onClick={handleInvertSelection}>
                反选
              </Button>
              {selectedIds.size > 0 && (
                <Button variant="outline" size="sm" className="text-sm" onClick={handleClearSelection}>
                  取消选择
                </Button>
              )}
            </div>
            <div className="flex items-center gap-2">
              <Button
                variant="destructive"
                size="sm"
                disabled={selectedIds.size === 0}
                onClick={() => setBatchDeleteDialogOpen(true)}
              >
                <Trash2 className="mr-1.5 h-3.5 w-3.5" />
                删除选中（{selectedIds.size}）
              </Button>
              <Button variant="outline" size="sm" onClick={handleToggleSelectionMode}>
                <X className="mr-1 h-3.5 w-3.5" />
                退出
              </Button>
            </div>
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
                {selectionMode && selectedIds.size > 0 && (
                  <span className="ml-2 text-primary">（已选 {selectedIds.size} 条）</span>
                )}
              </CardDescription>
            </div>
            <PageSizeSelector value={pageSize} onChange={handlePageSizeChange} />
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
                  selectionMode={selectionMode}
                  selectedIds={selectedIds}
                  onToggleSelect={handleToggleSelect}
                  onToggleAll={handleTogglePageAll}
                />
              ) : (
                /* 列表视图 */
                paginatedMemories.map((memory) => (
                  <div
                    key={memory.id}
                    className={`group flex items-start justify-between rounded-lg border p-4 transition-colors hover:bg-accent/50 ${selectionMode && selectedIds.has(memory.id) ? "bg-accent/30 border-primary/30" : ""}`}
                    onClick={() => {
                      if (selectionMode && memory.state !== "deleted") {
                        handleToggleSelect(memory.id);
                      }
                    }}
                  >
                    {/* 多选复选框 */}
                    {selectionMode && (
                      <div className="mr-3 pt-0.5 shrink-0">
                        <Checkbox
                          checked={selectedIds.has(memory.id)}
                          onCheckedChange={() => handleToggleSelect(memory.id)}
                          onClick={(e) => e.stopPropagation()}
                          disabled={memory.state === "deleted"}
                          aria-label={`选择记忆 ${memory.id}`}
                        />
                      </div>
                    )}
                    {/* 左侧内容 */}
                    <div
                      className="flex-1 min-w-0 cursor-pointer"
                      onClick={(e) => {
                        if (selectionMode) {
                          e.stopPropagation();
                          if (memory.state !== "deleted") handleToggleSelect(memory.id);
                        } else {
                          handleViewDetail(memory);
                        }
                      }}
                    >
                      <div className="flex items-center gap-2 mb-1">
                        <StateBadge state={memory.state} />
                      </div>
                      <p className="text-sm leading-relaxed line-clamp-2 break-all">{memory.memory}</p>
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
                        <DropdownMenuItem onClick={() => handleViewDetail(memory)}>
                          <Eye className="mr-2 h-4 w-4" />
                          查看详情
                        </DropdownMenuItem>
                        <DropdownMenuItem onClick={() => handleEdit(memory)} disabled={memory.state === "deleted"}>
                          <Pencil className="mr-2 h-4 w-4" />
                          编辑
                        </DropdownMenuItem>
                        <DropdownMenuSeparator />
                        <DropdownMenuItem
                          className="text-destructive focus:text-destructive"
                          onClick={() => handleDeleteClick(memory)}
                          disabled={memory.state === "deleted"}
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

                    <span className="text-sm font-medium px-2">
                      {currentPage} / {totalPages}
                    </span>

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
                          if (e.key === "Enter") handleJumpPage();
                        }}
                      />
                      <span className="text-sm text-muted-foreground">页</span>
                      <Button variant="outline" size="sm" className="h-8" onClick={handleJumpPage}>
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
                <Button className="mt-4" onClick={() => setAddDialogOpen(true)}>
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

      {/* 批量删除确认弹窗 */}
      <DeleteConfirmDialog
        open={batchDeleteDialogOpen}
        onOpenChange={setBatchDeleteDialogOpen}
        onConfirm={handleBatchDelete}
        loading={batchDeleteLoading}
        title="批量删除确认"
        description={`确定要删除选中的 ${selectedIds.size} 条记忆吗？此操作不可撤销。`}
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
