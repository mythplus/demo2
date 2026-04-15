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
  Eye,
  AlertTriangle,
} from "lucide-react";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";


import { Input } from "@/components/ui/input";
import { Search, ChevronDown, Check } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import { UserCombobox } from "@/components/shared/user-combobox";
import { mem0Api } from "@/lib/api";
import type { Memory } from "@/lib/api";
import { exportToJSON, exportToCSV, type ExportOutput } from "@/lib/data-transfer";
import { ImportDialog, type ImportSuccessInfo } from "@/components/memories/import-dialog";
import { useToast } from "@/hooks/use-toast";
import { useOperationRecords, type OperationRecord } from "@/hooks/use-operation-records";
import { hasRunningImportTask } from "@/lib/import-task-registry";
import { Progress } from "@/components/ui/progress";

export default function DataTransferPage() {
  const { toast } = useToast();

  // 导出状态
  const [exporting, setExporting] = useState(false);
  const [exportProgress, setExportProgress] = useState(0);
  const [exportStage, setExportStage] = useState("");
  const [memoryCount, setMemoryCount] = useState<number | null>(null);
  const [loading, setLoading] = useState(true);

  // 筛选条件
  const [filterUserId, setFilterUserId] = useState<string>("");
  const [userSelected, setUserSelected] = useState(false);
  const [filterDateFrom, setFilterDateFrom] = useState<string>("");
  const [filterDateTo, setFilterDateTo] = useState<string>("");

  // 用户列表（从记忆数据中提取）
  const [userList, setUserList] = useState<string[]>([]);

  // 筛选后的预览数量
  const [filteredCount, setFilteredCount] = useState<number | null>(null);
  const [previewing, setPreviewing] = useState(false);

  // 导入弹窗
  const [importDialogOpen, setImportDialogOpen] = useState(false);

  // 是否正在导入中（用于控制按钮状态）
  const [isImporting, setIsImporting] = useState(false);

  // 是否有待查看的导入结果
  const [hasImportResult, setHasImportResult] = useState(false);

  // 操作记录（IndexedDB 持久化）
  const {
    records: operationRecords,
    loading: recordsLoading,
    addRecord,
    updateRecord,
    clearRecords: handleClearRecords,
    downloadRecord: handleDownloadRecord,
    hasImportingRecord,
  } = useOperationRecords();

  // 页面加载时，如果 IndexedDB 中有"导入中"记录，恢复 isImporting 状态
  // 注意：仅在当前没有真正在进行的导入时才恢复
  useEffect(() => {
    if (hasImportingRecord && !isImporting) {
      setIsImporting(true);
    }
  }, [hasImportingRecord, isImporting]);

  // 判断是否为真正的中断（IndexedDB 有"导入中"记录，但 JS 运行时中没有对应任务）
  // SPA 路由切换：hasRunningImportTask() = true，说明导入仍在后台执行
  // 页面刷新：hasRunningImportTask() = false，说明导入真的中断了
  const isReallyInterrupted = hasImportingRecord && !hasRunningImportTask();

  // 判断是否有后台导入正在执行（SPA 切换页面后仍在后台运行）
  const isBackgroundRunning = hasImportingRecord && hasRunningImportTask();

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
  const hasFilter = userSelected || filterDateFrom || filterDateTo;

  // 页面加载时获取记忆数量和用户列表
  useEffect(() => {
    const fetchData = async () => {
      try {
        const [stats, users] = await Promise.all([
          mem0Api.getStats().catch(() => null),
          mem0Api.getMemoryUsers().catch(() => []),
        ]);
        setMemoryCount(stats?.total_memories ?? null);
        setUserList(
          Array.isArray(users)
            ? users.map((u) => u.user_id).filter(Boolean).sort()
            : []
        );
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
      const [stats, users] = await Promise.all([
        mem0Api.getStats().catch(() => null),
        mem0Api.getMemoryUsers().catch(() => []),
      ]);
      setMemoryCount(stats?.total_memories ?? null);
      setUserList(
        Array.isArray(users)
          ? users.map((u) => u.user_id).filter(Boolean).sort()
          : []
      );
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
      const preview = await mem0Api.getMemories({
        user_id: filterUserId || undefined,
        date_from: filterDateFrom || undefined,
        date_to: filterDateTo || undefined,
        page: 1,
        page_size: 1,
      });
      const totalFromServer = Array.isArray(preview) ? preview.length : preview.total;
      setFilteredCount(totalFromServer);
    } catch {
      setFilteredCount(null);
    } finally {
      setPreviewing(false);
    }
  }, [hasFilter, filterUserId, filterDateFrom, filterDateTo]);

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
    setUserSelected(false);
    setFilterDateFrom("");
    setFilterDateTo("");
    setFilteredCount(null);
  };

  // 通用导出逻辑（带进度反馈）
  const handleExport = async (format: "json" | "csv") => {
    setExporting(true);
    setExportProgress(0);
    setExportStage("正在获取数据...");
    try {
      // 阶段 1：获取数据（0% → 60%）
      setExportProgress(10);
      const data = hasFilter
        ? await getFilteredMemories()
        : await mem0Api.getMemories({}).then((m) => (Array.isArray(m) ? m : []));
      setExportProgress(60);

      // 阶段 2：转换格式（60% → 85%）
      setExportStage(`正在转换为 ${format.toUpperCase()} 格式...`);
      // 使用 setTimeout 让 UI 有机会更新进度
      await new Promise((r) => setTimeout(r, 100));
      const result: ExportOutput = format === "json"
        ? exportToJSON(data as Memory[])
        : exportToCSV(data as Memory[]);
      setExportProgress(85);

      // 阶段 3：下载完成（85% → 100%）
      setExportStage("下载完成！");
      setExportProgress(100);

      const exportUserLabel = filterUserId ? `「${filterUserId}」` : "「全部用户」";
      const exportFilterLabel = exportUserLabel;
      addRecord({
        type: "导出",
        status: "成功",
        filename: result.filename,
        blob: result.blob,
        detail: `导出${exportFilterLabel}的 ${data.length} 条记忆为 ${format.toUpperCase()}`,
      });
      toast({
        title: "导出成功",
        description: `已导出${exportFilterLabel}的 ${data.length} 条记忆为 ${format.toUpperCase()} 文件`,
        variant: "success",
      });

      // 延迟清除进度条，让用户看到 100% 完成状态
      setTimeout(() => {
        setExporting(false);
        setExportProgress(0);
        setExportStage("");
      }, 1500);
      return;
    } catch (err) {
      console.error("导出失败:", err);
      setExportStage("导出失败");
      setExportProgress(0);
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
    }
    setExporting(false);
    setExportProgress(0);
    setExportStage("");
  };

  // 导出 JSON
  const handleExportJSON = () => handleExport("json");

  // 导出 CSV
  const handleExportCSV = () => handleExport("csv");

  return (
    <div className="space-y-4">
      {/* 页面头部 */}
      <div>
        <h2 className="text-xl font-bold tracking-tight">数据导出</h2>
        <p className="text-sm text-muted-foreground">
          导入和导出记忆数据，方便备份和迁移
        </p>
      </div>

      {/* 导出数据 */}
      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="flex items-center gap-2">
            <Upload className="h-5 w-5" />
            导出数据
          </CardTitle>
          <CardDescription>
            筛选并导出记忆数据为文件，支持 JSON 和 CSV 格式
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-3 pt-0">
          {/* 筛选区域 */}
          <div className="rounded-lg border bg-muted/30 p-3 space-y-3">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2 text-sm font-medium">
                <Filter className="h-4 w-4" />
                导出筛选
                {hasFilter && (
                  <Badge variant="secondary" className="ml-1 bg-green-100 text-green-700 border-green-200 dark:bg-green-900/30 dark:text-green-400 dark:border-green-800">
                    已启用
                  </Badge>
                )}
              </div>
              {hasFilter && (
                <Button
                  variant="outline"
                  size="sm"
                  onClick={handleResetFilter}
                  className="h-9 px-4 text-sm"
                >
                  <X className="mr-1 h-4 w-4" />
                  重置
                </Button>
              )}
            </div>

            {/* 按用户 + 按状态 */}
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              {/* 按用户筛选 */}
              <div className="space-y-1.5">
                <label className="flex items-center gap-1.5 text-sm text-muted-foreground">
                  <User className="h-3.5 w-3.5" />
                  按用户
                </label>
                <UserCombobox
                  value={filterUserId}
                  users={userList}
                  onChange={(uid) => {
                    setFilterUserId(uid);
                    setUserSelected(true);
                  }}
                  placeholder="请选择用户"
                  className="w-full"
                  showAll
                  selected={userSelected}
                />
              </div>
            </div>

            {/* 按时间范围筛选 */}
            <div className="space-y-1.5">
              <label className="flex items-center gap-1.5 text-sm text-muted-foreground">
                <Calendar className="h-3.5 w-3.5" />
                按时间范围
              </label>
              <div className="flex flex-wrap items-center gap-2">
                <div className="flex items-center gap-2 flex-1 min-w-[280px]">
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
                </div>

                {/* 快捷日期范围按钮 */}
                <div className="flex items-center gap-2">
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
                      共 {filteredCount} 条数据
                    </span>
                  </div>
                ) : null}
              </div>
            )}
          </div>

          {/* 导出进度条 */}
          {exporting && (
            <div className="space-y-2 rounded-lg border bg-muted/30 p-3">
              <div className="flex items-center justify-between text-sm">
                <span className="flex items-center gap-2 text-muted-foreground">
                  <Loader2 className="h-4 w-4 animate-spin" />
                  {exportStage}
                </span>
                <span className="font-medium text-primary">{exportProgress}%</span>
              </div>
              <Progress value={exportProgress} className="h-2" />
            </div>
          )}

          {/* 导出按钮 */}
          <div className="flex gap-2">
            <Button
              variant="outline"
              onClick={handleExportJSON}
              disabled={exporting || !hasFilter}
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
              disabled={exporting || !hasFilter}
            >
              {exporting ? (
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              ) : (
                <Upload className="mr-2 h-4 w-4" />
              )}
              导出 CSV
            </Button>
          </div>
          <p className="text-xs text-muted-foreground -mt-1">
            💡 {!hasFilter ? "请先选择用户或状态再导出。" : "将按筛选条件导出匹配的记忆数据。"}JSON 格式包含完整的记忆数据（含分类、状态等），适合备份和迁移；CSV 格式适合在 Excel 中查看和分析。
          </p>
        </CardContent>
      </Card>

      {/* 导入数据 */}
      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="flex items-center gap-2">
            <Download className="h-5 w-5" />
            导入数据
          </CardTitle>
          <CardDescription>
            从 JSON 文件批量导入记忆数据到系统中
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-3 pt-0">
          <div className="flex gap-2 items-center">
            <Button
              variant="outline"
              onClick={() => setImportDialogOpen(true)}
              disabled={isImporting}
            >
              <Download className="mr-2 h-4 w-4" />
              导入 JSON
            </Button>
            {isImporting && (
              <Button
                variant="outline"
                onClick={() => setImportDialogOpen(true)}
                className="border-blue-200 text-blue-600 hover:bg-blue-50 dark:border-blue-800 dark:text-blue-400 dark:hover:bg-blue-900/30"
              >
                <Eye className="mr-2 h-4 w-4" />
                查看导入进度
              </Button>
            )}
            {!isImporting && hasImportResult && (
              <Button
                variant="outline"
                onClick={() => setImportDialogOpen(true)}
                className="border-green-200 text-green-600 hover:bg-green-50 dark:border-green-800 dark:text-green-400 dark:hover:bg-green-900/30"
              >
                <CheckCircle2 className="mr-2 h-4 w-4" />
                查看导入结果
              </Button>
            )}
          </div>
          <p className="text-xs text-muted-foreground -mt-1">
            💡 支持导入之前导出的 JSON 文件，会保留分类和状态信息。支持拖拽上传。
          </p>
        </CardContent>
      </Card>

      {/* 导入弹窗 */}
      <ImportDialog
        open={importDialogOpen}
        onOpenChange={setImportDialogOpen}
        onImportingChange={setIsImporting}
        onPendingResultChange={setHasImportResult}
        isRecovered={isReallyInterrupted}
        isBackgroundRunning={isBackgroundRunning}
        onRecoveredConfirm={() => {
          // 用户确认中断后：将 IndexedDB 中"导入中"的记录标记为"失败"
          operationRecords
            .filter((r) => r.status === "导入中")
            .forEach((r) => {
              updateRecord(r.id, {
                status: "失败",
detail: `页面刷新，导入中断`,
              });
            });
          setIsImporting(false);
        }}
        onSuccess={(info: ImportSuccessInfo) => {
          refreshCount();
          // 根据取消/成功/失败判断状态
          const status = info.wasCancelled
            ? (info.successCount > 0 ? "部分成功" : "已取消")
            : info.failedCount === 0
              ? "成功"
              : info.successCount === 0
                ? "失败"
                : "部分成功";
const importUserLabel = info.defaultUserId ? `「${info.defaultUserId}」` : "原ID";
          const skippedCount = info.totalCount - info.successCount - info.failedCount;
          const detail = info.wasCancelled
? `取消导入${info.successCount > 0 ? `，成功导入${importUserLabel}的 ${info.successCount} 条记忆` : ""}${skippedCount > 0 ? `，跳过 ${skippedCount} 条记忆` : ""}`
            : `导入${importUserLabel}的 ${info.successCount} 条记忆${info.failedCount > 0 ? `，失败 ${info.failedCount} 条` : ""}`;
          addRecord({
            type: "导入",
            status,
            filename: info.filename,
            blob: info.blob,
            detail,
          });
          toast({
            title: info.wasCancelled
              ? "导入已取消"
              : info.successCount === 0
                ? "导入失败"
                : info.failedCount === 0
                  ? "导入成功"
                  : "导入部分成功",
            description: info.wasCancelled
              ? `已取消导入${info.successCount > 0 ? `，成功导入 ${info.successCount} 条` : ""}${skippedCount > 0 ? `，跳过 ${skippedCount} 条` : ""}`
              : `成功导入 ${info.successCount} 条记忆${info.failedCount > 0 ? `，${info.failedCount} 条失败` : ""}`,
            variant: info.wasCancelled
              ? "default"
              : info.successCount === 0
                ? "destructive"
                : "success",
          });
        }}
        onBackgroundImport={(info) => {
          // 后台进行：先添加一条"导入中"记录
const bgUserLabel = info.defaultUserId ? `「${info.defaultUserId}」` : "原ID";
          const recordId = addRecord({
            type: "导入",
            status: "导入中",
            filename: info.filename,
            blob: info.blob,
            detail: `正在后台导入${bgUserLabel}的 ${info.totalCount} 条记忆...`,
          });
          // 返回 recordId 供后续更新
          return recordId;
        }}
        onBackgroundComplete={(recordId, info) => {
          // 后台导入完成：更新记录状态
          refreshCount();
          const status = info.failedCount === 0 ? "成功" : info.successCount === 0 ? "失败" : "部分成功";
          // 从已有记录中提取用户标签（保持与后台开始时一致）
          const existingRecord = operationRecords.find((r) => r.id === recordId);
const bgCompleteUserLabel = existingRecord?.detail?.match(/「[^」]+」/)?.[0] || "原ID";
          updateRecord(recordId, {
            status,
            detail: `导入${bgCompleteUserLabel}的 ${info.successCount} 条记忆${info.failedCount > 0 ? `，失败 ${info.failedCount} 条` : ""}`,
          });
          toast({
            title: info.successCount === 0 ? "导入失败" : info.failedCount === 0 ? "导入成功" : "导入部分成功",
            description: `后台导入完成：导入 ${info.successCount} 条记忆${info.failedCount > 0 ? `，${info.failedCount} 条失败` : ""}`,
            variant: info.successCount === 0 ? "destructive" : "success",
          });
        }}
      />

{/* 记录 */}
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <div className="space-y-1.5">
              <CardTitle className="flex items-center gap-2">
                <ClipboardList className="h-5 w-5" />
记录
              </CardTitle>
              <CardDescription>
                记录导入导出操作历史，数据持久化存储在浏览器中，只保留最近 20 条记录
              </CardDescription>
            </div>
            {operationRecords.length > 0 && (
              <div className="flex items-center gap-2">
                <Button
                  variant="outline"
                  size="sm"
                  onClick={handleClearRecords}
                  className="h-8 px-3 text-xs"
                >
                  <Trash2 className="mr-1 h-3 w-3" />
                  清空记录
                </Button>
                <span className="text-sm text-muted-foreground whitespace-nowrap">
                  共 {operationRecords.length} 条记录
                </span>
              </div>
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
            <div className="rounded-md border overflow-auto max-h-[400px]">
              <Table className="min-w-[600px]">
                <TableHeader>
                  <TableRow>
                    <TableHead className="w-[80px]">类型</TableHead>
                    <TableHead className="w-[180px]">时间</TableHead>
                    <TableHead>文件</TableHead>
                    <TableHead>详情</TableHead>
                    <TableHead className="w-[80px]">状态</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {operationRecords.map((record) => (
                    <TableRow key={record.id}>
                      <TableCell>
                        <Badge
                          variant="outline"
                          className={cn(
                            "font-normal whitespace-nowrap",
                            record.type === "导出"
                              ? "bg-blue-50 text-blue-600 border-blue-200 dark:bg-blue-900/30 dark:text-blue-400 dark:border-blue-800"
                              : "bg-red-50 text-red-600 border-red-200 dark:bg-red-900/30 dark:text-red-400 dark:border-red-800"
                          )}
                        >
                          {record.type === "导出" ? (
                            <Upload className="mr-1 h-3 w-3" />
                          ) : (
                            <Download className="mr-1 h-3 w-3" />
                          )}
                          {record.type}
                        </Badge>
                      </TableCell>
                      <TableCell className="text-muted-foreground whitespace-nowrap">
                        {record.time}
                      </TableCell>
                      <TableCell>
                        {record.blob ? (
                          <button
                            onClick={() => handleDownloadRecord(record)}
                            className="inline-flex items-center gap-1 text-primary hover:underline cursor-pointer"
                          >
                            <FileText className="h-3.5 w-3.5" />
                            <span className="truncate">{record.filename}</span>
                            <Download className="h-3 w-3 ml-0.5 shrink-0" />
                          </button>
                        ) : (
                          <span className="inline-flex items-center gap-1 text-muted-foreground">
                            <FileText className="h-3.5 w-3.5" />
                            <span className="truncate">{record.filename}</span>
                          </span>
                        )}
                      </TableCell>
                      <TableCell className="text-muted-foreground whitespace-nowrap">
                        {record.detail || "-"}
                      </TableCell>
                      <TableCell className="whitespace-nowrap">
                        {record.status === "成功" ? (
                          <span className="inline-flex items-center gap-1 text-green-600 dark:text-green-400">
                            <CheckCircle2 className="h-3.5 w-3.5" />
                            成功
                          </span>
                        ) : record.status === "部分成功" ? (
                          <span className="inline-flex items-center gap-1 text-yellow-600 dark:text-yellow-400">
                            <AlertTriangle className="h-3.5 w-3.5" />
                            部分成功
                          </span>
                        ) : record.status === "导入中" ? (
                          <span className="inline-flex items-center gap-1 text-blue-600 dark:text-blue-400">
                            <Loader2 className="h-3.5 w-3.5 animate-spin" />
                            导入中
                          </span>
                        ) : record.status === "已取消" ? (
                          <span className="inline-flex items-center gap-1 text-muted-foreground">
                            <XCircle className="h-3.5 w-3.5" />
                            已取消
                          </span>
                        ) : (
                          <span className="inline-flex items-center gap-1 text-red-600 dark:text-red-400">
                            <XCircle className="h-3.5 w-3.5" />
                            失败
                          </span>
                        )}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
