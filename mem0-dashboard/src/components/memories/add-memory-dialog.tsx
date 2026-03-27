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
import { Loader2 } from "lucide-react";
import { mem0Api } from "@/lib/api";
import type { Category, MemoryState } from "@/lib/api";
import { CATEGORY_LIST, STATE_LIST, getCategoryInfo } from "@/lib/constants";
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
  const [state, setState] = useState<MemoryState>("active");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

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

    try {
      await mem0Api.addMemory({
        messages: [{ role: "user", content: content.trim() }],
        user_id: userId.trim(),
        categories: selectedCategories.length > 0 ? selectedCategories : undefined,
        state: state,
      });
      // 重置表单
      setContent("");
      setUserId("");
      setSelectedCategories([]);
      setState("active");
      onOpenChange(false);
      onSuccess();
    } catch (err) {
      setError(err instanceof Error ? err.message : "添加失败");
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

          {/* 分类选择 */}
          <div className="space-y-2">
            <label className="text-sm font-medium">分类标签（可选）</label>
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
                      "inline-flex items-center rounded-full px-2.5 py-1 text-xs font-medium transition-colors cursor-pointer",
                      isSelected
                        ? cn(cat.bgColor, cat.textColor, "ring-1 ring-current")
                        : "bg-muted text-muted-foreground hover:bg-muted/80"
                    )}
                  >
                    {cat.label}
                  </button>
                );
              })}
            </div>
          </div>

          {/* 状态选择 */}
          <div className="space-y-2">
            <label className="text-sm font-medium">初始状态</label>
            <Select
              value={state}
              onValueChange={(v) => setState(v as MemoryState)}
              disabled={loading}
            >
              <SelectTrigger className="w-[160px]">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {STATE_LIST.map((s) => (
                  <SelectItem key={s.value} value={s.value}>
                    <span className="flex items-center gap-1.5">
                      <span className={cn("h-1.5 w-1.5 rounded-full", s.dotColor)} />
                      {s.label}
                    </span>
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
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
              添加记忆
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
