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
import {
  Upload,
  FileJson,
  Loader2,
  CheckCircle,
  AlertTriangle,
} from "lucide-react";
import {
  parseImportJSON,
  validateImportItems,
  type ImportItem,
  type ImportResult,
} from "@/lib/data-transfer";
import { mem0Api } from "@/lib/api";
import type { Category, MemoryState } from "@/lib/api/types";
import { registerImportTask, unregisterImportTask } from "@/lib/import-task-registry";

/** 导入成功回调信息 */
export interface ImportSuccessInfo {
  filename: string;
  successCount: number;
  failedCount: number;
  blob: Blob | null;
}

/** 后台导入信息 */
export interface BackgroundImportInfo {
  filename: string;
  totalCount: number;
  blob: Blob | null;
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
  const [importFileName, setImportFileName] = useState("");
  const [importFileBlob, setImportFileBlob] = useState<Blob | null>(null);

  // 后台导入记录 ID
  const backgroundRecordIdRef = useRef<string | null>(null);
  // 是否已切换到后台（手动点击"后台进行"按钮）
  const isBackgroundRef = useRef(false);
  // 是否正在执行导入（用于判断关闭弹窗时是否需要转后台）
  const isImportingRef = useRef(false);
  // 当前导入任务的全局唯一 ID（用于全局注册表）
  const importTaskIdRef = useRef<string | null>(null);

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
    setImportFileName(file.name);
    // 保存文件 Blob 用于操作记录下载
    setImportFileBlob(new Blob([await file.arrayBuffer()], { type: file.type || "application/json" }));

    if (!file.name.endsWith(".json")) {
      setError("仅支持 .json 格式的文件");
      return;
    }

    try {
      const text = await file.text();
      const parsed = parseImportJSON(text);
      const { valid, errors } = validateImportItems(parsed);

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
    backgroundRecordIdRef.current = null;
    isBackgroundRef.current = false;
    isImportingRef.current = false;
    importTaskIdRef.current = null;
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

  // 执行导入（并发批量，每批 5 条）
  const handleImport = async () => {
    setStep("importing");
    isBackgroundRef.current = false;
    backgroundRecordIdRef.current = null;
    isImportingRef.current = true;
    // 注册全局导入任务（用于区分 SPA 切换 vs 页面刷新）
    const taskId = `import-${Date.now()}-${++importTaskCounter}`;
    importTaskIdRef.current = taskId;
    registerImportTask(taskId);
    onImportingChange?.(true);

    const result: ImportResult = { success: 0, failed: 0, errors: [] };
    const BATCH_SIZE = 5;
    let completed = 0;

    for (let i = 0; i < items.length; i += BATCH_SIZE) {
      const batch = items.slice(i, i + BATCH_SIZE);

      const promises = batch.map(async (item, batchIdx) => {
        const globalIdx = i + batchIdx;
        try {
          await mem0Api.addMemory({
            messages: [{ role: "user", content: item.content }],
            user_id: item.user_id,
            metadata: item.metadata,
            categories: item.categories as Category[] | undefined,
            state: item.state as MemoryState | undefined,
          });
          result.success++;
        } catch (err) {
          result.failed++;
          result.errors.push(
            `第 ${globalIdx + 1} 条: ${err instanceof Error ? err.message : "导入失败"}`
          );
        }
      });

      await Promise.all(promises);

      completed += batch.length;
      const newProgress = Math.round((completed / items.length) * 100);
      setProgress(newProgress);
    }

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
    if (result.success > 0 && !backgroundRecordIdRef.current) {
      // 仅在非后台模式下通过 onSuccess 添加记录（后台模式已通过 onBackgroundImport 添加）
      onSuccess({
        filename: importFileName,
        successCount: result.success,
        failedCount: result.failed,
        blob: importFileBlob,
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
            <div className="flex flex-col items-center gap-3">
              <Loader2 className="h-10 w-10 animate-spin text-primary" />
              <p className="text-sm font-medium">正在导入记忆数据...</p>
              <p className="text-xs text-muted-foreground">
                {isBackgroundRunning ? "导入正在后台执行中，请耐心等待" : "可点击\"后台进行\"在后台继续导入"}
              </p>
            </div>

            {/* 进度条（仅在非后台恢复模式下显示，因为后台恢复时没有进度数据） */}
            {!isBackgroundRunning && (
              <div className="space-y-1">
                <div className="flex justify-between text-xs text-muted-foreground">
                  <span>进度</span>
                  <span>{progress}%</span>
                </div>
                <div className="h-2 rounded-full bg-muted overflow-hidden">
                  <div
                    className="h-full rounded-full bg-primary transition-all duration-300"
                    style={{ width: `${progress}%` }}
                  />
                </div>
              </div>
            )}

            {/* 后台进行按钮（仅在非后台恢复模式下显示） */}
            {!isBackgroundRunning && (
              <DialogFooter>
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
                请在操作汇总中查看详情，如需继续请重新导入。
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
              {importResult.failed === 0 ? (
                <CheckCircle className="h-10 w-10 text-green-500" />
              ) : (
                <AlertTriangle className="h-10 w-10 text-yellow-500" />
              )}
              <p className="text-sm font-medium">导入完成</p>
            </div>

            <div className="grid grid-cols-2 gap-3">
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
