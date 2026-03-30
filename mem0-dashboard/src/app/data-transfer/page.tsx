"use client";

import React, { useEffect, useState, useCallback, useRef } from "react";
import {
  Loader2,
  Download,
  Upload,
  Filter,
  X,
  User,
  Calendar,
  FileText,
  CheckCircle2,
  XCircle,
  ClipboardList,
  Trash2,
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
import { Search, ChevronDown, Check } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import { mem0Api } from "@/lib/api";
import type { Memory } from "@/lib/api";
import { exportToJSON, exportToCSV, type ExportOutput } from "@/lib/data-transfer";
import { ImportDialog, type ImportSuccessInfo } from "@/components/memories/import-dialog";
import { useToast } from "@/hooks/use-toast";

/** 操作记录类型 */
interface OperationRecord {
  id: string;
  type: "导入" | "导出";
  time: string;
  status: "成功" | "失败";
  filename: string;
  blob: Blob | null;
  detail?: string;
}

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

  // 操作记录
  const [operationRecords, setOperationRecords] = useState<OperationRecord[]>([]);

  // 用户搜索
  const [userSearchQuery, setUserSearchQuery] = useState("");
  const [userDropdownOpen, setUserDropdownOpen] = useState(false);
  const userDropdownRef = useRef<HTMLDivElement>(null);

  // 过滤后的用户列表
  const filteredUserList = userSearchQuery
    ? userList.filter((uid) =>
        uid.toLowerCase().includes(userSearchQuery.toLowerCase())
      )
    : userList;

  // 点击外部关闭下拉
  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (
        userDropdownRef.current &&
        !userDropdownRef.current.contains(e.target as Node)
      ) {
        setUserDropdownOpen(false);
      }
    };
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

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

  // 添加操作记录
  const addRecord = useCallback(
    (record: Omit<OperationRecord, "id" | "time">) => {
      const now = new Date();
      const timeStr = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}-${String(now.getDate()).padStart(2, "0")} ${String(now.getHours()).padStart(2, "0")}:${String(now.getMinutes()).padStart(2, "0")}:${String(now.getSeconds()).padStart(2, "0")}`;
      setOperationRecords((prev) => [
        {
          id: `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
          time: timeStr,
          ...record,
        },
        ...prev,
      ]);
    },
    []
  );

  // 下载操作记录中的文件
  const handleDownloadRecord = useCallback((record: OperationRecord) => {
    if (!record.blob) return;
    const url = URL.createObjectURL(record.blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = record.filename;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
  }, []);

  // 清空操作记录
  const handleClearRecords = useCallback(() => {
    setOperationRecords([]);
  }, []);

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
      const result: ExportOutput = exportToJSON(data as Memory[]);
      addRecord({
        type: "导出",
        status: "成功",
        filename: result.filename,
        blob: result.blob,
        detail: `导出 ${data.length} 条记忆为 JSON`,
      });
      toast({
        title: "导出成功",
        description: `已导出 ${data.length} 条记忆为 JSON 文件`,
        variant: "success",
      });
    } catch (err) {
      console.error("导出失败:", err);
      addRecord({
        type: "导出",
        status: "失败",
        filename: "-",
        blob: null,
        detail: err instanceof Error ? err.message : "导出失败",
      });
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
      const result: ExportOutput = exportToCSV(data as Memory[]);
      addRecord({
        type: "导出",
        status: "成功",
        filename: result.filename,
        blob: result.blob,
        detail: `导出 ${data.length} 条记忆为 CSV`,
      });
      toast({
        title: "导出成功",
        description: `已导出 ${data.length} 条记忆为 CSV 文件`,
        variant: "success",
      });
    } catch (err) {
      console.error("导出失败:", err);
      addRecord({
        type: "导出",
        status: "失败",
        filename: "-",
        blob: null,
        detail: err instanceof Error ? err.message : "导出失败",
      });
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
                  variant="outline"
                  size="sm"
                  onClick={handleResetFilter}
                  className="h-8 px-3 text-xs"
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
              <div className="relative" ref={userDropdownRef}>
                <button
                  type="button"
                  onClick={() => setUserDropdownOpen(!userDropdownOpen)}
                  className={cn(
                    "flex h-9 w-full items-center justify-between rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background",
                    "focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2",
                    "hover:bg-accent/50 transition-colors"
                  )}
                >
                  <span className={filterUserId ? "text-foreground" : "text-muted-foreground"}>
                    {filterUserId || "全部用户"}
                  </span>
                  <ChevronDown className={cn("h-4 w-4 text-muted-foreground transition-transform", userDropdownOpen && "rotate-180")} />
                </button>
                {userDropdownOpen && (
                  <div className="absolute z-50 mt-1 w-full rounded-md border bg-popover text-popover-foreground shadow-lg animate-in fade-in-0 zoom-in-95">
                    {/* 搜索框 */}
                    <div className="flex items-center border-b px-3 py-2">
                      <Search className="mr-2 h-4 w-4 shrink-0 text-muted-foreground" />
                      <input
                        type="text"
                        value={userSearchQuery}
                        onChange={(e) => setUserSearchQuery(e.target.value)}
                        placeholder="搜索用户..."
                        className="flex-1 bg-transparent text-sm outline-none placeholder:text-muted-foreground"
                        autoFocus
                      />
                    </div>
                    {/* 选项列表 */}
                    <div className="max-h-60 overflow-y-auto p-1">
                      <div
                        onClick={() => {
                          setFilterUserId("");
                          setUserDropdownOpen(false);
                          setUserSearchQuery("");
                        }}
                        className={cn(
                          "relative flex cursor-pointer select-none items-center rounded-sm px-2 py-1.5 text-sm outline-none hover:bg-accent hover:text-accent-foreground",
                          !filterUserId && "bg-accent"
                        )}
                      >
                        {!filterUserId && <Check className="mr-2 h-4 w-4" />}
                        <span className={!filterUserId ? "" : "pl-6"}>全部用户</span>
                      </div>
                      {filteredUserList.length > 0 ? (
                        filteredUserList.map((uid) => (
                          <div
                            key={uid}
                            onClick={() => {
                              setFilterUserId(uid);
                              setUserDropdownOpen(false);
                              setUserSearchQuery("");
                            }}
                            className={cn(
                              "relative flex cursor-pointer select-none items-center rounded-sm px-2 py-1.5 text-sm outline-none hover:bg-accent hover:text-accent-foreground",
                              filterUserId === uid && "bg-accent"
                            )}
                          >
                            {filterUserId === uid && <Check className="mr-2 h-4 w-4" />}
                            <span className={filterUserId === uid ? "" : "pl-6"}>{uid}</span>
                          </div>
                        ))
                      ) : (
                        <div className="px-2 py-4 text-center text-sm text-muted-foreground">
                          未找到匹配的用户
                        </div>
                      )}
                    </div>
                  </div>
                )}
              </div>
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
              <div className="flex items-center gap-2 pt-2 mt-2 border-t">
                {previewing ? (
                  <div className="flex items-center gap-2 px-3 py-2 rounded-md bg-muted/50">
                    <Loader2 className="h-4 w-4 animate-spin text-muted-foreground" />
                    <span className="text-sm text-muted-foreground">正在统计...</span>
                  </div>
                ) : filteredCount !== null ? (
                  <div className="flex items-center gap-2 px-3 py-2 rounded-md bg-primary/10 border border-primary/20">
                    <Filter className="h-4 w-4 text-primary" />
                    <span className="text-sm font-medium text-primary">
                      {filteredCount}
                    </span>
                    <span className="text-sm text-primary/80">
                      条记忆匹配当前筛选条件
                    </span>
                  </div>
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
        onSuccess={(info: ImportSuccessInfo) => {
          refreshCount();
          addRecord({
            type: "导入",
            status: info.failedCount === 0 ? "成功" : "失败",
            filename: info.filename,
            blob: null,
            detail: `成功 ${info.successCount} 条${info.failedCount > 0 ? `，失败 ${info.failedCount} 条` : ""}`,
          });
        }}
      />

      {/* 操作汇总 */}
      <Separator />
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <div>
              <CardTitle className="flex items-center gap-2">
                <ClipboardList className="h-5 w-5" />
                操作汇总
              </CardTitle>
              <CardDescription>
                记录本次会话中的导入导出操作，关闭页面后记录将清空
              </CardDescription>
            </div>
            {operationRecords.length > 0 && (
              <Button
                variant="outline"
                size="sm"
                onClick={handleClearRecords}
                className="h-8 px-3 text-xs"
              >
                <Trash2 className="mr-1 h-3 w-3" />
                清空记录
              </Button>
            )}
          </div>
        </CardHeader>
        <CardContent>
          {operationRecords.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-8 text-muted-foreground">
              <ClipboardList className="h-10 w-10 mb-2 opacity-30" />
              <p className="text-sm">暂无操作记录</p>
              <p className="text-xs mt-1">执行导入或导出操作后，记录将显示在此处</p>
            </div>
          ) : (
            <div className="rounded-md border overflow-hidden">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b bg-muted/50">
                    <th className="px-4 py-2.5 text-left font-medium text-muted-foreground">类型</th>
                    <th className="px-4 py-2.5 text-left font-medium text-muted-foreground">时间</th>
                    <th className="px-4 py-2.5 text-left font-medium text-muted-foreground">状态</th>
                    <th className="px-4 py-2.5 text-left font-medium text-muted-foreground">文件</th>
                    <th className="px-4 py-2.5 text-left font-medium text-muted-foreground">详情</th>
                  </tr>
                </thead>
                <tbody>
                  {operationRecords.map((record) => (
                    <tr key={record.id} className="border-b last:border-b-0 hover:bg-muted/30 transition-colors">
                      <td className="px-4 py-2.5">
                        <Badge
                          variant={record.type === "导出" ? "default" : "secondary"}
                          className="font-normal"
                        >
                          {record.type === "导出" ? (
                            <Upload className="mr-1 h-3 w-3" />
                          ) : (
                            <Download className="mr-1 h-3 w-3" />
                          )}
                          {record.type}
                        </Badge>
                      </td>
                      <td className="px-4 py-2.5 text-muted-foreground whitespace-nowrap">
                        {record.time}
                      </td>
                      <td className="px-4 py-2.5">
                        {record.status === "成功" ? (
                          <span className="inline-flex items-center gap-1 text-green-600">
                            <CheckCircle2 className="h-3.5 w-3.5" />
                            成功
                          </span>
                        ) : (
                          <span className="inline-flex items-center gap-1 text-red-600">
                            <XCircle className="h-3.5 w-3.5" />
                            失败
                          </span>
                        )}
                      </td>
                      <td className="px-4 py-2.5">
                        {record.blob ? (
                          <button
                            onClick={() => handleDownloadRecord(record)}
                            className="inline-flex items-center gap-1 text-primary hover:underline cursor-pointer"
                          >
                            <FileText className="h-3.5 w-3.5" />
                            <span className="max-w-[200px] truncate">{record.filename}</span>
                            <Download className="h-3 w-3 ml-0.5" />
                          </button>
                        ) : (
                          <span className="inline-flex items-center gap-1 text-muted-foreground">
                            <FileText className="h-3.5 w-3.5" />
                            <span className="max-w-[200px] truncate">{record.filename}</span>
                          </span>
                        )}
                      </td>
                      <td className="px-4 py-2.5 text-muted-foreground">
                        {record.detail || "-"}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
