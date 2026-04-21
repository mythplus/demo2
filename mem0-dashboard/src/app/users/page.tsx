"use client";

import React, { useEffect, useState, useRef, useCallback } from "react";
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
import { toast } from "@/hooks/use-toast";
import { mem0Api } from "@/lib/api";
import type { UserInfo } from "@/lib/api";

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

  const usersAbortRef = useRef<AbortController | null>(null);

  const fetchUsers = useCallback(async () => {
    usersAbortRef.current?.abort();
    const controller = new AbortController();
    usersAbortRef.current = controller;

    setLoading(true);
    setError("");
    try {
      const data = await mem0Api.getMemoryUsers(controller.signal);
      if (usersAbortRef.current !== controller) return;
      setUsers(Array.isArray(data) ? (data as UserInfo[]) : []);
    } catch (err) {
      if (err instanceof DOMException && err.name === "AbortError") return;
      setError(err instanceof Error ? err.message : "获取用户列表失败");
    } finally {
      if (usersAbortRef.current === controller) {
        usersAbortRef.current = null;
        setLoading(false);
      }
    }
  }, []);

  useEffect(() => {
    fetchUsers();
    return () => { usersAbortRef.current?.abort(); };
  }, [fetchUsers]);

  // 搜索过滤 + 前缀匹配优先排序
  const filteredUsers = users
    .filter((u) => {
      if (!searchText.trim()) return true;
      return u.user_id.toLowerCase().includes(searchText.toLowerCase());
    })
    .sort((a, b) => {
      if (!searchText.trim()) return 0;
      const keyword = searchText.toLowerCase();
      const aStartsWith = a.user_id.toLowerCase().startsWith(keyword);
      const bStartsWith = b.user_id.toLowerCase().startsWith(keyword);
      if (aStartsWith && !bStartsWith) return -1;
      if (!aStartsWith && bStartsWith) return 1;
      return 0;
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
      await mem0Api.hardDeleteUser(deleteUserId);
      toast({
        title: "删除成功",
        description: `用户 "${deleteUserId.length > 20 ? deleteUserId.slice(0, 20) + "..." : deleteUserId}" 及其所有数据已永久删除`,
        variant: "success",
      });
      setDeleteDialogOpen(false);
      setDeleteUserId("");
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
  };

  // 统计
  const totalMemories = users.reduce((sum, u) => sum + u.memory_count, 0);

  return (
    <div className="space-y-4">
      {/* 页面头部 */}
      <div>
        <h2 className="text-xl font-bold tracking-tight">用户管理</h2>
        <p className="text-sm text-muted-foreground">
          查看和管理所有拥有记忆的用户，数据从记忆中自动聚合
        </p>
      </div>

      {/* 统计卡片 */}
      <div className="grid gap-4 md:grid-cols-3">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">用户总数</CardTitle>
            <Users className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {loading ? "..." : users.length}
            </div>
            <p className="text-xs text-muted-foreground">拥有记忆的独立用户</p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">记忆总数</CardTitle>
            <Brain className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {loading ? "..." : totalMemories}
            </div>
            <p className="text-xs text-muted-foreground">所有用户的活跃记忆</p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">平均记忆数</CardTitle>
            <Brain className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {loading
                ? "..."
                : users.length > 0
                ? (totalMemories / users.length).toFixed(1)
                : 0}
            </div>
            <p className="text-xs text-muted-foreground">每位用户平均记忆条数</p>
          </CardContent>
        </Card>
      </div>

      {/* 搜索栏 */}
      <div className="flex items-center gap-2">
        <div className="relative flex-1">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            placeholder="搜索用户 ID..."
            value={searchText}
            onChange={(e) => setSearchText(e.target.value)}
            className="pl-9 pr-8"
          />
          {searchText && (
            <button
              type="button"
              onClick={() => setSearchText("")}
              className="absolute right-1.5 top-1/2 -translate-y-1/2 flex h-6 w-6 items-center justify-center rounded border border-input bg-background text-muted-foreground hover:bg-accent hover:text-foreground transition-colors"
            >
              <X className="h-3.5 w-3.5" />
            </button>
          )}
        </div>
        <Button variant="outline" size="sm" onClick={fetchUsers} className="shrink-0 gap-1.5">
          <RefreshCw className={`h-4 w-4 ${loading ? "animate-spin" : ""}`} />
          刷新
        </Button>
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
                    className="flex flex-1 items-center gap-4 min-w-0"
                  >
                    {/* 头像 */}
                    <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-primary/10 text-primary font-bold">
                      {user.user_id.charAt(0).toUpperCase()}
                    </div>

                    {/* 信息 */}
                    <div className="flex-1 min-w-0">
                      <p className="font-medium truncate" title={user.user_id}>{user.user_id}</p>
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

                <span className="text-sm font-medium px-2">
                  {currentPage} / {totalPages}
                </span>

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
        description={`确定要删除用户 "${deleteUserId.length > 20 ? deleteUserId.slice(0, 20) + "..." : deleteUserId}" 吗？该用户及其所有记忆数据将被永久删除，此操作不可撤销。`}
      />
    </div>
  );
}
