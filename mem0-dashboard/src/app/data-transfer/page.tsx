"use client";

import React, { useEffect, useState, useCallback } from "react";
import {
  Loader2,
  Download,
  Upload,
  Database,
  Filter,
  X,
  User,
  Calendar,
} from "lucide-react";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import { mem0Api } from "@/lib/api";
import type { Memory } from "@/lib/api";
import { exportToJSON, exportToCSV } from "@/lib/data-transfer";
import { ImportDialog } from "@/components/memories/import-dialog";
import { useToast } from "@/hooks/use-toast";

export default function DataTransferPage() {
  const { toast } = useToast();

  // 导出状态
  const [exporting, setExporting] = useState(false);
  const [memoryCount, setMemoryCount] = useState<number | null>(null);
  const [loading, setLoading] = useState(true);

  // 筛选条件
  const [filterUserId, setFilterUserId] = useState<string>("");
  const [filterDateFrom, setFilterDateFrom] = useState<string>("");
  const [filterDateTo, setFilterDateTo] = useState<string>("");

  // 用户列表（从记忆数据中提取）
  const [userList, setUserList] = useState<string[]>([]);

  // 筛选后的预览数量
  const [filteredCount, setFilteredCount] = useState<number | null>(null);
  const [previewing, setPreviewing] = useState(false);

  // 导入弹窗
  const [importDialogOpen, setImportDialogOpen] = useState(false);

  // 是否有筛选条件
  const hasFilter = filterUserId || filterDateFrom || filterDateTo;

  // 页面加载时获取记忆数量和用户列表
  useEffect(() => {
    const fetchData = async () => {
      try {
        const memories = await mem0Api.getMemories();
        const data = Array.isArray(memories) ? memories : [];
        setMemoryCount(data.length);

        // 提取去重的用户列表
        const users = Array.from(
          new Set(
            data
              .map((m) => m.user_id)
              .filter((id): id is string => !!id)
          )
        ).sort();
        setUserList(users);
      } catch {
        setMemoryCount(null);
      } finally {
        setLoading(false);
      }
    };
    fetchData();
  }, []);

  // 刷新记忆数量
  const refreshCount = async () => {
    try {
      const memories = await mem0Api.getMemories();
      const data = Array.isArray(memories) ? memories : [];
      setMemoryCount(data.length);

      // 同时刷新用户列表
      const users = Array.from(
        new Set(
          data
            .map((m) => m.user_id)
            .filter((id): id is string => !!id)
        )
      ).sort();
      setUserList(users);
    } catch {
      // 忽略
    }
  };

  // 获取筛选后的记忆数据
  const getFilteredMemories = useCallback(async (): Promise<Memory[]> => {
    const memories = await mem0Api.getMemories({
      user_id: filterUserId || undefined,
      date_from: filterDateFrom || undefined,
      date_to: filterDateTo || undefined,
    });
    return Array.isArray(memories) ? memories : [];
  }, [filterUserId, filterDateFrom, filterDateTo]);

  // 预览筛选结果数量
  const handlePreview = useCallback(async () => {
    if (!hasFilter) {
      setFilteredCount(null);
      return;
    }
    setPreviewing(true);
    try {
      const data = await getFilteredMemories();
      setFilteredCount(data.length);
    } catch {
      setFilteredCount(null);
    } finally {
      setPreviewing(false);
    }
  }, [hasFilter, getFilteredMemories]);

  // 筛选条件变化时自动预览
  useEffect(() => {
    // 防抖：延迟 500ms 后预览
    const timer = setTimeout(() => {
      handlePreview();
    }, 500);
    return () => clearTimeout(timer);
  }, [handlePreview]);

  // 重置筛选条件
  const handleResetFilter = () => {
    setFilterUserId("");
    setFilterDateFrom("");
    setFilterDateTo("");
    setFilteredCount(null);
  };

  // 导出 JSON
  const handleExportJSON = async () => {
    setExporting(true);
    try {
      const data = hasFilter
        ? await getFilteredMemories()
        : await mem0Api.getMemories().then((m) => (Array.isArray(m) ? m : []));
      exportToJSON(data as Memory[]);
      toast({
        title: "导出成功",
        description: `已导出 ${data.length} 条记忆为 JSON 文件`,
        variant: "success",
      });
    } catch (err) {
      console.error("导出失败:", err);
      toast({
        title: "导出失败",
        description: err instanceof Error ? err.message : "请检查 API 连接状态",
        variant: "destructive",
      });
    } finally {
      setExporting(false);
    }
  };

  // 导出 CSV
  const handleExportCSV = async () => {
    setExporting(true);
    try {
      const data = hasFilter
        ? await getFilteredMemories()
        : await mem0Api.getMemories().then((m) => (Array.isArray(m) ? m : []));
      exportToCSV(data as Memory[]);
      toast({
        title: "导出成功",
        description: `已导出 ${data.length} 条记忆为 CSV 文件`,
        variant: "success",
      });
    } catch (err) {
      console.error("导出失败:", err);
      toast({
        title: "导出失败",
        description: err instanceof Error ? err.message : "请检查 API 连接状态",
        variant: "destructive",
      });
    } finally {
      setExporting(false);
    }
  };

  return (
    <div className="space-y-6">
      {/* 页面头部 */}
      <div>
        <h2 className="text-2xl font-bold tracking-tight">记忆导出</h2>
        <p className="text-muted-foreground">
          导入和导出记忆数据，方便备份和迁移
        </p>
      </div>

      {/* 数据概览 */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Database className="h-5 w-5" />
            数据概览
          </CardTitle>
          <CardDescription>
            当前系统中的记忆数据统计
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="flex items-center gap-4">
            <div className="flex h-16 w-16 items-center justify-center rounded-xl bg-primary/10">
              <Database className="h-8 w-8 text-primary" />
            </div>
            <div>
              <p className="text-3xl font-bold">
                {loading ? (
                  <Loader2 className="h-6 w-6 animate-spin" />
                ) : memoryCount !== null ? (
                  memoryCount
                ) : (
                  "--"
                )}
              </p>
              <p className="text-sm text-muted-foreground">条记忆数据</p>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* 导出数据 */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Upload className="h-5 w-5" />
            导出数据
          </CardTitle>
          <CardDescription>
            筛选并导出记忆数据为文件，支持 JSON 和 CSV 格式
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-5">
          {/* 筛选区域 */}
          <div className="rounded-lg border bg-muted/30 p-4 space-y-4">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2 text-sm font-medium">
                <Filter className="h-4 w-4" />
                导出筛选
                {hasFilter && (
                  <Badge variant="secondary" className="ml-1">
                    已启用
                  </Badge>
                )}
              </div>
              {hasFilter && (
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={handleResetFilter}
                  className="h-7 px-2 text-xs text-muted-foreground hover:text-foreground"
                >
                  <X className="mr-1 h-3 w-3" />
                  重置
                </Button>
              )}
            </div>

            {/* 按用户筛选 */}
            <div className="space-y-1.5">
              <label className="flex items-center gap-1.5 text-sm text-muted-foreground">
                <User className="h-3.5 w-3.5" />
                按用户
              </label>
              <Select
                value={filterUserId}
                onValueChange={(val) => setFilterUserId(val === "__all__" ? "" : val)}
              >
                <SelectTrigger className="w-full">
                  <SelectValue placeholder="全部用户" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="__all__">全部用户</SelectItem>
                  {userList.map((uid) => (
                    <SelectItem key={uid} value={uid}>
                      {uid}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            {/* 按时间范围筛选 */}
            <div className="space-y-1.5">
              <label className="flex items-center gap-1.5 text-sm text-muted-foreground">
                <Calendar className="h-3.5 w-3.5" />
                按时间范围
              </label>
              <div className="flex items-center gap-2">
                <Input
                  type="date"
                  value={filterDateFrom}
                  onChange={(e) => setFilterDateFrom(e.target.value)}
                  placeholder="开始日期"
                  className="flex-1"
                />
                <span className="text-sm text-muted-foreground shrink-0">至</span>
                <Input
                  type="date"
                  value={filterDateTo}
                  onChange={(e) => setFilterDateTo(e.target.value)}
                  placeholder="结束日期"
                  className="flex-1"
                />

                {/* 快捷日期范围按钮 */}
                {[
                  { label: "今天", days: 0 },
                  { label: "近7天", days: 7 },
                  { label: "近30天", days: 30 },
                ].map(({ label, days }) => {
                  const today = new Date();
                  const todayStr = today.toISOString().split("T")[0];
                  const fromDate = new Date(today);
                  fromDate.setDate(today.getDate() - days);
                  const fromStr = fromDate.toISOString().split("T")[0];
                  const isActive = filterDateFrom === fromStr && filterDateTo === todayStr;
                  return (
                    <button
                      key={label}
                      onClick={() => {
                        if (isActive) {
                          // 再次点击取消选择
                          setFilterDateFrom("");
                          setFilterDateTo("");
                        } else {
                          setFilterDateFrom(fromStr);
                          setFilterDateTo(todayStr);
                        }
                      }}
                      className={cn(
                        "inline-flex items-center justify-center rounded-md h-9 px-4 text-sm font-medium transition-all cursor-pointer border whitespace-nowrap",
                        isActive
                          ? "bg-primary text-primary-foreground border-primary shadow-sm"
                          : "bg-background text-foreground border-input hover:bg-accent hover:text-accent-foreground"
                      )}
                    >
                      {label}
                    </button>
                  );
                })}
              </div>
            </div>

            {/* 筛选结果预览 */}
            {hasFilter && (
              <div className="flex items-center gap-2 pt-1 text-sm">
                {previewing ? (
                  <>
                    <Loader2 className="h-3.5 w-3.5 animate-spin text-muted-foreground" />
                    <span className="text-muted-foreground">正在统计...</span>
                  </>
                ) : filteredCount !== null ? (
                  <>
                    <Badge variant="outline" className="font-mono">
                      {filteredCount}
                    </Badge>
                    <span className="text-muted-foreground">
                      条记忆匹配当前筛选条件
                    </span>
                  </>
                ) : null}
              </div>
            )}
          </div>

          {/* 导出按钮 */}
          <div className="flex gap-3">
            <Button
              variant="outline"
              onClick={handleExportJSON}
              disabled={exporting}
            >
              {exporting ? (
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              ) : (
                <Upload className="mr-2 h-4 w-4" />
              )}
              导出 JSON
            </Button>
            <Button
              variant="outline"
              onClick={handleExportCSV}
              disabled={exporting}
            >
              {exporting ? (
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              ) : (
                <Upload className="mr-2 h-4 w-4" />
              )}
              导出 CSV
            </Button>
          </div>
          <p className="text-xs text-muted-foreground">
            💡 {hasFilter ? "将按筛选条件导出匹配的记忆数据。" : "未设置筛选条件，将导出全部记忆数据。"}JSON 格式包含完整的记忆数据（含分类、状态等），适合备份和迁移；CSV 格式适合在 Excel 中查看和分析。
          </p>
        </CardContent>
      </Card>

      <Separator />

      {/* 导入数据 */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Download className="h-5 w-5" />
            导入数据
          </CardTitle>
          <CardDescription>
            从 JSON 文件批量导入记忆数据到系统中
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <Button
            variant="outline"
            onClick={() => setImportDialogOpen(true)}
          >
            <Download className="mr-2 h-4 w-4" />
            导入 JSON
          </Button>
          <p className="text-xs text-muted-foreground">
            💡 支持导入之前导出的 JSON 文件，会保留分类和状态信息。支持拖拽上传。
          </p>
        </CardContent>
      </Card>

      {/* 导入弹窗 */}
      <ImportDialog
        open={importDialogOpen}
        onOpenChange={setImportDialogOpen}
        onSuccess={() => {
          refreshCount();
        }}
      />
    </div>
  );
}
