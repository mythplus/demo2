"use client";

import React, { useState } from "react";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Loader2, AlertTriangle, Sparkles, Check } from "lucide-react";
import { toast } from "@/hooks/use-toast";
import { mem0Api } from "@/lib/api";
import type { Category, AddMemoryResponse } from "@/lib/api";
import { CATEGORY_LIST, getCategoryInfo } from "@/lib/constants";
import { cn } from "@/lib/utils";

interface AddMemoryDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onSuccess: () => void;
}

export function AddMemoryDialog({
  open,
  onOpenChange,
  onSuccess,
}: AddMemoryDialogProps) {
  const [content, setContent] = useState("");
  const [userId, setUserId] = useState("");
  const [selectedCategories, setSelectedCategories] = useState<Category[]>([]);
  const [infer, setInfer] = useState(false);                  // 存储模式：false=原文存储，true=AI 智能提取
  const [autoCategorize, setAutoCategorize] = useState(true); // 默认开启 AI 自动分类
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [warning, setWarning] = useState("");

  const toggleCategory = (cat: Category) => {
    setSelectedCategories((prev) =>
      prev.includes(cat) ? prev.filter((c) => c !== cat) : [...prev, cat]
    );
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!content.trim()) {
      setError("请输入记忆内容");
      return;
    }
    if (!userId.trim()) {
      setError("请输入用户 ID");
      return;
    }

    setLoading(true);
    setError("");
    setWarning("");

    try {
      const result: AddMemoryResponse = await mem0Api.addMemory({
        messages: [{ role: "user", content: content.trim() }],
        user_id: userId.trim(),
        categories: selectedCategories.length > 0 ? selectedCategories : undefined,
        infer: infer,
        auto_categorize: autoCategorize,
      });

      // 检查返回结果是否为空（LLM 可能判断内容不值得提取）
      const addedCount = result?.results?.filter((r) => r.event === "ADD").length ?? 0;
      if (result?.results?.length === 0 || addedCount === 0) {
        setWarning(
          infer
            ? "AI 未从内容中提取到有效记忆。建议切换到「📝 原文存储」模式重试。"
            : "记忆添加未生效，请检查内容后重试。"
        );
        return;
      }

      // 重置表单
      setContent("");
      setUserId("");
      setSelectedCategories([]);
      setInfer(false);
      setAutoCategorize(true);
      setWarning("");
      toast({
        title: "添加成功",
        description: `已成功添加 ${addedCount} 条记忆`,
        variant: "success",
      });
      onOpenChange(false);
      onSuccess();
    } catch (err) {
      // B4 P1-4: 根据错误类型给出友好提示
      if (err instanceof Error) {
        const msg = err.message;
        if (msg.includes("超时")) {
          setError("请求超时，请检查网络连接或稍后重试");
        } else if (msg.includes("503") || msg.includes("暂不可用")) {
          setError("服务暂不可用，请检查后端连接状态");
        } else if (msg.includes("500") || msg.includes("内部错误")) {
          setError("添加失败，请稍后重试。如持续出现请联系管理员");
        } else {
          setError(msg);
        }
      } else {
        setError("添加失败，请稍后重试");
      }
    } finally {
      setLoading(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[520px]">
        <DialogHeader>
          <DialogTitle>添加记忆</DialogTitle>
          <DialogDescription>
            输入一段文本，Mem0 会自动提取并存储关键记忆信息
          </DialogDescription>
        </DialogHeader>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="space-y-2">
            <label className="text-sm font-medium">记忆内容 *</label>
            <Textarea
              placeholder="例如：我喜欢蓝色，平时爱喝咖啡，周末经常去爬山..."
              value={content}
              onChange={(e) => setContent(e.target.value)}
              rows={4}
              disabled={loading}
            />
          </div>

          <div className="space-y-2">
            <label className="text-sm font-medium">用户 ID *</label>
            <Input
              placeholder="例如：user_001"
              value={userId}
              onChange={(e) => setUserId(e.target.value)}
              disabled={loading}
              required
            />
            <p className="text-xs text-muted-foreground">
              记忆将关联到该用户
            </p>
          </div>

          {/* 分类标签 */}
          <div className="space-y-2">
            <label className="text-sm font-medium">分类标签</label>
            <div className="flex items-center gap-3">
              <button
                type="button"
                onClick={() => {
                  setAutoCategorize(true);
                  setSelectedCategories([]);
                }}
                disabled={loading}
                className={cn(
                  "inline-flex items-center gap-1 rounded-md px-3 py-1.5 text-xs font-medium transition-colors cursor-pointer",
                  autoCategorize
                    ? "bg-primary text-primary-foreground"
                    : "bg-muted text-muted-foreground hover:bg-muted/80"
                )}
              >
                <Sparkles className="h-3 w-3" />
                AI 自动分类
              </button>
              <button
                type="button"
                onClick={() => setAutoCategorize(false)}
                disabled={loading}
                className={cn(
                  "inline-flex items-center gap-1 rounded-md px-3 py-1.5 text-xs font-medium transition-colors cursor-pointer",
                  !autoCategorize
                    ? "bg-primary text-primary-foreground"
                    : "bg-muted text-muted-foreground hover:bg-muted/80"
                )}
              >
                ✏️ 手动选择
              </button>
            </div>
            {autoCategorize ? (
              <p className="text-xs text-muted-foreground">
                💡 添加记忆后，AI 将自动分析内容并打上合适的分类标签
              </p>
            ) : (
              <div className="flex flex-wrap gap-1.5">
                {CATEGORY_LIST.map((cat) => {
                  const isSelected = selectedCategories.includes(cat.value);
                  return (
                    <button
                      key={cat.value}
                      type="button"
                      onClick={() => toggleCategory(cat.value)}
                      disabled={loading}
                      className={cn(
                        "inline-flex items-center gap-1 rounded-full px-2.5 py-1 text-xs font-medium transition-all cursor-pointer border",
                        isSelected
                          ? "bg-primary text-primary-foreground border-primary shadow-sm"
                          : "bg-muted text-muted-foreground border-transparent hover:bg-muted/80"
                      )}
                    >
                      {isSelected && <Check className="h-3 w-3" />}
                      {cat.label}
                    </button>
                  );
                })}
              </div>
            )}
          </div>

          {/* 存储模式 */}
          <div className="space-y-2">
            <label className="text-sm font-medium">存储模式</label>
            <div className="flex items-center gap-3">
              <button
                type="button"
                onClick={() => setInfer(true)}
                disabled={loading}
                className={cn(
                  "inline-flex items-center rounded-md px-3 py-1.5 text-xs font-medium transition-colors cursor-pointer",
                  infer
                    ? "bg-primary text-primary-foreground"
                    : "bg-muted text-muted-foreground hover:bg-muted/80"
                )}
              >
                🤖 AI 智能提取
              </button>
              <button
                type="button"
                onClick={() => setInfer(false)}
                disabled={loading}
                className={cn(
                  "inline-flex items-center rounded-md px-3 py-1.5 text-xs font-medium transition-colors cursor-pointer",
                  !infer
                    ? "bg-primary text-primary-foreground"
                    : "bg-muted text-muted-foreground hover:bg-muted/80"
                )}
              >
                📝 原文存储
              </button>
            </div>
            <p className="text-xs text-muted-foreground">
              {infer
                ? "AI 会自动提取关键信息，可能将内容拆分为多条记忆"
                : "将输入内容作为一条完整记忆原样存储，不做拆分"}
            </p>
          </div>

          {warning && (
            <div className="rounded-md bg-yellow-500/10 border border-yellow-500/20 p-3 text-sm text-yellow-700 dark:text-yellow-400 flex items-start gap-2">
              <AlertTriangle className="h-4 w-4 mt-0.5 shrink-0" />
              <span>{warning}</span>
            </div>
          )}

          {error && (
            <div className="rounded-md bg-destructive/10 p-3 text-sm text-destructive">
              {error}
            </div>
          )}

          <DialogFooter>
            <Button
              type="button"
              variant="outline"
              onClick={() => onOpenChange(false)}
              disabled={loading}
            >
              取消
            </Button>
            <Button type="submit" disabled={loading}>
              {loading && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              添加记忆
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
