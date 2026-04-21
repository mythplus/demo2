"use client";

import React, { useState, useCallback } from "react";
import { Button } from "@/components/ui/button";
import { Code, Check, AlertCircle } from "lucide-react";
import { cn } from "@/lib/utils";

interface JsonEditorProps {
  value: Record<string, unknown>;
  onChange?: (value: Record<string, unknown>) => void;
  readOnly?: boolean;
  className?: string;
}

export function JsonEditor({
  value,
  onChange,
  readOnly = false,
  className,
}: JsonEditorProps) {
  const [text, setText] = useState(JSON.stringify(value, null, 2));
  const [error, setError] = useState<string | null>(null);
  const [isFormatted, setIsFormatted] = useState(true);

  // 当外部 value 变化时同步（使用序列化字符串作为依赖，避免对象引用变化导致无限触发）
  const valueStr = JSON.stringify(value);
  React.useEffect(() => {
    setText(JSON.stringify(value, null, 2));
    setError(null);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [valueStr]);

  const handleChange = useCallback(
    (newText: string) => {
      setText(newText);
      try {
        const parsed = JSON.parse(newText);
        setError(null);
        if (onChange && typeof parsed === "object" && parsed !== null && !Array.isArray(parsed)) {
          onChange(parsed);
        }
      } catch (e) {
        setError(e instanceof Error ? e.message : "Invalid JSON");
      }
    },
    [onChange]
  );

  const handleFormat = () => {
    try {
      const parsed = JSON.parse(text);
      const formatted = isFormatted
        ? JSON.stringify(parsed)
        : JSON.stringify(parsed, null, 2);
      setText(formatted);
      setIsFormatted(!isFormatted);
      setError(null);
    } catch {
      // 格式化失败时不处理
    }
  };

  // 行号计算
  const lines = text.split("\n");

  return (
    <div className={cn("rounded-lg border overflow-hidden", className)}>
      {/* 工具栏 */}
      <div className="flex items-center justify-between border-b bg-muted/30 px-3 py-1.5">
        <div className="flex items-center gap-1.5">
          <Code className="h-3.5 w-3.5 text-muted-foreground" />
          <span className="text-xs text-muted-foreground font-medium">JSON</span>
        </div>
        <div className="flex items-center gap-1.5">
          {error ? (
            <span className="flex items-center gap-1 text-xs text-destructive">
              <AlertCircle className="h-3 w-3" />
              格式错误
            </span>
          ) : (
            <span className="flex items-center gap-1 text-xs text-green-600 dark:text-green-400">
              <Check className="h-3 w-3" />
              有效
            </span>
          )}
          {!readOnly && (
            <Button variant="ghost" size="sm" className="h-6 px-2 text-xs" onClick={handleFormat}>
              {isFormatted ? "压缩" : "格式化"}
            </Button>
          )}
        </div>
      </div>

      {/* 编辑器主体 */}
      <div className="flex max-h-[300px] overflow-auto">
        {/* 行号 */}
        <div className="flex-shrink-0 select-none border-r bg-muted/20 px-2 py-2 text-right">
          {lines.map((_, i) => (
            <div key={i} className="text-xs leading-5 text-muted-foreground/50 font-mono">
              {i + 1}
            </div>
          ))}
        </div>

        {/* 文本区域 */}
        <textarea
          value={text}
          onChange={(e) => handleChange(e.target.value)}
          readOnly={readOnly}
          className={cn(
            "flex-1 resize-none bg-transparent p-2 text-xs leading-5 font-mono focus:outline-none",
            readOnly && "cursor-default"
          )}
          style={{ minHeight: `${Math.max(lines.length * 20 + 16, 80)}px` }}
          spellCheck={false}
        />
      </div>

      {/* 错误详情 */}
      {error && (
        <div className="border-t bg-destructive/5 px-3 py-1.5">
          <p className="text-xs text-destructive truncate">{error}</p>
        </div>
      )}
    </div>
  );
}
