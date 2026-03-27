"use client";

import React from "react";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

interface PageSizeSelectorProps {
  value: number;
  onChange: (size: number) => void;
  options?: number[];
  className?: string;
}

export function PageSizeSelector({
  value,
  onChange,
  options = [5, 10, 20, 50],
  className,
}: PageSizeSelectorProps) {
  return (
    <div className={className}>
      <Select
        value={String(value)}
        onValueChange={(v) => onChange(parseInt(v))}
      >
        <SelectTrigger className="h-8 w-[100px]">
          <SelectValue />
        </SelectTrigger>
        <SelectContent>
          {options.map((size) => (
            <SelectItem key={size} value={String(size)}>
              {size} 条/页
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
    </div>
  );
}
