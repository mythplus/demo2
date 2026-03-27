"use client";

import React from "react";
import { cn } from "@/lib/utils";
import type { MemoryState } from "@/lib/api";
import { getStateInfo } from "@/lib/constants";

interface StateBadgeProps {
  state?: MemoryState;
  className?: string;
  size?: "sm" | "md";
}

export function StateBadge({ state = "active", className, size = "sm" }: StateBadgeProps) {
  const info = getStateInfo(state);
  if (!info) return null;

  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full font-medium",
        info.bgColor,
        info.textColor,
        size === "sm" ? "px-2 py-0.5 text-xs" : "px-2.5 py-1 text-sm",
        className
      )}
    >
      <span className={cn("h-1.5 w-1.5 rounded-full", info.dotColor)} />
      {info.label}
    </span>
  );
}
