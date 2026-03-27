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
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Loader2 } from "lucide-react";
import { mem0Api } from "@/lib/api";
import type { Memory, Category, MemoryState } from "@/lib/api";
import { CATEGORY_LIST, STATE_LIST } from "@/lib/constants";
import { cn } from "@/lib/utils";

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
  const [state, setState] = useState<MemoryState>(
    (memory?.state as MemoryState) || "active"
  );
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  // 当 memory 变化时更新内容
  React.useEffect(() => {
    if (memory) {
      setContent(memory.memory);
      setSelectedCategories((memory.categories as Category[]) || []);
      setState((memory.state as MemoryState) || "active");
    }
  }, [memory]);

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
        state: state,
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
      <DialogContent className="sm:max-w-[520px]">
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
            <div className="rounded-md bg-muted p-3 text-sm">
              <span className="text-muted-foreground">所属用户：</span>
              <span className="font-medium">{memory.user_id}</span>
            </div>
          )}

          {/* 分类选择 */}
          <div className="space-y-2">
            <label className="text-sm font-medium">分类标签</label>
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
            <label className="text-sm font-medium">状态</label>
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
              保存修改
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
