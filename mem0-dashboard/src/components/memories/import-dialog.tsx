"use client";

import React, { useState, useRef } from "react";
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

interface ImportDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onSuccess: () => void;
}

type ImportStep = "upload" | "preview" | "importing" | "done";

export function ImportDialog({
  open,
  onOpenChange,
  onSuccess,
}: ImportDialogProps) {
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [step, setStep] = useState<ImportStep>("upload");
  const [items, setItems] = useState<ImportItem[]>([]);
  const [parseErrors, setParseErrors] = useState<string[]>([]);
  const [importResult, setImportResult] = useState<ImportResult | null>(null);
  const [error, setError] = useState("");
  const [progress, setProgress] = useState(0);

  // 重置状态
  const reset = () => {
    setStep("upload");
    setItems([]);
    setParseErrors([]);
    setImportResult(null);
    setError("");
    setProgress(0);
    if (fileInputRef.current) fileInputRef.current.value = "";
  };

  // 处理文件选择
  const handleFileSelect = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    setError("");

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
  };

  // 执行导入
  const handleImport = async () => {
    setStep("importing");
    const result: ImportResult = { success: 0, failed: 0, errors: [] };

    for (let i = 0; i < items.length; i++) {
      const item = items[i];
      setProgress(Math.round(((i + 1) / items.length) * 100));

      try {
        await mem0Api.addMemory({
          messages: [{ role: "user", content: item.content }],
          user_id: item.user_id,
          metadata: item.metadata,
        });
        result.success++;
      } catch (err) {
        result.failed++;
        result.errors.push(
          `第 ${i + 1} 条: ${err instanceof Error ? err.message : "导入失败"}`
        );
      }
    }

    setImportResult(result);
    setStep("done");
    if (result.success > 0) {
      onSuccess();
    }
  };

  // 关闭时重置
  const handleClose = (open: boolean) => {
    if (!open) reset();
    onOpenChange(open);
  };

  return (
    <Dialog open={open} onOpenChange={handleClose}>
      <DialogContent className="sm:max-w-[520px]">
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
              className="flex flex-col items-center justify-center rounded-lg border-2 border-dashed p-8 cursor-pointer transition-colors hover:border-primary hover:bg-accent/30"
              onClick={() => fileInputRef.current?.click()}
            >
              <Upload className="mb-3 h-10 w-10 text-muted-foreground" />
              <p className="text-sm font-medium">点击选择 JSON 文件</p>
              <p className="mt-1 text-xs text-muted-foreground">
                支持标准导出格式或简单数组格式
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
            <div className="max-h-[300px] overflow-y-auto space-y-2 rounded-lg border p-3">
              {items.slice(0, 10).map((item, index) => (
                <div
                  key={index}
                  className="rounded border p-2 text-sm"
                >
                  <p className="truncate">{item.content}</p>
                  {item.user_id && (
                    <Badge variant="secondary" className="mt-1 text-xs">
                      {item.user_id}
                    </Badge>
                  )}
                </div>
              ))}
              {items.length > 10 && (
                <p className="text-center text-xs text-muted-foreground py-2">
                  ... 还有 {items.length - 10} 条未显示
                </p>
              )}
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
                请勿关闭此窗口
              </p>
            </div>

            {/* 进度条 */}
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
                <p className="text-2xl font-bold text-green-600">
                  {importResult.success}
                </p>
                <p className="text-xs text-muted-foreground">成功</p>
              </div>
              <div className="rounded-lg border p-3 text-center">
                <p className="text-2xl font-bold text-red-600">
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
