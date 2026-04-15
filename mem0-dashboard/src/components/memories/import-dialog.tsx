"use client";

import React, { useState, useRef, useCallback } from "react";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import {
  Upload,
  FileJson,
  Loader2,
  CheckCircle,
  AlertTriangle,
  XCircle,
  User,
  Ban,
  SkipForward,
} from "lucide-react";
import { Progress } from "@/components/ui/progress";
import {
  parseImportJSON,
  validateImportItems,
  type ImportItem,
  type ImportResult,
} from "@/lib/data-transfer";
import { mem0Api } from "@/lib/api";
import type { Category } from "@/lib/api/types";
import { registerImportTask, unregisterImportTask } from "@/lib/import-task-registry";

/** 导入成功回调信息 */
export interface ImportSuccessInfo {
  filename: string;
  successCount: number;
  failedCount: number;
  /** 导入文件中的总记忆条数 */
  totalCount: number;
  blob: Blob | null;
  /** 是否为用户主动取消导入 */
  wasCancelled?: boolean;
  /** 导入时填写的默认用户ID（为空表示使用原有ID） */
  defaultUserId?: string;
}

/** 后台导入信息 */
export interface BackgroundImportInfo {
  filename: string;
  totalCount: number;
  blob: Blob | null;
  /** 导入时填写的默认用户ID（为空表示使用原有ID） */
  defaultUserId?: string;
}

/** 后台导入完成信息 */
export interface BackgroundCompleteInfo {
  successCount: number;
  failedCount: number;
}

interface ImportDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onSuccess: (info: ImportSuccessInfo) => void;
  /** 后台进行回调：返回 recordId */
  onBackgroundImport?: (info: BackgroundImportInfo) => string;
  /** 后台导入完成回调 */
  onBackgroundComplete?: (recordId: string, info: BackgroundCompleteInfo) => void;
  /** 导入状态变化回调（true=正在导入中，false=导入结束或未开始） */
  onImportingChange?: (importing: boolean) => void;
  /** 后台导入完成且弹窗关闭时通知父组件有待查看的结果 */
  onPendingResultChange?: (hasPendingResult: boolean) => void;
  /** 是否为恢复模式（IndexedDB 中有"导入中"记录且 JS 运行时中没有对应任务） */
  isRecovered?: boolean;
  /** 恢复模式确认后的回调 */
  onRecoveredConfirm?: () => void;
  /** 是否有后台导入正在执行（SPA 切换页面后仍在后台运行） */
  isBackgroundRunning?: boolean;
}

type ImportStep = "upload" | "preview" | "importing" | "done" | "interrupted";

// 导入限制常量
const MAX_FILE_SIZE = 10 * 1024 * 1024; // 10MB
const MAX_IMPORT_ITEMS = 1000;
const PROGRESS_SEGMENTS = 10; // 进度条固定切分为 10 份（每份 10%）
const MAX_BATCH_SIZE = 100;   // 后端单次最多接受 100 条
const FRONT_CONCURRENCY = 2;  // 前端同时并行提交的批次数

// 用于生成全局唯一的导入任务 ID
let importTaskCounter = 0;

export function ImportDialog({
  open,
  onOpenChange,
  onSuccess,
  onBackgroundImport,
  onBackgroundComplete,
  onImportingChange,
  onPendingResultChange,
  isRecovered,
  onRecoveredConfirm,
  isBackgroundRunning,
}: ImportDialogProps) {
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [step, setStep] = useState<ImportStep>("upload");
  const [items, setItems] = useState<ImportItem[]>([]);
  const [parseErrors, setParseErrors] = useState<string[]>([]);
  const [importResult, setImportResult] = useState<ImportResult | null>(null);
  const [error, setError] = useState("");
  const [progress, setProgress] = useState(0);
  const [isDragging, setIsDragging] = useState(false);
  const [importStage, setImportStage] = useState("");
  const [importFileName, setImportFileName] = useState("");
  const [importFileBlob, setImportFileBlob] = useState<Blob | null>(null);
  // 默认 user_id（用于没有 user_id 的导入记忆）
  const [defaultUserId, setDefaultUserId] = useState("");

  // 后台导入记录 ID
  const backgroundRecordIdRef = useRef<string | null>(null);
  // 是否已切换到后台（手动点击"后台进行"按钮）
  const isBackgroundRef = useRef(false);
  // 是否正在执行导入（用于判断关闭弹窗时是否需要转后台）
  const isImportingRef = useRef(false);
  // 当前弹窗实例是否拥有实际的导入进度数据（区分"本次发起的导入"和"从后台恢复查看"）
  const [hasLocalProgress, setHasLocalProgress] = useState(false);
  // 当前导入任务的全局唯一 ID（用于全局注册表）
  const importTaskIdRef = useRef<string | null>(null);
  // 取消导入控制
  const cancelledRef = useRef(false);
  const abortControllerRef = useRef<AbortController | null>(null);

  // 恢复模式：仅在弹窗打开且确认是真正中断时才显示中断界面
  React.useEffect(() => {
    if (open && isRecovered && step === "upload") {
      setStep("interrupted");
    }
  }, [open, isRecovered, step]);

  // 后台运行模式：SPA 切换页面后再切回来，弹窗打开时显示"导入中"界面
  React.useEffect(() => {
    if (open && isBackgroundRunning && step === "upload") {
      setStep("importing");
    }
    // 后台导入完成后（isBackgroundRunning 变为 false），如果当前仍在 importing 步骤，
    // 说明是从后台恢复的查看模式，此时导入已完成，关闭弹窗并重置
    if (!isBackgroundRunning && !isImportingRef.current && step === "importing") {
      // 导入已在后台完成，关闭弹窗
      reset();
      onOpenChange(false);
    }
  }, [open, isBackgroundRunning, step]);

  /** 解析文件内容 */
  const processFile = useCallback(async (file: File) => {
    setError("");

    // 文件大小限制
    if (file.size > MAX_FILE_SIZE) {
      setError(`文件过大（${(file.size / 1024 / 1024).toFixed(1)}MB），最大支持 10MB`);
      return;
    }

    if (!file.name.endsWith(".json")) {
      setError("仅支持 .json 格式的文件");
      return;
    }

    setImportFileName(file.name);
    // 保存文件 Blob 用于操作记录下载
    setImportFileBlob(new Blob([await file.arrayBuffer()], { type: file.type || "application/json" }));

    try {
      const text = await file.text();
      const parsed = parseImportJSON(text);
      const { valid, errors } = validateImportItems(parsed);

      // 导入条目数量限制
      if (valid.length > MAX_IMPORT_ITEMS) {
        setError(`导入条目过多（${valid.length} 条），最大支持 ${MAX_IMPORT_ITEMS} 条。请拆分文件后重试。`);
        return;
      }

      setItems(valid);
      setParseErrors(errors);
      setStep("preview");
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "文件解析失败，请检查格式"
      );
    }
  }, []);

  // 重置状态
  const reset = () => {
    setStep("upload");
    setItems([]);
    setParseErrors([]);
    setImportResult(null);
    setError("");
    setProgress(0);
    setImportFileName("");
    setImportFileBlob(null);
    setImportStage("");
    setDefaultUserId("");
    backgroundRecordIdRef.current = null;
    isBackgroundRef.current = false;
    isImportingRef.current = false;
    importTaskIdRef.current = null;
    cancelledRef.current = false;
    abortControllerRef.current = null;
    setHasLocalProgress(false);
    onPendingResultChange?.(false);
    if (fileInputRef.current) fileInputRef.current.value = "";
  };

  // 处理文件选择
  const handleFileSelect = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    processFile(file);
  };

  // 拖拽上传处理
  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(true);
  }, []);

  const handleDragLeave = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(false);
  }, []);

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(false);
    const file = e.dataTransfer.files?.[0];
    if (file) processFile(file);
  }, [processFile]);

  // 执行导入（使用批量接口，一次性提交）
  const handleImport = async () => {
    setStep("importing");
    isBackgroundRef.current = false;
    backgroundRecordIdRef.current = null;
    isImportingRef.current = true;
    setHasLocalProgress(true);
    // 注册全局导入任务（用于区分 SPA 切换 vs 页面刷新）
    const taskId = `import-${Date.now()}-${++importTaskCounter}`;
    importTaskIdRef.current = taskId;
    registerImportTask(taskId);
    onImportingChange?.(true);

    const result: ImportResult = { success: 0, failed: 0, skipped: 0, errors: [] };
    cancelledRef.current = false;
    const abortController = new AbortController();
    abortControllerRef.current = abortController;
    let wasCancelled = false;

    try {
      setProgress(0); // 开始请求
      setImportStage("准备导入...");

      // 根据数据量动态计算每批大小，使进度条固定切分为 10 份
      const batchSize = Math.min(Math.max(Math.ceil(items.length / PROGRESS_SEGMENTS), 1), MAX_BATCH_SIZE);
      const batches: ImportItem[][] = [];
      for (let i = 0; i < items.length; i += batchSize) {
        batches.push(items.slice(i, i + batchSize));
      }

      // 并行流水线提交（同时提交 FRONT_CONCURRENCY 个批次）
      let completedBatches = 0;

      const submitBatch = async (batchIdx: number) => {
        const batch = batches[batchIdx];
        const batchOffset = batchIdx * batchSize;

        try {
          const response = await mem0Api.batchImport({
            items: batch.map((item) => ({
              content: item.content,
              user_id: item.user_id,
              metadata: item.metadata,
              categories: item.categories as Category[] | undefined,
            })),
            default_user_id: defaultUserId.trim() || undefined,
            infer: false,           // 导入时原文整条存储，不让 AI 拆分
            auto_categorize: true,  // AI 自动识别标签
          }, abortController.signal);

          result.success += response.success;
          result.failed += response.failed;

          // 收集失败项的错误信息（修正索引为全局索引）
          for (const item of response.results) {
            if (!item.success && item.error) {
              result.errors.push(`第 ${batchOffset + item.index + 1} 条: ${item.error}`);
            }
          }
        } catch (err) {
          // 请求被 abort 时，无法确认后端实际处理了多少条
          // 将这些条目视为"跳过"（既不计入 success 也不计入 failed），
          // 这样取消导入时状态才能正确反映为"已取消"或"部分成功"
          if (cancelledRef.current) {
            result.skipped += batch.length;
            return;
          }
          // 当前批次整体请求失败（非取消导致的真实错误）
          result.failed += batch.length;
          result.errors.push(
            `第 ${batchOffset + 1}-${batchOffset + batch.length} 条批量导入失败: ${err instanceof Error ? err.message : "未知错误"}`
          );
        }

        // 更新进度
        completedBatches++;
        const progressValue = Math.round((completedBatches / batches.length) * 100);
        setProgress(progressValue);
        setImportStage(`已完成 ${Math.min(completedBatches * batchSize, items.length)}/${items.length} 条...`);
      };

      // 以滑动窗口方式并行提交批次
      for (let i = 0; i < batches.length; i += FRONT_CONCURRENCY) {
        if (cancelledRef.current) {
          wasCancelled = true;
          const remaining = items.length - result.success - result.failed - result.skipped;
          if (remaining > 0) {
            result.skipped += remaining;
          }
          break;
        }

        const windowEnd = Math.min(i + FRONT_CONCURRENCY, batches.length);
        const windowStart = completedBatches * batchSize + 1;
        const windowEndItem = Math.min(windowEnd * batchSize, items.length);
        setImportStage(`正在导入第 ${windowStart}-${windowEndItem} 条，共 ${items.length} 条...`);

        // 同时提交窗口内的所有批次
        const promises: Promise<void>[] = [];
        for (let j = i; j < windowEnd; j++) {
          promises.push(submitBatch(j));
        }
        await Promise.all(promises);

        // 窗口完成后检查是否被取消
        if (cancelledRef.current) {
          wasCancelled = true;
          const remaining = items.length - result.success - result.failed - result.skipped;
          if (remaining > 0) {
            result.skipped += remaining;
          }
          break;
        }
      }
      // 取消导入时，统一生成一条包含总跳过数的提示信息
      if (wasCancelled && result.skipped > 0) {
        result.errors.push(`用户取消导入，跳过 ${result.skipped} 条记忆`);
      }
      setImportStage(wasCancelled ? "导入已取消" : "导入完成！");

      // 所有批次完成后，发送 Webhook 汇总通知（无论是否取消，只要有成功/失败都通知）
      if (result.success > 0 || result.failed > 0) {
        try {
          await mem0Api.batchImportNotify({
            total: items.length,
            success: result.success,
            failed: result.failed,
            skipped: result.skipped,
          });
        } catch {
          // Webhook 通知失败不影响导入结果
        }
      }
    } catch (err) {
      // 整个导入流程异常（不太可能走到这里，但作为兜底）
      result.failed = items.length - result.success;
      result.errors.push(
        `批量导入请求失败: ${err instanceof Error ? err.message : "未知错误"}`
      );
      setProgress(100);
    }

    abortControllerRef.current = null;

    isImportingRef.current = false;
    // 注销全局导入任务
    if (importTaskIdRef.current) {
      unregisterImportTask(importTaskIdRef.current);
      importTaskIdRef.current = null;
    }
    onImportingChange?.(false);

    // 通过回调通知完成（无论前台还是后台）
    if (backgroundRecordIdRef.current) {
      onBackgroundComplete?.(backgroundRecordIdRef.current, {
        successCount: result.success,
        failedCount: result.failed,
      });
    }

    // 更新弹窗 UI 为完成状态（无论弹窗是否打开，状态都保留）
    setImportResult(result);
    setStep("done");
    // 如果弹窗当前是关闭的，通知父组件有待查看的结果
    onPendingResultChange?.(true);
    if (!backgroundRecordIdRef.current) {
      // 仅在非后台模式下通过 onSuccess 添加记录（后台模式已通过 onBackgroundImport 添加）
      // 无论成功、失败还是取消，都需要添加操作记录
      onSuccess({
        filename: importFileName,
        successCount: result.success,
        failedCount: result.failed,
        totalCount: items.length,
        blob: importFileBlob,
        wasCancelled,
        defaultUserId: defaultUserId.trim() || undefined,
      });
    }
  };

  // 后台进行（手动点击按钮）
  const handleBackgroundImport = () => {
    ensureBackgroundRecord();
    isBackgroundRef.current = true;
    // 关闭弹窗，导入继续在后台执行（不重置状态，保留进度）
    onOpenChange(false);
  };

  // 确保已创建后台导入记录
  const ensureBackgroundRecord = () => {
    if (!backgroundRecordIdRef.current && onBackgroundImport) {
      const recordId = onBackgroundImport({
        filename: importFileName,
        totalCount: items.length,
        blob: importFileBlob,
        defaultUserId: defaultUserId.trim() || undefined,
      });
      backgroundRecordIdRef.current = recordId;
    }
  };

  // 关闭弹窗处理
  const handleClose = (open: boolean) => {
    if (!open) {
      if (isImportingRef.current) {
        // 导入中关闭弹窗：自动转为后台模式（不重置状态）
        ensureBackgroundRecord();
        isBackgroundRef.current = true;
      } else if (step === "done") {
        // 完成界面关闭：重置状态
        reset();
      } else {
        // 其他情况（上传、预览）：正常重置
        reset();
      }
    }
    onOpenChange(open);
  };

  return (
    <Dialog open={open} onOpenChange={handleClose}>
      <DialogContent
        className="sm:max-w-[520px]"
      >
        <DialogHeader>
          <DialogTitle>导入记忆数据</DialogTitle>
          <DialogDescription>
            从 JSON 文件批量导入记忆数据到系统中
          </DialogDescription>
        </DialogHeader>

        {/* 步骤 1：上传文件 */}
        {step === "upload" && (
          <div className="space-y-4">
            <div
              className={`flex flex-col items-center justify-center rounded-lg border-2 border-dashed p-8 cursor-pointer transition-colors hover:border-primary hover:bg-accent/30 ${
                isDragging ? "border-primary bg-accent/30" : ""
              }`}
              onClick={() => fileInputRef.current?.click()}
              onDragOver={handleDragOver}
              onDragLeave={handleDragLeave}
              onDrop={handleDrop}
            >
              <Upload className="mb-3 h-10 w-10 text-muted-foreground" />
              <p className="text-sm font-medium">点击选择 JSON 文件</p>
              <p className="mt-1 text-xs text-muted-foreground">
                点击选择或拖拽 JSON 文件到此处
              </p>
            </div>

            <input
              ref={fileInputRef}
              type="file"
              accept=".json"
              className="hidden"
              onChange={handleFileSelect}
            />

            {error && (
              <div className="rounded-md bg-destructive/10 p-3 text-sm text-destructive">
                {error}
              </div>
            )}

            {/* 格式说明 */}
            <div className="rounded-lg bg-muted p-3 space-y-2">
              <p className="text-xs font-medium">支持的 JSON 格式：</p>
              <div className="text-xs text-muted-foreground space-y-1">
                <p>
                  <strong>格式 1</strong>（标准导出格式）：
                </p>
                <pre className="rounded bg-background p-2 overflow-x-auto">
                  {`{ "memories": [{ "memory": "内容", "user_id": "用户" }] }`}
                </pre>
                <p>
                  <strong>格式 2</strong>（简单数组）：
                </p>
                <pre className="rounded bg-background p-2 overflow-x-auto">
                  {`[{ "content": "内容", "user_id": "用户" }]`}
                </pre>
              </div>
            </div>
          </div>
        )}

        {/* 步骤 2：预览 */}
        {step === "preview" && (
          <div className="space-y-4">
            <div className="flex items-center gap-3">
              <FileJson className="h-5 w-5 text-primary" />
              <div>
                <p className="text-sm font-medium">
                  解析完成，共 {items.length} 条有效记忆
                </p>
                {parseErrors.length > 0 && (
                  <p className="text-xs text-yellow-600">
                    {parseErrors.length} 条数据有问题已跳过
                  </p>
                )}
              </div>
            </div>

            {/* 预览列表 */}
            <div className="max-h-[300px] overflow-y-auto rounded-lg border">
              <div className="divide-y">
                {items.slice(0, 10).map((item, index) => (
                  <div
                    key={index}
                    className="px-3 py-2 text-sm"
                  >
                    <p className="break-all line-clamp-2">{item.content}</p>
                    {item.user_id && (
                      <Badge variant="secondary" className="mt-1 text-xs">
                        {item.user_id}
                      </Badge>
                    )}
                  </div>
                ))}
                {items.length > 10 && (
                  <div className="px-3 py-2 text-center text-xs text-muted-foreground">
                    ... 还有 {items.length - 10} 条未显示
                  </div>
                )}
              </div>
            </div>

            {/* 解析警告 */}
            {parseErrors.length > 0 && (
              <div className="rounded-md bg-yellow-50 dark:bg-yellow-950/20 p-3 space-y-1">
                <p className="text-xs font-medium text-yellow-800 dark:text-yellow-200">
                  ⚠️ 以下数据有问题：
                </p>
                {parseErrors.map((err, i) => (
                  <p
                    key={i}
                    className="text-xs text-yellow-700 dark:text-yellow-300"
                  >
                    {err}
                  </p>
                ))}
              </div>
            )}

            {/* 默认 user_id 设置 */}
            {(() => {
              const noUserCount = items.filter((item) => !item.user_id?.trim()).length;
              return (
                <div className="rounded-lg border bg-muted/30 p-3 space-y-2">
                  <label className="flex items-center gap-1.5 text-sm font-medium">
                    <User className="h-4 w-4" />
                    默认用户 ID
                    {noUserCount > 0 && (
                      <Badge variant="destructive" className="ml-1 text-xs">
                        {noUserCount} 条缺少用户ID
                      </Badge>
                    )}
                  </label>
                  <Input
                    value={defaultUserId}
                    onChange={(e) => setDefaultUserId(e.target.value)}
                    placeholder={noUserCount > 0 ? "必填：为缺少用户ID的记忆指定默认值" : "填写后将覆盖所有记忆的用户ID"}
                    className="h-9"
                  />
                  <p className="text-xs text-muted-foreground">
                    {noUserCount > 0
                      ? `有 ${noUserCount} 条记忆缺少 user_id，请输入默认值，否则将使用 "default" 作为用户ID`
                      : "填写后所有记忆都将使用此用户ID导入；留空则使用每条记忆原有的 user_id"}
                  </p>
                </div>
              );
            })()}

            {/* 导入说明 */}
            <div className="rounded-md bg-blue-50 dark:bg-blue-950/20 p-3">
              <p className="text-xs text-blue-700 dark:text-blue-300">
                💡 导入流程：每条记忆将通过后端 API 写入数据库，AI 会自动识别并添加分类标签。记忆内容将原文存储，不会被 AI 拆分。
              </p>
            </div>

            <DialogFooter>
              <Button variant="outline" onClick={reset}>
                重新选择
              </Button>
              <Button onClick={handleImport} disabled={items.length === 0}>
                开始导入 ({items.length} 条)
              </Button>
            </DialogFooter>
          </div>
        )}

        {/* 步骤 3：导入中 */}
        {step === "importing" && (
          <div className="space-y-4 py-4">
            {/* 进度条区域 */}
            {(hasLocalProgress || !isBackgroundRunning) ? (
              <div className="space-y-2 rounded-lg border bg-muted/30 p-3">
                <div className="flex items-center justify-between text-sm">
                  <span className="flex items-center gap-2 text-muted-foreground">
                    <Loader2 className="h-4 w-4 animate-spin" />
                    {importStage || "正在导入记忆数据..."}
                  </span>
                  <span className="font-medium text-primary">{progress}%</span>
                </div>
                <Progress value={progress} className="h-2" />
              </div>
            ) : (
              <div className="space-y-2 rounded-lg border bg-muted/30 p-3">
                <div className="flex items-center gap-2 text-sm text-muted-foreground">
                  <Loader2 className="h-4 w-4 animate-spin" />
                  导入正在后台执行中，请耐心等待
                </div>
              </div>
            )}

            <p className="text-xs text-muted-foreground text-center">
              {isBackgroundRunning && !hasLocalProgress ? "" : "可点击\"后台进行\"关闭弹窗，导入将在后台继续"}
            </p>

            {/* 操作按钮 */}
            {(hasLocalProgress || !isBackgroundRunning) && (
              <DialogFooter className="gap-2 sm:gap-0">
                <Button
                  variant="destructive"
                  onClick={() => {
                    cancelledRef.current = true;
                    // 立即 abort 当前正在进行的网络请求，让 await Promise.all 马上返回
                    // 这样用户点击取消后不需要等待当前批次请求完成
                    abortControllerRef.current?.abort();
                  }}
                >
                  <Ban className="mr-1.5 h-4 w-4" />
                  取消导入
                </Button>
                <Button onClick={handleBackgroundImport}>
                  后台进行
                </Button>
              </DialogFooter>
            )}
          </div>
        )}

        {/* 步骤 4.5：导入中断（页面刷新后恢复） */}
        {step === "interrupted" && (
          <div className="space-y-4 py-4">
            <div className="flex flex-col items-center gap-3">
              <AlertTriangle className="h-10 w-10 text-yellow-500" />
              <p className="text-sm font-medium">导入已中断</p>
              <p className="text-xs text-muted-foreground text-center">
                上次的导入任务因页面刷新或关闭已中断，部分数据可能未导入完成。
                <br />
请在记录中查看详情，如需继续请重新导入。
              </p>
            </div>

            <DialogFooter>
              <Button onClick={() => {
                onRecoveredConfirm?.();
                reset();
                onOpenChange(false);
              }}>
                我知道了
              </Button>
            </DialogFooter>
          </div>
        )}

        {/* 步骤 4：完成 */}
        {step === "done" && importResult && (
          <div className="space-y-4 py-4">
            <div className="flex flex-col items-center gap-3">
              {importResult.success > 0 && importResult.failed === 0 && importResult.skipped === 0 ? (
                <CheckCircle className="h-10 w-10 text-green-500" />
              ) : importResult.success === 0 && importResult.failed === 0 ? (
                <Ban className="h-10 w-10 text-yellow-500" />
              ) : importResult.success === 0 ? (
                <XCircle className="h-10 w-10 text-red-500" />
              ) : (
                <AlertTriangle className="h-10 w-10 text-yellow-500" />
              )}
              <p className="text-sm font-medium">
                {importResult.success === 0 && importResult.failed === 0
                  ? "导入已取消"
                  : importResult.success === 0
                    ? "导入失败"
                    : importResult.failed === 0 && importResult.skipped === 0
                      ? "导入成功"
                      : "导入完成"}
              </p>
            </div>

            <div className={`grid gap-3 ${importResult.skipped > 0 ? "grid-cols-3" : "grid-cols-2"}`}>
              <div className="rounded-lg border p-3 text-center">
                <p className="text-2xl font-bold text-green-600 dark:text-green-400">
                  {importResult.success}
                </p>
                <p className="text-xs text-muted-foreground">成功</p>
              </div>
              <div className="rounded-lg border p-3 text-center">
                <p className="text-2xl font-bold text-red-600 dark:text-red-400">
                  {importResult.failed}
                </p>
                <p className="text-xs text-muted-foreground">失败</p>
              </div>
              {importResult.skipped > 0 && (
                <div className="rounded-lg border p-3 text-center">
                  <p className="text-2xl font-bold text-yellow-600 dark:text-yellow-400">
                    {importResult.skipped}
                  </p>
                  <p className="text-xs text-muted-foreground">跳过</p>
                </div>
              )}
            </div>

            {importResult.errors.length > 0 && (
              <div className="max-h-[150px] overflow-y-auto rounded-md bg-destructive/10 p-3 space-y-1">
                {importResult.errors.map((err, i) => (
                  <p key={i} className="text-xs text-destructive">
                    {err}
                  </p>
                ))}
              </div>
            )}

            <DialogFooter>
              <Button onClick={() => handleClose(false)}>完成</Button>
            </DialogFooter>
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}
