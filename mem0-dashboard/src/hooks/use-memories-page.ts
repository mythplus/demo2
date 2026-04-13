/**
 * 记忆管理页面业务逻辑 Hook
 * 将 memories/page.tsx 中的状态管理和业务逻辑抽取到此处，
 * 页面组件只负责渲染，提升可维护性和可测试性。
 */
"use client";

import { useEffect, useState, useCallback, useMemo } from "react";
import { toast } from "@/hooks/use-toast";
import { mem0Api } from "@/lib/api";
import type { Memory, FilterParams } from "@/lib/api";
import { usePreferences } from "@/hooks/use-preferences";
import type { ViewMode } from "@/components/memories/view-toggle";

export function useMemoriesPage() {
  // 用户偏好设置
  const { preferences } = usePreferences();
  const sortOrder = preferences.sortOrder;

  // ============ 数据状态 ============
  const [memories, setMemories] = useState<Memory[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  // ============ 筛选状态 ============
  const [searchText, setSearchText] = useState("");
  const [filters, setFilters] = useState<FilterParams>({ state: "active" });
  const [currentPage, setCurrentPage] = useState(1);
  const [pageSize, setPageSize] = useState(preferences.pageSize);
  const [jumpPage, setJumpPage] = useState("");

  // ============ 视图模式 ============
  const [viewMode, setViewMode] = useState<ViewMode>("table");

  // ============ IME 中文输入法组合状态 ============
  const [isComposing, setIsComposing] = useState(false);

  // ============ 弹窗状态 ============
  const [addDialogOpen, setAddDialogOpen] = useState(false);
  const [editDialogOpen, setEditDialogOpen] = useState(false);
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [detailPanelOpen, setDetailPanelOpen] = useState(false);

  // ============ 当前操作的记忆 ============
  const [selectedMemory, setSelectedMemory] = useState<Memory | null>(null);
  const [deleteLoading, setDeleteLoading] = useState(false);

  // ============ 多选操作状态 ============
  const [selectionMode, setSelectionMode] = useState(false);
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [batchDeleteDialogOpen, setBatchDeleteDialogOpen] = useState(false);
  const [batchDeleteLoading, setBatchDeleteLoading] = useState(false);

  // ============ 数据获取 ============

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

  // ============ 派生数据（useMemo 优化） ============

  /** 所有唯一用户（按名称排序） */
  const uniqueUsers = useMemo(
    () =>
      (
        Array.from(
          new Set(memories.map((m) => m.user_id).filter(Boolean))
        ) as string[]
      ).sort((a, b) => a.localeCompare(b, "zh-CN", { numeric: true })),
    [memories]
  );

  /** 本地搜索过滤 + 排序后的记忆列表 */
  const filteredMemories = useMemo(() => {
    return memories
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
      .sort((a, b) => {
        const timeA = a.created_at ? new Date(a.created_at).getTime() : 0;
        const timeB = b.created_at ? new Date(b.created_at).getTime() : 0;
        return sortOrder === "newest" ? timeB - timeA : timeA - timeB;
      });
  }, [memories, searchText, sortOrder]);

  /** 分页 */
  const totalPages = Math.ceil(filteredMemories.length / pageSize);
  const paginatedMemories = useMemo(
    () =>
      filteredMemories.slice(
        (currentPage - 1) * pageSize,
        currentPage * pageSize
      ),
    [filteredMemories, currentPage, pageSize]
  );

  // ============ 筛选操作 ============

  const handleFiltersChange = useCallback((newFilters: FilterParams) => {
    setFilters(newFilters);
    setCurrentPage(1);
  }, []);

  const handleSearchChange = useCallback(
    (value: string) => {
      setSearchText(value);
      if (!isComposing) {
        setCurrentPage(1);
      }
    },
    [isComposing]
  );

  const handleCompositionStart = useCallback(() => {
    setIsComposing(true);
  }, []);

  const handleCompositionEnd = useCallback((value: string) => {
    setIsComposing(false);
    setSearchText(value);
    setCurrentPage(1);
  }, []);

  const handlePageSizeChange = useCallback((size: number) => {
    setPageSize(size);
    setCurrentPage(1);
  }, []);

  const handleJumpPage = useCallback(() => {
    if (jumpPage) {
      const page = Math.max(1, Math.min(totalPages, parseInt(jumpPage)));
      setCurrentPage(page);
      setJumpPage("");
    }
  }, [jumpPage, totalPages]);

  // ============ 单条删除 ============

  const handleDelete = useCallback(async () => {
    if (!selectedMemory) return;
    setDeleteLoading(true);
    try {
      await mem0Api.deleteMemory(selectedMemory.id);
      toast({
        title: "删除成功",
        description: "记忆已成功删除",
        variant: "success",
      });
      setDeleteDialogOpen(false);
      setSelectedMemory(null);
      fetchMemories();
    } catch (err) {
      console.error("删除失败:", err);
      toast({
        title: "删除失败",
        description: err instanceof Error ? err.message : "未知错误",
        variant: "destructive",
      });
    } finally {
      setDeleteLoading(false);
    }
  }, [selectedMemory, fetchMemories]);

  // ============ 多选操作 ============

  const handleToggleSelectionMode = useCallback(() => {
    setSelectionMode((prev) => {
      if (prev) setSelectedIds(new Set());
      return !prev;
    });
  }, []);

  const handleToggleSelect = useCallback((id: string) => {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) {
        next.delete(id);
      } else {
        next.add(id);
      }
      return next;
    });
  }, []);

  const handleToggleAll = useCallback(
    (checked: boolean) => {
      if (checked) {
        const allIds = new Set(
          filteredMemories
            .filter((m) => m.state !== "deleted")
            .map((m) => m.id)
        );
        setSelectedIds(allIds);
      } else {
        setSelectedIds(new Set());
      }
    },
    [filteredMemories]
  );

  const handleTogglePageAll = useCallback(
    (checked: boolean) => {
      if (checked) {
        const newIds = new Set(selectedIds);
        paginatedMemories.forEach((m) => {
          if (m.state !== "deleted") newIds.add(m.id);
        });
        setSelectedIds(newIds);
      } else {
        const newIds = new Set(selectedIds);
        paginatedMemories.forEach((m) => newIds.delete(m.id));
        setSelectedIds(newIds);
      }
    },
    [selectedIds, paginatedMemories]
  );

  const handleInvertSelection = useCallback(() => {
    const newIds = new Set<string>();
    filteredMemories.forEach((m) => {
      if (m.state !== "deleted" && !selectedIds.has(m.id)) {
        newIds.add(m.id);
      }
    });
    setSelectedIds(newIds);
  }, [filteredMemories, selectedIds]);

  const handleClearSelection = useCallback(() => {
    setSelectedIds(new Set());
  }, []);

  // ============ 批量删除 ============

  const handleBatchDelete = useCallback(async () => {
    if (selectedIds.size === 0) return;
    setBatchDeleteLoading(true);
    try {
      const result = await mem0Api.batchDeleteMemories(
        Array.from(selectedIds)
      );
      if (result.failed > 0) {
        toast({
          title: "部分删除失败",
          description: `成功 ${result.success} 条，失败 ${result.failed} 条`,
          variant: "destructive",
        });
      } else {
        toast({
          title: "批量删除成功",
          description: `已成功删除 ${result.success} 条记忆`,
          variant: "success",
        });
      }
      setBatchDeleteDialogOpen(false);
      setSelectedIds(new Set());
      setSelectionMode(false);
      fetchMemories();
    } catch (err) {
      console.error("批量删除失败:", err);
      toast({
        title: "批量删除失败",
        description: err instanceof Error ? err.message : "未知错误",
        variant: "destructive",
      });
    } finally {
      setBatchDeleteLoading(false);
    }
  }, [selectedIds, fetchMemories]);

  // ============ 记忆操作（打开弹窗） ============

  const handleEdit = useCallback((memory: Memory) => {
    setSelectedMemory(memory);
    setEditDialogOpen(true);
  }, []);

  const handleDeleteClick = useCallback((memory: Memory) => {
    setSelectedMemory(memory);
    setDeleteDialogOpen(true);
  }, []);

  const handleViewDetail = useCallback((memory: Memory) => {
    setSelectedMemory(memory);
    setDetailPanelOpen(true);
  }, []);

  // ============ 返回所有状态和操作 ============

  return {
    // 数据
    memories,
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
    isComposing,
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
  };
}
