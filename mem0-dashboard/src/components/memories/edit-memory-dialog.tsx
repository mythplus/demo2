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
import { Textarea } from "@/components/ui/textarea";
import { Loader2, Code, Sparkles, Check } from "lucide-react";
import { toast } from "@/hooks/use-toast";
import { mem0Api } from "@/lib/api";
import type { Memory, Category } from "@/lib/api";
import { CATEGORY_LIST } from "@/lib/constants";
import { cn } from "@/lib/utils";
import { JsonEditor } from "./json-editor";

interface EditMemoryDialogProps {
  memory: Memory | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onSuccess: () => void;
}

export function EditMemoryDialog({
  memory,
  open,
  onOpenChange,
  onSuccess,
}: EditMemoryDialogProps) {
  const [content, setContent] = useState(memory?.memory || "");
  const [selectedCategories, setSelectedCategories] = useState<Category[]>(
    (memory?.categories as Category[]) || []
  );
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [metadata, setMetadata] = useState<Record<string, unknown>>(
    (memory?.metadata as Record<string, unknown>) || {}
  );
  const [showMetadata, setShowMetadata] = useState(false);
  const [aiCategorizing, setAiCategorizing] = useState(false);

  // 当 memory 或弹窗打开状态变化时更新内容（加 open 依赖避免快速切换时闭包旧值）
  React.useEffect(() => {
    if (memory && open) {
      setContent(memory.memory);
      setSelectedCategories((memory.categories as Category[]) || []);
      setMetadata((memory.metadata as Record<string, unknown>) || {});
      setError("");
      setShowMetadata(false);
    }
  }, [memory, open]);

  const toggleCategory = (cat: Category) => {
    setSelectedCategories((prev) =>
      prev.includes(cat) ? prev.filter((c) => c !== cat) : [...prev, cat]
    );
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!memory || !content.trim()) {
      setError("请输入记忆内容");
      return;
    }

    setLoading(true);
    setError("");

    try {
      await mem0Api.updateMemory(memory.id, {
        text: content.trim(),
        categories: selectedCategories,
        metadata: Object.keys(metadata).length > 0 ? metadata : undefined,
      });
      toast({
        title: "编辑成功",
        description: "记忆内容已更新",
        variant: "success",
      });
      onOpenChange(false);
      onSuccess();
    } catch (err) {
      setError(err instanceof Error ? err.message : "更新失败");
    } finally {
      setLoading(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[520px] max-h-[85vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>编辑记忆</DialogTitle>
          <DialogDescription>
            修改记忆内容，ID: {memory?.id?.slice(0, 8)}...
          </DialogDescription>
        </DialogHeader>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="space-y-2">
            <label className="text-sm font-medium">记忆内容</label>
            <Textarea
              value={content}
              onChange={(e) => setContent(e.target.value)}
              rows={4}
              disabled={loading}
            />
          </div>

          {memory?.user_id && (
            <div className="rounded-md bg-muted p-3 text-sm overflow-hidden">
              <span className="text-muted-foreground">所属用户：</span>
              <span className="font-medium break-all line-clamp-2" title={memory.user_id}>{memory.user_id}</span>
            </div>
          )}

          {/* 分类选择 */}
          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <label className="text-sm font-medium">分类标签</label>
              <button
                type="button"
                onClick={async () => {
                  if (!memory) return;
                  setAiCategorizing(true);
                  try {
                    await mem0Api.updateMemory(memory.id, {
                      auto_categorize: true,
                    });
                    // 重新获取记忆以更新分类
                    const updated = await mem0Api.getMemory(memory.id);
                    if (updated?.categories) {
                      setSelectedCategories(updated.categories as Category[]);
                    }
                  } catch (err) {
                    setError(err instanceof Error ? err.message : "AI 分类失败");
                  } finally {
                    setAiCategorizing(false);
                  }
                }}
                disabled={loading || aiCategorizing}
                className={cn(
                  "inline-flex items-center gap-1 rounded-md px-2 py-1 text-xs font-medium transition-colors cursor-pointer",
                  "bg-violet-100 text-violet-700 dark:bg-violet-900/30 dark:text-violet-300 hover:bg-violet-200 dark:hover:bg-violet-900/50"
                )}
              >
                {aiCategorizing ? (
                  <Loader2 className="h-3 w-3 animate-spin" />
                ) : (
                  <Sparkles className="h-3 w-3" />
                )}
                AI 重新分类
              </button>
            </div>
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
          </div>

          {/* Metadata 编辑器 */}
          <div className="space-y-2">
            <button
              type="button"
              className="flex items-center gap-1.5 text-sm font-medium text-muted-foreground hover:text-foreground transition-colors"
              onClick={() => setShowMetadata(!showMetadata)}
            >
              <Code className="h-3.5 w-3.5" />
              元数据 (metadata)
              <span className="text-xs">
                {showMetadata ? "▼" : "▶"}
              </span>
            </button>
            {showMetadata && (
              <JsonEditor
                value={metadata}
                onChange={setMetadata}
                readOnly={loading}
              />
            )}
          </div>

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
              保存修改
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
