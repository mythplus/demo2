"use client";

import React from "react";
import { cn } from "@/lib/utils";
import type { Category } from "@/lib/api";
import { getCategoryInfo } from "@/lib/constants";

interface CategoryBadgeProps {
  category: Category;
  className?: string;
  size?: "sm" | "md";
}

export function CategoryBadge({ category, className, size = "sm" }: CategoryBadgeProps) {
  const info = getCategoryInfo(category);
  if (!info) return null;

  return (
    <span
      className={cn(
        "inline-flex items-center rounded-full font-medium",
        info.bgColor,
        info.textColor,
        size === "sm" ? "px-2 py-0.5 text-xs" : "px-2.5 py-1 text-sm",
        className
      )}
    >
      {info.label}
    </span>
  );
}

/** 批量渲染分类标签 */
export function CategoryBadges({
  categories,
  className,
  max,
}: {
  categories?: Category[];
  className?: string;
  max?: number;
}) {
  if (!categories || categories.length === 0) return null;

  const shown = max ? categories.slice(0, max) : categories;
  const remaining = max ? categories.length - max : 0;

  return (
    <div className={cn("flex flex-wrap gap-1", className)}>
      {shown.map((cat) => (
        <CategoryBadge key={cat} category={cat} />
      ))}
      {remaining > 0 && (
        <span className="inline-flex items-center rounded-full bg-muted px-2 py-0.5 text-xs text-muted-foreground">
          +{remaining}
        </span>
      )}
    </div>
  );
}
