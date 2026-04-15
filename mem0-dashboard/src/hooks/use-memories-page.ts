/**
 * 记忆管理页面业务逻辑 Hook
 * 将 memories/page.tsx 中的状态管理和业务逻辑抽取到此处，
 * 页面组件只负责渲染，提升可维护性和可测试性。
 */
"use client";

import { useEffect, useState, useCallback } from "react";
import { toast } from "@/hooks/use-toast";
import { mem0Api } from "@/lib/api";
import type { Memory, FilterParams, PaginatedMemoriesResponse, UserInfo } from "@/lib/api";
import { usePreferences } from "@/hooks/use-preferences";
import type { ViewMode } from "@/components/memories/view-toggle";

export function useMemoriesPage() {
  // 用户偏好设置
  const { preferences, savePreferences } = usePreferences();
  const sortOrder = preferences.sortOrder;

  // ============ 数据状态 ============
  const [memories, setMemories] = useState<Memory[]>([]);
  const [totalCount, setTotalCount] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [uniqueUsers, setUniqueUsers] = useState<string[]>([]);

  // ============ 筛选状态 ============
  const [searchText, setSearchText] = useState("");
  const [debouncedSearchText, setDebouncedSearchText] = useState("");
  const [filters, setFilters] = useState<FilterParams>({});
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

  const totalPages = Math.max(1, Math.ceil(totalCount / pageSize));

  // ============ 数据获取 ============

  const fetchUsers = useCallback(async () => {
    try {
      const users = await mem0Api.getMemoryUsers();
      const ids = Array.isArray(users)
        ? (users as UserInfo[])
            .map((u) => u.user_id)
            .filter(Boolean)
            .sort((a, b) => a.localeCompare(b, "zh-CN", { numeric: true }))
        : [];
      setUniqueUsers(ids);
    } catch {
      setUniqueUsers([]);
    }
  }, []);

  const fetchMemories = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const apiFilters: FilterParams = {
        ...filters,
        search: debouncedSearchText.trim() || undefined,
        page: currentPage,
        page_size: pageSize,
        sort_by: sortOrder === "oldest" ? "created_at" : "created_at",
        sort_order: sortOrder === "oldest" ? "asc" : "desc",
      };
      const data = await mem0Api.getMemories(apiFilters);
      const pageData: PaginatedMemoriesResponse = Array.isArray(data)
        ? {
            items: data,
            total: data.length,
            page: currentPage,
            page_size: pageSize,
            total_pages: Math.max(1, Math.ceil(data.length / pageSize)),
          }
        : data;
      setMemories(pageData.items || []);
      setTotalCount(pageData.total || 0);

      const safeTotalPages = Math.max(1, pageData.total_pages || 1);
      if (currentPage > safeTotalPages) {
        setCurrentPage(safeTotalPages);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "获取记忆列表失败");
      setMemories([]);
      setTotalCount(0);
    } finally {
      setLoading(false);
    }
  }, [filters, debouncedSearchText, currentPage, pageSize, sortOrder]);

  useEffect(() => {
    const timer = setTimeout(() => {
      setDebouncedSearchText(searchText);
    }, 300);
    return () => clearTimeout(timer);
  }, [searchText]);

  useEffect(() => {
    fetchMemories();
  }, [fetchMemories]);

  useEffect(() => {
    fetchUsers();
  }, [fetchUsers]);

  useEffect(() => {
    setPageSize(preferences.pageSize);
  }, [preferences.pageSize]);

  // ============ 派生数据 ============

  const filteredMemories = memories;
  const paginatedMemories = memories;

  // ============ 筛选操作 ============

  const handleFiltersChange = useCallback((newFilters: FilterParams) => {
    setFilters(newFilters);
    setCurrentPage(1);
    setSelectedIds(new Set());
  }, []);

  const handleSearchChange = useCallback(
    (value: string) => {
      setSearchText(value);
      if (!isComposing) {
        setCurrentPage(1);
        setSelectedIds(new Set());
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
    setSelectedIds(new Set());
  }, []);

  const handlePageSizeChange = useCallback((size: number) => {
    setPageSize(size);
    savePreferences({ pageSize: size });
    setCurrentPage(1);
    setSelectedIds(new Set());
  }, [savePreferences]);

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
      setSelectedIds((prev) => {
        const next = new Set(prev);
        next.delete(selectedMemory.id);
        return next;
      });
      fetchMemories();
      fetchUsers();
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
  }, [selectedMemory, fetchMemories, fetchUsers]);

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

  const [selectAllLoading, setSelectAllLoading] = useState(false);

  const handleToggleAll = useCallback(
    async (checked: boolean) => {
      if (checked) {
        setSelectAllLoading(true);
        try {
          // 构建与当前列表一致的筛选参数（不含分页），调用后端获取所有 ID
          const apiFilters: FilterParams = {
            ...filters,
            search: debouncedSearchText.trim() || undefined,
          };
          const result = await mem0Api.getAllMemoryIds(apiFilters);
          setSelectedIds(new Set(result.ids));
          toast({
            title: "全选成功",
            description: `已选中 ${result.total} 条记忆`,
          });
        } catch (err) {
          console.error("全选失败:", err);
          toast({
            title: "全选失败",
            description: err instanceof Error ? err.message : "未知错误",
            variant: "destructive",
          });
        } finally {
          setSelectAllLoading(false);
        }
      } else {
        setSelectedIds(new Set());
      }
    },
    [filters, debouncedSearchText]
  );

  const handleTogglePageAll = useCallback(
    (checked: boolean) => {
      if (checked) {
        const newIds = new Set(selectedIds);
        paginatedMemories.forEach((m) => {
          newIds.add(m.id);
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

  const [invertLoading, setInvertLoading] = useState(false);

  const handleInvertSelection = useCallback(async () => {
    setInvertLoading(true);
    try {
      // 从后端获取当前筛选条件下的所有记忆 ID
      const apiFilters: FilterParams = {
        ...filters,
        search: debouncedSearchText.trim() || undefined,
      };
      const result = await mem0Api.getAllMemoryIds(apiFilters);
      const allIds = new Set(result.ids);
      // 反选：在所有 ID 中，已选的去掉，未选的加上
      const newIds = new Set<string>();
      allIds.forEach((id) => {
        if (!selectedIds.has(id)) {
          newIds.add(id);
        }
      });
      setSelectedIds(newIds);
    } catch (err) {
      console.error("反选失败:", err);
      toast({
        title: "反选失败",
        description: err instanceof Error ? err.message : "未知错误",
        variant: "destructive",
      });
    } finally {
      setInvertLoading(false);
    }
  }, [filters, debouncedSearchText, selectedIds]);

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
      fetchUsers();
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
  }, [selectedIds, fetchMemories, fetchUsers]);

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
    totalCount,

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
    selectAllLoading,
    handleToggleSelectionMode,
    handleToggleSelect,
    handleToggleAll,
    handleTogglePageAll,
    handleInvertSelection,
    invertLoading,
    handleClearSelection,
    handleBatchDelete,
  };
}
