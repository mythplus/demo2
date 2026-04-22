/**
 * 记忆管理页面业务逻辑 Hook
 * 将 memories/page.tsx 中的状态管理和业务逻辑抽取到此处，
 * 页面组件只负责渲染，提升可维护性和可测试性。
 */
"use client";

import { useEffect, useState, useCallback, useRef } from "react";

import { toast } from "@/hooks/use-toast";
import { mem0Api } from "@/lib/api";
import type { Memory, FilterParams, PaginatedMemoriesResponse, UserInfo } from "@/lib/api";
import { usePreferences } from "@/hooks/use-preferences";
import { useUIStore } from "@/store";


export function useMemoriesPage() {
  // 用户偏好设置
  const { preferences, savePreferences } = usePreferences();
  const sortOrder = preferences.sortOrder;

  // ============ 数据状态 ============
  const [memories, setMemories] = useState<Memory[]>([]);
  const [totalCount, setTotalCount] = useState(0);
  const [totalIsEstimate, setTotalIsEstimate] = useState(false);
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

  // ============ 视图模式（全局 UI store，避免页面切换后状态漂移） ============
  const viewMode = useUIStore((state) => state.viewMode);
  const setViewMode = useUIStore((state) => state.setViewMode);
  const hydratePersistedState = useUIStore((state) => state.hydratePersistedState);


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

  const memoriesAbortRef = useRef<AbortController | null>(null);
  const usersAbortRef = useRef<AbortController | null>(null);
  const bulkSelectionAbortRef = useRef<AbortController | null>(null);

  const totalPages = Math.max(1, Math.ceil(totalCount / pageSize));


  // ============ 数据获取 ============

  const fetchUsers = useCallback(async () => {
    usersAbortRef.current?.abort();
    const controller = new AbortController();
    usersAbortRef.current = controller;

    try {
      const users = await mem0Api.getMemoryUsers(controller.signal);
      if (usersAbortRef.current !== controller) {
        return;
      }
      const ids = Array.isArray(users)
        ? (users as UserInfo[])
            .map((u) => u.user_id)
            .filter(Boolean)
            .sort((a, b) => a.localeCompare(b, "zh-CN", { numeric: true }))
        : [];
      setUniqueUsers(ids);
    } catch (err) {
      if (err instanceof DOMException && err.name === "AbortError") {
        return;
      }
      setUniqueUsers([]);
    } finally {
      if (usersAbortRef.current === controller) {
        usersAbortRef.current = null;
      }
    }
  }, []);

  const fetchMemories = useCallback(async () => {
    memoriesAbortRef.current?.abort();
    const controller = new AbortController();
    memoriesAbortRef.current = controller;

    setLoading(true);
    setError("");
    try {
      const apiFilters: FilterParams = {
        ...filters,
        search: debouncedSearchText.trim() || undefined,
        page: currentPage,
        page_size: pageSize,
        sort_by: "created_at",
        sort_order: sortOrder === "oldest" ? "asc" : "desc",
      };
      const data = await mem0Api.getMemories(apiFilters, controller.signal);
      if (memoriesAbortRef.current !== controller) {
        return;
      }
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
      setTotalIsEstimate(Boolean(pageData.total_is_estimate));

      const safeTotalPages = Math.max(1, pageData.total_pages || 1);
      if (currentPage > safeTotalPages) {
        setCurrentPage(safeTotalPages);
      }
    } catch (err) {
      if (err instanceof DOMException && err.name === "AbortError") {
        return;
      }
      setError(err instanceof Error ? err.message : "获取记忆列表失败");
      setMemories([]);
      setTotalCount(0);
      setTotalIsEstimate(false);
    } finally {
      if (memoriesAbortRef.current === controller) {
        memoriesAbortRef.current = null;
        setLoading(false);
      }
    }
  }, [filters, debouncedSearchText, currentPage, pageSize, sortOrder]);


  // 搜索防抖：400ms（兼顾中文 IME 输入法组合延迟，减少无效 API 请求）
  useEffect(() => {
    const timer = setTimeout(() => {
      setDebouncedSearchText(searchText);
    }, 400);
    return () => clearTimeout(timer);
  }, [searchText]);

  useEffect(() => {
    hydratePersistedState();
  }, [hydratePersistedState]);

  useEffect(() => {
    fetchMemories();
  }, [fetchMemories]);


  useEffect(() => {
    fetchUsers();
  }, [fetchUsers]);

  useEffect(() => {
    setPageSize(preferences.pageSize);
  }, [preferences.pageSize]);

  useEffect(() => {
    return () => {
      memoriesAbortRef.current?.abort();
      usersAbortRef.current?.abort();
      bulkSelectionAbortRef.current?.abort();
    };
  }, []);

  // ============ 派生数据（B4 P2-5: 删除死代码 filteredMemories/paginatedMemories，直接用 memories） ============

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
        bulkSelectionAbortRef.current?.abort();
        const controller = new AbortController();
        bulkSelectionAbortRef.current = controller;
        setSelectAllLoading(true);
        try {
          // 构建与当前列表一致的筛选参数（不含分页），调用后端获取所有 ID
          const apiFilters: FilterParams = {
            ...filters,
            search: debouncedSearchText.trim() || undefined,
          };
          const result = await mem0Api.getAllMemoryIds(apiFilters, controller.signal);
          if (bulkSelectionAbortRef.current !== controller) {
            return;
          }
          setSelectedIds(new Set(result.ids));
          toast({
            title: "全选成功",
            description: `已选中 ${result.total} 条记忆`,
          });
        } catch (err) {
          if (err instanceof DOMException && err.name === "AbortError") {
            return;
          }
          console.error("全选失败:", err);
          toast({
            title: "全选失败",
            description: err instanceof Error ? err.message : "未知错误",
            variant: "destructive",
          });
        } finally {
          if (bulkSelectionAbortRef.current === controller) {
            bulkSelectionAbortRef.current = null;
            setSelectAllLoading(false);
          }
        }
      } else {
        bulkSelectionAbortRef.current?.abort();
        bulkSelectionAbortRef.current = null;
        setSelectAllLoading(false);
        setSelectedIds(new Set());
      }

    },
    [filters, debouncedSearchText]
  );


  const handleTogglePageAll = useCallback(
    (checked: boolean) => {
      if (checked) {
      const newIds = new Set(selectedIds);
        memories.forEach((m) => {
          newIds.add(m.id);
        });
        setSelectedIds(newIds);
      } else {
        const newIds = new Set(selectedIds);
        memories.forEach((m) => newIds.delete(m.id));
        setSelectedIds(newIds);
      }
    },
    [selectedIds, memories]
  );

  const [invertLoading, setInvertLoading] = useState(false);

  const handleInvertSelection = useCallback(async () => {
    bulkSelectionAbortRef.current?.abort();
    const controller = new AbortController();
    bulkSelectionAbortRef.current = controller;
    setInvertLoading(true);
    try {
      // 从后端获取当前筛选条件下的所有记忆 ID
      const apiFilters: FilterParams = {
        ...filters,
        search: debouncedSearchText.trim() || undefined,
      };
      const result = await mem0Api.getAllMemoryIds(apiFilters, controller.signal);
      if (bulkSelectionAbortRef.current !== controller) {
        return;
      }
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
      if (err instanceof DOMException && err.name === "AbortError") {
        return;
      }
      console.error("反选失败:", err);
      toast({
        title: "反选失败",
        description: err instanceof Error ? err.message : "未知错误",
        variant: "destructive",
      });
    } finally {
      if (bulkSelectionAbortRef.current === controller) {
        bulkSelectionAbortRef.current = null;
        setInvertLoading(false);
      }
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
    uniqueUsers,
    totalCount,
    totalIsEstimate,

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
