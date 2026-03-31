"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import {
  Users,
  Brain,
  Search,
  RefreshCw,
  ChevronRight,
  ChevronLeft,
  Trash2,
  Loader2,
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
import { DeleteConfirmDialog } from "@/components/memories/delete-confirm-dialog";
import { mem0Api } from "@/lib/api";
import type { Memory, UserInfo } from "@/lib/api";

export default function UsersPage() {
  const [users, setUsers] = useState<UserInfo[]>([]);
  const [loading, setLoading] = useState(true);
  const [searchText, setSearchText] = useState("");
  const [error, setError] = useState("");

  // 分页状态
  const [currentPage, setCurrentPage] = useState(1);
  const [jumpPage, setJumpPage] = useState("");
  const pageSize = 10;

  // 删除状态
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [deleteUserId, setDeleteUserId] = useState<string>("");
  const [deleteLoading, setDeleteLoading] = useState(false);

  const fetchUsers = async () => {
    setLoading(true);
    setError("");
    try {
      const memories = await mem0Api.getMemories();
      const memoriesArr = Array.isArray(memories) ? memories : [];

      // 从记忆数据中聚合用户信息
      const userMap = new Map<string, UserInfo>();

      memoriesArr.forEach((m: Memory) => {
        if (!m.user_id) return;
        const existing = userMap.get(m.user_id);
        if (existing) {
          existing.memory_count += 1;
          // 更新最后活跃时间
          if (m.updated_at || m.created_at) {
            const time = m.updated_at || m.created_at;
            if (!existing.last_active || (time && time > existing.last_active)) {
              existing.last_active = time;
            }
          }
        } else {
          userMap.set(m.user_id, {
            user_id: m.user_id,
            memory_count: 1,
            last_active: m.updated_at || m.created_at,
          });
        }
      });

      // 按记忆数量排序
      const userList = Array.from(userMap.values()).sort(
        (a, b) => b.memory_count - a.memory_count
      );
      setUsers(userList);
    } catch (err) {
      setError(err instanceof Error ? err.message : "获取用户列表失败");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchUsers();
  }, []);

  // 搜索过滤
  const filteredUsers = users.filter((u) => {
    if (!searchText.trim()) return true;
    return u.user_id.toLowerCase().includes(searchText.toLowerCase());
  });

  // 分页计算
  const totalPages = Math.max(1, Math.ceil(filteredUsers.length / pageSize));
  const paginatedUsers = filteredUsers.slice(
    (currentPage - 1) * pageSize,
    currentPage * pageSize
  );

  // 搜索时重置页码
  useEffect(() => {
    setCurrentPage(1);
  }, [searchText]);

  // 删除用户所有记忆
  const handleDeleteUser = async () => {
    if (!deleteUserId) return;
    setDeleteLoading(true);
    try {
      await mem0Api.deleteAllMemories(deleteUserId);
      setDeleteDialogOpen(false);
      setDeleteUserId("");
      fetchUsers();
    } catch (err) {
      console.error("删除失败:", err);
    } finally {
      setDeleteLoading(false);
    }
  };

  // 统计
  const totalMemories = users.reduce((sum, u) => sum + u.memory_count, 0);

  return (
    <div className="space-y-4">
      {/* 页面头部 */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold tracking-tight">用户管理</h2>
          <p className="text-muted-foreground">
            查看和管理所有拥有记忆的用户，数据从记忆中自动聚合
          </p>
        </div>
        <Button variant="outline" size="icon" onClick={fetchUsers}>
          <RefreshCw className={`h-4 w-4 ${loading ? "animate-spin" : ""}`} />
        </Button>
      </div>

      {/* 统计卡片 */}
      <div className="grid gap-4 md:grid-cols-3">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 px-4 pt-3 pb-1">
            <CardTitle className="text-sm font-medium">用户总数</CardTitle>
            <Users className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent className="px-4 pb-3 pt-0">
            <div className="text-2xl font-bold">
              {loading ? "..." : users.length}
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 px-4 pt-3 pb-1">
            <CardTitle className="text-sm font-medium">记忆总数</CardTitle>
            <Brain className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent className="px-4 pb-3 pt-0">
            <div className="text-2xl font-bold">
              {loading ? "..." : totalMemories}
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 px-4 pt-3 pb-1">
            <CardTitle className="text-sm font-medium">
              平均记忆数
            </CardTitle>
            <Brain className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent className="px-4 pb-3 pt-0">
            <div className="text-2xl font-bold">
              {loading
                ? "..."
                : users.length > 0
                ? (totalMemories / users.length).toFixed(1)
                : 0}
            </div>
          </CardContent>
        </Card>
      </div>

      {/* 搜索栏 */}
      <div className="relative">
        <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
        <Input
          placeholder="搜索用户 ID..."
          value={searchText}
          onChange={(e) => setSearchText(e.target.value)}
          className="pl-9 pr-9"
        />
        {searchText && (
          <button
            type="button"
            onClick={() => setSearchText("")}
            className="absolute right-2 top-1/2 -translate-y-1/2 rounded-md border border-red-300 p-1 text-red-500 hover:bg-red-50 hover:text-red-600 dark:border-red-800 dark:text-red-400 dark:hover:bg-red-900/30 dark:hover:text-red-300 transition-colors"
          >
            <X className="h-4 w-4" />
          </button>
        )}
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

      {/* 用户列表 */}
      <Card>
        <CardHeader>
          <CardTitle>用户列表</CardTitle>
        </CardHeader>
        <CardContent>
          {loading ? (
            <div className="space-y-3">
              {[1, 2, 3, 4].map((i) => (
                <div
                  key={i}
                  className="h-16 animate-pulse rounded-lg bg-muted"
                />
              ))}
            </div>
          ) : filteredUsers.length > 0 ? (
            <div className="space-y-2">
              {paginatedUsers.map((user) => (
                <div
                  key={user.user_id}
                  className="group flex items-center justify-between rounded-lg border p-4 transition-colors hover:bg-accent/50"
                >
                  {/* 用户信息 */}
                  <Link
                    href={`/users/${encodeURIComponent(user.user_id)}`}
                    className="flex flex-1 items-center gap-4"
                  >
                    {/* 头像 */}
                    <div className="flex h-10 w-10 items-center justify-center rounded-full bg-primary/10 text-primary font-bold">
                      {user.user_id.charAt(0).toUpperCase()}
                    </div>

                    {/* 信息 */}
                    <div className="flex-1">
                      <p className="font-medium">{user.user_id}</p>
                      <div className="flex items-center gap-3 mt-1">
                        <span className="text-xs text-muted-foreground">
                          <Brain className="mr-1 inline h-3 w-3" />
                          {user.memory_count} 条记忆
                        </span>
                        {user.last_active && (
                          <span className="text-xs text-muted-foreground">
                            最后活跃:{" "}
                            {new Date(user.last_active).toLocaleString(
                              "zh-CN"
                            )}
                          </span>
                        )}
                      </div>
                    </div>

                    {/* 记忆数量 Badge */}
                    <Badge variant="secondary">{user.memory_count}</Badge>
                    <ChevronRight className="h-4 w-4 text-muted-foreground" />
                  </Link>

                  {/* 删除按钮 */}
                  <Button
                    variant="ghost"
                    size="icon"
                    className="ml-2 shrink-0 opacity-0 group-hover:opacity-100 transition-opacity text-destructive hover:text-destructive"
                    title="删除用户及其所有记忆"
                    onClick={(e) => {
                      e.preventDefault();
                      setDeleteUserId(user.user_id);
                      setDeleteDialogOpen(true);
                    }}
                  >
                    <Trash2 className="h-4 w-4" />
                  </Button>
                </div>
              ))}
            </div>
          ) : (
            <div className="flex flex-col items-center justify-center py-12 text-center">
              <Users className="mb-4 h-16 w-16 text-muted-foreground/30" />
              <p className="text-lg font-medium text-muted-foreground">
                {searchText ? "未找到匹配的用户" : "暂无用户数据"}
              </p>
              <p className="mt-1 text-sm text-muted-foreground">
                {searchText
                  ? "尝试修改搜索关键词"
                  : "当记忆数据中包含 user_id 时，用户将自动出现在这里"}
              </p>
            </div>
          )}

          {/* 分页控件 */}
          {!loading && filteredUsers.length > pageSize && (
            <div className="flex items-center justify-between pt-4 border-t mt-4 flex-wrap gap-3">
              <p className="text-sm text-muted-foreground">
                显示第 {(currentPage - 1) * pageSize + 1}-{Math.min(currentPage * pageSize, filteredUsers.length)} 条，共 {filteredUsers.length} 条
              </p>
              <div className="flex items-center gap-1.5">
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => setCurrentPage((p) => Math.max(1, p - 1))}
                  disabled={currentPage <= 1}
                >
                  <ChevronLeft className="h-4 w-4 mr-1" />
                  上一页
                </Button>

                {/* 智能页码显示 */}
                {(() => {
                  const pages: (number | string)[] = [];
                  if (totalPages <= 7) {
                    // 页数较少时全部显示
                    for (let i = 1; i <= totalPages; i++) pages.push(i);
                  } else {
                    // 始终显示第1页
                    pages.push(1);
                    if (currentPage > 3) pages.push("...");
                    // 当前页附近的页码
                    const start = Math.max(2, currentPage - 1);
                    const end = Math.min(totalPages - 1, currentPage + 1);
                    for (let i = start; i <= end; i++) pages.push(i);
                    if (currentPage < totalPages - 2) pages.push("...");
                    // 始终显示最后一页
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
                  onClick={() => setCurrentPage((p) => Math.min(totalPages, p + 1))}
                  disabled={currentPage >= totalPages}
                >
                  下一页
                  <ChevronRight className="h-4 w-4 ml-1" />
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
        </CardContent>
      </Card>

      {/* 删除确认弹窗 */}
      <DeleteConfirmDialog
        open={deleteDialogOpen}
        onOpenChange={setDeleteDialogOpen}
        onConfirm={handleDeleteUser}
        loading={deleteLoading}
        title="删除用户"
        description={`确定要删除用户 "${deleteUserId}" 吗？该用户及其所有记忆数据将被永久删除，此操作不可撤销。`}
      />
    </div>
  );
}
