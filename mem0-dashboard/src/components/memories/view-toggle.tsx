"use client";

import React from "react";
import { List, LayoutGrid } from "lucide-react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

export type ViewMode = "list" | "table";

interface ViewToggleProps {
  mode: ViewMode;
  onChange: (mode: ViewMode) => void;
  className?: string;
}

export function ViewToggle({ mode, onChange, className }: ViewToggleProps) {
  return (
    <div className={cn("flex items-center rounded-lg border p-0.5 shrink-0", className)}>
      <Button
        variant={mode === "table" ? "default" : "ghost"}
        size="icon"
        className="h-[26px] w-[26px]"
        onClick={() => onChange("table")}
        title="表格视图"
      >
        <LayoutGrid className="h-4 w-4" />
      </Button>
      <Button
        variant={mode === "list" ? "default" : "ghost"}
        size="icon"
        className="h-[26px] w-[26px]"
        onClick={() => onChange("list")}
        title="列表视图"
      >
        <List className="h-4 w-4" />
      </Button>
    </div>
  );
}
