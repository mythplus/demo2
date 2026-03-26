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
import { Loader2 } from "lucide-react";
import { mem0Api } from "@/lib/api";

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
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!content.trim()) {
      setError("请输入记忆内容");
      return;
    }

    setLoading(true);
    setError("");

    try {
      await mem0Api.addMemory({
        messages: [{ role: "user", content: content.trim() }],
        user_id: userId.trim() || undefined,
      });
      // 重置表单
      setContent("");
      setUserId("");
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
      <DialogContent className="sm:max-w-[500px]">
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
            <label className="text-sm font-medium">用户 ID（可选）</label>
            <Input
              placeholder="例如：user_001"
              value={userId}
              onChange={(e) => setUserId(e.target.value)}
              disabled={loading}
            />
            <p className="text-xs text-muted-foreground">
              不填则不关联用户，记忆将作为全局记忆存储
            </p>
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
