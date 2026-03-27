"use client";

import React from "react";
import { cn } from "@/lib/utils";

/**
 * 通用骨架屏组件
 */
interface SkeletonProps {
  className?: string;
}

export function Skeleton({ className }: SkeletonProps) {
  return (
    <div className={cn("animate-pulse rounded-md bg-muted", className)} />
  );
}

/** 统计卡片骨架屏 */
export function StatsCardSkeleton() {
  return (
    <div className="rounded-lg border bg-card p-6 space-y-3">
      <div className="flex items-center justify-between">
        <Skeleton className="h-4 w-20" />
        <Skeleton className="h-4 w-4 rounded" />
      </div>
      <Skeleton className="h-8 w-16" />
      <Skeleton className="h-3 w-32" />
    </div>
  );
}

/** 记忆列表项骨架屏 */
export function MemoryItemSkeleton() {
  return (
    <div className="rounded-lg border p-4 space-y-3">
      <div className="flex items-center gap-2">
        <Skeleton className="h-5 w-12 rounded-full" />
      </div>
      <Skeleton className="h-4 w-full" />
      <Skeleton className="h-4 w-3/4" />
      <div className="flex items-center gap-2">
        <Skeleton className="h-5 w-16 rounded-full" />
        <Skeleton className="h-5 w-12 rounded-full" />
        <Skeleton className="h-3 w-24" />
      </div>
    </div>
  );
}

/** 记忆列表骨架屏 */
export function MemoryListSkeleton({ count = 5 }: { count?: number }) {
  return (
    <div className="space-y-3">
      {Array.from({ length: count }, (_, i) => (
        <MemoryItemSkeleton key={i} />
      ))}
    </div>
  );
}

/** 图表骨架屏 */
export function ChartSkeleton() {
  return (
    <div className="rounded-lg border bg-card p-6 space-y-4">
      <div className="space-y-1">
        <Skeleton className="h-5 w-24" />
        <Skeleton className="h-3 w-36" />
      </div>
      <Skeleton className="h-[200px] w-full rounded" />
    </div>
  );
}

/** 详情页骨架屏 */
export function DetailPageSkeleton() {
  return (
    <div className="grid gap-6 lg:grid-cols-3">
      <div className="lg:col-span-2 space-y-6">
        <div className="rounded-lg border bg-card p-6 space-y-4">
          <Skeleton className="h-5 w-20" />
          <Skeleton className="h-24 w-full rounded" />
        </div>
        <div className="rounded-lg border bg-card p-6 space-y-4">
          <Skeleton className="h-5 w-20" />
          <div className="space-y-3">
            <Skeleton className="h-16 w-full rounded" />
            <Skeleton className="h-16 w-full rounded" />
          </div>
        </div>
      </div>
      <div className="space-y-6">
        <div className="rounded-lg border bg-card p-6 space-y-4">
          <Skeleton className="h-5 w-20" />
          <Skeleton className="h-4 w-full" />
          <Skeleton className="h-4 w-24" />
          <Skeleton className="h-4 w-32" />
        </div>
      </div>
    </div>
  );
}
