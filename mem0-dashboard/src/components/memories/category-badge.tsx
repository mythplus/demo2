"use client";

import React from "react";
import { cn } from "@/lib/utils";
import type { Category } from "@/lib/api";
import { getCategoryInfo } from "@/lib/constants";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";

interface CategoryBadgeProps {
  category: Category;
  className?: string;
  size?: "sm" | "md";
}

export function CategoryBadge({ category, className, size = "sm" }: CategoryBadgeProps) {
  const info = getCategoryInfo(category);
  if (!info) return null;

  return (
    <TooltipProvider delayDuration={200}>
      <Tooltip>
        <TooltipTrigger asChild>
          <span
            className={cn(
              "inline-flex items-center rounded-full font-medium border transition-colors cursor-default category-badge whitespace-nowrap",
              "border-gray-200 dark:border-gray-700",
              size === "sm" ? "px-2.5 py-0.5 text-xs" : "px-3 py-1 text-sm",
              className
            )}
            style={{
              "--cat-light-bg": info.lightBg,
              "--cat-light-text": info.lightText,
              "--cat-dark-bg": info.darkBg,
              "--cat-dark-text": info.darkText,
              backgroundColor: "var(--cat-light-bg)",
              color: "var(--cat-light-text)",
            } as React.CSSProperties}
          >
            {info.label}
          </span>
        </TooltipTrigger>
        <TooltipContent side="top">
          <p className="text-xs">分类：{info.label}</p>
        </TooltipContent>
      </Tooltip>
    </TooltipProvider>
  );
}

/** 批量渲染分类标签 */
export function CategoryBadges({
  categories,
  className,
  max,
  nowrap,
}: {
  categories?: Category[];
  className?: string;
  max?: number;
  /** 不换行模式，适用于表格等紧凑场景 */
  nowrap?: boolean;
}) {
  if (!categories || categories.length === 0) return null;

  const shown = max ? categories.slice(0, max) : categories;
  const remaining = max ? categories.length - max : 0;
  const hiddenCategories = max ? categories.slice(max) : [];

  return (
    <div className={cn("flex gap-1.5 items-center", nowrap ? "flex-nowrap" : "flex-wrap", className)}>
      {shown.map((cat) => (
        <CategoryBadge key={cat} category={cat} />
      ))}
      {remaining > 0 && (
        <TooltipProvider delayDuration={200}>
          <Tooltip>
            <TooltipTrigger asChild>
              <span className="inline-flex items-center rounded-full bg-muted border border-muted-foreground/20 px-2.5 py-0.5 text-xs font-medium text-muted-foreground cursor-default transition-colors hover:bg-muted/80">
                +{remaining}
              </span>
            </TooltipTrigger>
            <TooltipContent side="top">
              <p className="text-xs">
                {hiddenCategories
                  .map((cat) => getCategoryInfo(cat)?.label || cat)
                  .join("、")}
              </p>
            </TooltipContent>
          </Tooltip>
        </TooltipProvider>
      )}
    </div>
  );
}
