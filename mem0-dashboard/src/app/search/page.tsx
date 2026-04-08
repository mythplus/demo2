"use client";

import React, { useState, useEffect, useRef } from "react";
import Link from "next/link";
import {
  Search,
  Loader2,
  Clock,
  X,
  Sparkles,
  ArrowRight,
  ExternalLink,
  ChevronDown,
  Check,
} from "lucide-react";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { mem0Api } from "@/lib/api";
import type { SearchResult, Memory } from "@/lib/api";
import { CategoryBadges } from "@/components/memories/category-badge";
import { StateBadge } from "@/components/memories/state-badge";
import { MemoryDetailPanel } from "@/components/memories/memory-detail-panel";
import { UserCombobox } from "@/components/shared/user-combobox";

// 搜索历史记录类型
interface SearchHistoryItem {
  query: string;
  userId?: string;
  timestamp: number;
  resultCount: number;
}

const SEARCH_HISTORY_KEY = "mem0-search-history";
const MAX_HISTORY = 10;

export default function SearchPage() {
  // 搜索状态
  const [query, setQuery] = useState("");
  const [userId, setUserId] = useState<string>("");
  const [limit, setLimit] = useState("10");
  const [results, setResults] = useState<SearchResult[]>([]);
  const [loading, setLoading] = useState(false);
  const [searched, setSearched] = useState(false);
  const [error, setError] = useState("");

  // 搜索历史
  const [searchHistory, setSearchHistory] = useState<SearchHistoryItem[]>([]);

  // 详情面板状态
  const [detailPanelOpen, setDetailPanelOpen] = useState(false);
  const [selectedMemory, setSelectedMemory] = useState<Memory | null>(null);

  // 用户列表（从记忆数据获取）
  const [users, setUsers] = useState<string[]>([]);

  // 加载搜索历史和用户列表
  useEffect(() => {
    // 加载搜索历史
    try {
      const saved = localStorage.getItem(SEARCH_HISTORY_KEY);
      if (saved) {
        setSearchHistory(JSON.parse(saved));
      }
    } catch {}

    // 加载用户列表
    loadUsers();
  }, []);

  const loadUsers = async () => {
    try {
      const memories = await mem0Api.getMemories();
      // 从所有记忆（含已删除）中提取用户，确保用户不会因记忆全部删除而消失
      const uniqueUsers = Array.from(
        new Set(
          (Array.isArray(memories) ? memories : [])
            .map((m: Memory) => m.user_id)
            .filter(Boolean)
        )
      ) as string[];
      setUsers(uniqueUsers);
    } catch {}
  };

  // 保存搜索历史
  const saveHistory = (item: SearchHistoryItem) => {
    const updated = [
      item,
      ...searchHistory.filter((h) => h.query !== item.query),
    ].slice(0, MAX_HISTORY);
    setSearchHistory(updated);
    localStorage.setItem(SEARCH_HISTORY_KEY, JSON.stringify(updated));
  };

  // 清除搜索历史
  const clearHistory = () => {
    setSearchHistory([]);
    localStorage.removeItem(SEARCH_HISTORY_KEY);
  };

  // 执行搜索
  const handleSearch = async (searchQuery?: string) => {
    const q = searchQuery || query;
    if (!q.trim()) return;

    setLoading(true);
    setError("");
    setSearched(true);

    try {
      const response = await mem0Api.searchMemories({
        query: q.trim(),
        user_id: userId || undefined,
        limit: parseInt(limit),
      });

      const searchResults = (response.results || []).filter(
        (r) => r.state !== "deleted"
      );
      setResults(searchResults);

      // 保存搜索历史
      saveHistory({
        query: q.trim(),
        userId: userId === "all" ? undefined : userId,
        timestamp: Date.now(),
        resultCount: searchResults.length,
      });
    } catch (err) {
      setError(err instanceof Error ? err.message : "搜索失败");
      setResults([]);
    } finally {
      setLoading(false);
    }
  };

  // 从历史记录搜索
  const handleHistorySearch = (item: SearchHistoryItem) => {
    setQuery(item.query);
    if (item.userId) setUserId(item.userId);
    handleSearch(item.query);
  };

  // 点击查看记忆详情（将 SearchResult 转为 Memory 类型传给详情面板）
  const handleViewDetail = (result: SearchResult) => {
    const memoryData: Memory = {
      id: result.id,
      memory: result.memory,
      user_id: result.user_id,
      agent_id: result.agent_id,
      metadata: result.metadata,
      categories: result.categories,
      state: result.state,
      created_at: result.created_at,
      updated_at: result.updated_at,
    };
    setSelectedMemory(memoryData);
    setDetailPanelOpen(true);
  };

  // 相似度分数颜色
  const getScoreColor = (score: number) => {
    if (score >= 0.8) return "text-green-600 dark:text-green-400";
    if (score >= 0.6) return "text-yellow-600 dark:text-yellow-400";
    return "text-orange-600 dark:text-orange-400";
  };

  const getScoreBg = (score: number) => {
    if (score >= 0.8) return "bg-green-100 dark:bg-green-900/30";
    if (score >= 0.6) return "bg-yellow-100 dark:bg-yellow-900/30";
    return "bg-orange-100 dark:bg-orange-900/30";
  };

  return (
    <div className="space-y-6">
      {/* 页面头部 */}
      <div>
        <h2 className="text-2xl font-bold tracking-tight">语义检索</h2>
        <p className="text-muted-foreground">
          使用自然语言检索已存储的记忆，基于语义相似度智能匹配
        </p>
      </div>

      {/* 搜索栏 */}
      <Card>
        <CardContent className="pt-6">
          <form
            onSubmit={(e) => {
              e.preventDefault();
              handleSearch();
            }}
            className="space-y-3"
          >
            <div className="flex gap-3">
              <div className="relative flex-1">
                <Sparkles className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
                <Input
                  placeholder="输入搜索内容，例如：用户喜欢什么颜色？"
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                  className="pl-9"
                  disabled={loading}
                />
              </div>
              <Button type="submit" disabled={loading || !query.trim()}>
                {loading ? (
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                ) : (
                  <Search className="mr-2 h-4 w-4" />
                )}
                搜索
              </Button>
            </div>

            {/* 高级选项 */}
            <div className="flex gap-3">
              <UserCombobox
                value={userId}
                users={users}
                onChange={setUserId}
              />

              {/* 查找条数选择 */}
              <Select value={limit} onValueChange={setLimit}>
                <SelectTrigger className="w-[130px]">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="5">查找 5 条</SelectItem>
                  <SelectItem value="10">查找 10 条</SelectItem>
                  <SelectItem value="20">查找 20 条</SelectItem>
                </SelectContent>
              </Select>

              {/* 清除按钮 - 重置搜索回到初始状态 */}
              {searched && (
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  className="shrink-0"
                  title="清除搜索"
                  onClick={() => {
                    setQuery("");
                    setUserId("");
                    setLimit("10");
                    setResults([]);
                    setSearched(false);
                    setError("");
                  }}
                >
                  <X className="mr-1 h-4 w-4" />
                  清除
                </Button>
              )}
            </div>
          </form>
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

      {/* 搜索结果 */}
      {searched && !loading && (
        <Card>
          <CardHeader>
            <div className="flex items-center justify-between">
              <div>
                <CardTitle className="text-base">
                  搜索结果
                  <Badge variant="secondary" className="ml-2">
                    {results.length} 条
                  </Badge>
                </CardTitle>
                <CardDescription className="mt-1">
                  按语义相似度从高到低排序
                </CardDescription>
              </div>
            </div>
          </CardHeader>
          <CardContent>
            {results.length > 0 ? (
              <div className="max-h-[calc(100vh-300px)] overflow-y-auto overflow-x-auto space-y-3 pr-1">
                {results.map((result, index) => (
                  <div
                    key={result.id}
                    className="rounded-lg border p-4 transition-colors hover:bg-accent/30 cursor-pointer"
                    onClick={() => handleViewDetail(result)}
                  >
                    <div className="flex items-start justify-between gap-4 min-w-[500px]">
                      {/* 序号 + 内容 */}
                      <div className="flex-1">
                        <div className="flex items-center gap-2 mb-2">
                          <span className="flex h-6 w-6 items-center justify-center rounded-full bg-primary/10 text-xs font-bold text-primary">
                            {index + 1}
                          </span>
                          {result.user_id && (
                            <Badge variant="secondary" className="text-xs">
                              {result.user_id}
                            </Badge>
                          )}
                          <StateBadge state={result.state} />
                          {result.created_at && (
                            <span className="text-xs text-muted-foreground">
                              {new Date(result.created_at).toLocaleString(
                                "zh-CN"
                              )}
                            </span>
                          )}
                        </div>
                        <p className="text-sm leading-relaxed break-all whitespace-pre-wrap">
                          {result.memory}
                        </p>
                        {/* 分类标签 + 详情页链接 */}
                        <div className="mt-2 flex flex-wrap items-center gap-2">
                          <CategoryBadges categories={result.categories} max={3} />
                          <Link
                            href={`/memory/${result.id}`}
                            className="text-xs text-primary hover:underline inline-flex items-center gap-0.5"
                            onClick={(e) => e.stopPropagation()}
                          >
                            详情页
                            <ExternalLink className="h-3 w-3" />
                          </Link>
                        </div>
                      </div>

                      {/* 相似度分数 */}
                      <div
                        className={`shrink-0 rounded-lg px-3 py-1.5 text-center ${getScoreBg(
                          result.score
                        )}`}
                      >
                        <p
                          className={`text-lg font-bold ${getScoreColor(
                            result.score
                          )}`}
                        >
                          {(result.score * 100).toFixed(1)}%
                        </p>
                        <p className="text-xs text-muted-foreground">
                          相似度
                        </p>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <div className="flex flex-col items-center justify-center py-12 text-center">
                <Search className="mb-4 h-16 w-16 text-muted-foreground/30" />
                <p className="text-lg font-medium text-muted-foreground">
                  未找到相关记忆
                </p>
                <p className="mt-1 text-sm text-muted-foreground">
                  尝试使用不同的关键词或更宽泛的描述
                </p>
              </div>
            )}

          </CardContent>
        </Card>
      )}

      {/* 搜索历史 */}
      {!searched && searchHistory.length > 0 && (
        <Card>
          <CardHeader>
            <div className="flex items-center justify-between">
              <CardTitle>
                搜索历史
              </CardTitle>
              <Button
                variant="outline"
                size="sm"
                onClick={clearHistory}
              >
                清除记录
              </Button>
            </div>
          </CardHeader>
          <CardContent>
            <div className="space-y-2">
              {searchHistory.map((item, index) => (
                <div
                  key={index}
                  className="flex items-center justify-between rounded-lg border p-3 cursor-pointer transition-colors hover:bg-accent/50"
                  onClick={() => handleHistorySearch(item)}
                >
                  <div className="flex items-center gap-3">
                    <Clock className="h-4 w-4 text-muted-foreground" />
                    <div>
                      <p className="text-sm font-medium">{item.query}</p>
                      <div className="flex items-center gap-2 mt-0.5">
                        {item.userId && (
                          <span className="text-xs text-muted-foreground">
                            用户: {item.userId}
                          </span>
                        )}
                        <span className="text-xs text-muted-foreground">
                          {item.resultCount} 条结果
                        </span>
                        <span className="text-xs text-muted-foreground">
                          {new Date(item.timestamp).toLocaleString("zh-CN")}
                        </span>
                      </div>
                    </div>
                  </div>
                  <ArrowRight className="h-4 w-4 text-muted-foreground" />
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      {/* 初始提示 */}
      {!searched && searchHistory.length === 0 && (
        <Card>
          <CardContent className="py-12">
            <div className="flex flex-col items-center justify-center text-center">
              <Sparkles className="mb-4 h-16 w-16 text-muted-foreground/30" />
              <p className="text-lg font-medium text-muted-foreground">
开始语义检索
              </p>
              <p className="mt-2 max-w-md text-sm text-muted-foreground">
                输入自然语言描述，Mem0 会基于语义相似度智能匹配最相关的记忆。
                例如：「用户的饮食偏好」「最近讨论的技术话题」
              </p>
            </div>
          </CardContent>
        </Card>
      )}

      {/* 记忆详情侧边面板 */}
      <MemoryDetailPanel
        memory={selectedMemory}
        open={detailPanelOpen}
        onClose={() => setDetailPanelOpen(false)}
      />
    </div>
  );
}



