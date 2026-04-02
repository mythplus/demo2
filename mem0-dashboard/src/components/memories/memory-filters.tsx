"use client";

import React, { useState, useRef, useEffect } from "react";
import { Filter, X, CalendarDays, Check, Search, ChevronDown } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import type { Category, MemoryState, FilterParams } from "@/lib/api";
import { CATEGORY_LIST, STATE_LIST, getCategoryInfo } from "@/lib/constants";

interface MemoryFiltersProps {
  filters: FilterParams;
  onFiltersChange: (filters: FilterParams) => void;
  users?: string[];
  className?: string;
  prefix?: React.ReactNode;
}

export function MemoryFilters({
  filters,
  onFiltersChange,
  users = [],
  className,
  prefix,
}: MemoryFiltersProps) {
  const [expanded, setExpanded] = useState(false);

  const updateFilter = (key: keyof FilterParams, value: unknown) => {
    onFiltersChange({ ...filters, [key]: value || undefined });
  };

  const clearFilters = () => {
    onFiltersChange({});
  };

  const hasActiveFilters =
    (filters.categories && filters.categories.length > 0) ||
    filters.state ||
    filters.user_id ||
    filters.date_from ||
    filters.date_to;

  const toggleCategory = (cat: Category) => {
    const current = filters.categories || [];
    const updated = current.includes(cat)
      ? current.filter((c) => c !== cat)
      : [...current, cat];
    updateFilter("categories", updated.length > 0 ? updated : undefined);
  };

  return (
    <div className={cn("space-y-3", className)}>
      {/* 主筛选行 */}
      <div className="flex flex-wrap items-center gap-2">
        {/* 前置插槽（如视图切换按钮） */}
        {prefix}

        {/* 展开/折叠高级筛选 */}
        <Button
          variant={expanded ? "default" : "outline"}
          size="sm"
          onClick={() => setExpanded(!expanded)}
          className="gap-1.5 h-8"
        >
          <Filter className="h-3.5 w-3.5" />
          筛选
          {hasActiveFilters && (
            <Badge variant="secondary" className="ml-1 h-5 w-5 rounded-full p-0 flex items-center justify-center text-xs">
              {(filters.categories?.length || 0) + (filters.state ? 1 : 0) + (filters.user_id ? 1 : 0) + (filters.date_from ? 1 : 0)}
            </Badge>
          )}
        </Button>

        {/* 状态快速筛选 */}
        <Select
          value={filters.state || "all"}
          onValueChange={(v) => updateFilter("state", v === "all" ? undefined : v)}
        >
          <SelectTrigger className="h-8 w-[120px]">
            <SelectValue placeholder="全部状态" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">全部状态</SelectItem>
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

        {/* 用户筛选（带搜索） */}
        <UserFilterDropdown
          value={filters.user_id}
          users={users}
          onChange={(v) => updateFilter("user_id", v)}
        />

        {/* 清除筛选 */}
        {hasActiveFilters && (
          <Button variant="outline" size="sm" onClick={clearFilters} className="gap-1 h-8 border-red-300 text-red-600 hover:bg-red-50 hover:text-red-700 hover:border-red-400 dark:border-red-800 dark:text-red-400 dark:hover:bg-red-900/30 dark:hover:text-red-300 dark:hover:border-red-700">
            <X className="h-3.5 w-3.5" />
            清除
          </Button>
        )}
      </div>

      {/* 展开的高级筛选区域 */}
      {expanded && (
        <div className="space-y-3 rounded-lg border p-3 bg-muted/30">
          {/* 分类筛选 */}
          <div className="space-y-1.5">
            <label className="text-xs font-medium text-muted-foreground">分类筛选</label>
            <div className="flex flex-wrap gap-1.5">
              {CATEGORY_LIST.map((cat) => {
                const isSelected = filters.categories?.includes(cat.value);
                return (
                  <button
                    key={cat.value}
                    onClick={() => toggleCategory(cat.value)}
                    className={cn(
                      "inline-flex items-center gap-1 rounded-full px-2.5 py-1 text-xs font-medium transition-all cursor-pointer border",
                      isSelected
                        ? "bg-primary text-primary-foreground border-primary shadow-sm"
                        : "bg-muted text-muted-foreground border-transparent hover:bg-muted/80"
                    )}
                  >
                    {isSelected && <Check className="h-3 w-3" />}
                    {cat.label}
                  </button>
                );
              })}
            </div>
          </div>

          {/* 时间范围 */}
          <div className="space-y-1.5">
            <label className="text-xs font-medium text-muted-foreground flex items-center gap-1">
              <CalendarDays className="h-3.5 w-3.5" />
              时间范围
            </label>
            <div className="flex items-center gap-2">
              <Input
                type="date"
                value={filters.date_from || ""}
                max={filters.date_to || undefined}
                onChange={(e) => {
                  const newFrom = e.target.value || undefined;
                  // 如果新的开始日期晚于结束日期，自动清空结束日期
                  if (newFrom && filters.date_to && newFrom > filters.date_to) {
                    onFiltersChange({ ...filters, date_from: newFrom, date_to: undefined });
                  } else {
                    updateFilter("date_from", newFrom);
                  }
                }}
                className="h-8 w-[160px]"
                placeholder="开始日期"
              />
              <span className="text-xs text-muted-foreground">至</span>
              <Input
                type="date"
                value={filters.date_to || ""}
                min={filters.date_from || undefined}
                onChange={(e) => {
                  const newTo = e.target.value || undefined;
                  // 如果新的结束日期早于开始日期，自动清空开始日期
                  if (newTo && filters.date_from && newTo < filters.date_from) {
                    onFiltersChange({ ...filters, date_to: newTo, date_from: undefined });
                  } else {
                    updateFilter("date_to", newTo);
                  }
                }}
                className="h-8 w-[160px]"
                placeholder="结束日期"
              />

              {/* 快捷日期范围按钮 */}
              {[
                { label: "今天", days: 0 },
                { label: "近7天", days: 7 },
                { label: "近30天", days: 30 },
              ].map(({ label, days }) => {
                const today = new Date();
                const todayStr = today.toISOString().split("T")[0];
                const fromDate = new Date(today);
                fromDate.setDate(today.getDate() - days);
                const fromStr = fromDate.toISOString().split("T")[0];
                const isActive = filters.date_from === fromStr && filters.date_to === todayStr;
                return (
                  <button
                    key={label}
                    onClick={() => {
                      if (isActive) {
                        // 再次点击取消选择
                        onFiltersChange({ ...filters, date_from: undefined, date_to: undefined });
                      } else {
                        onFiltersChange({ ...filters, date_from: fromStr, date_to: todayStr });
                      }
                    }}
                    className={cn(
                      "inline-flex items-center rounded-md px-2.5 py-1 text-xs font-medium transition-all cursor-pointer border whitespace-nowrap",
                      isActive
                        ? "bg-primary text-primary-foreground border-primary shadow-sm"
                        : "bg-background text-foreground border-input hover:bg-accent hover:text-accent-foreground"
                    )}
                  >
                    {label}
                  </button>
                );
              })}
            </div>
          </div>

          {/* 已选筛选条件摘要 */}
          {hasActiveFilters && (
            <div className="flex flex-wrap gap-1.5 pt-1 border-t">
              {filters.categories?.map((cat) => {
                const info = getCategoryInfo(cat);
                return (
                  <Badge
                    key={cat}
                    variant="secondary"
                    className="gap-1 cursor-pointer"
                    onClick={() => toggleCategory(cat)}
                  >
                    {info?.label || cat}
                    <X className="h-3 w-3" />
                  </Badge>
                );
              })}
              {filters.state && (
                <Badge variant="secondary" className="gap-1 cursor-pointer" onClick={() => updateFilter("state", undefined)}>
                  状态: {STATE_LIST.find(s => s.value === filters.state)?.label}
                  <X className="h-3 w-3" />
                </Badge>
              )}
              {filters.user_id && (
                <Badge variant="secondary" className="gap-1 cursor-pointer" onClick={() => updateFilter("user_id", undefined)}>
                  用户: {filters.user_id}
                  <X className="h-3 w-3" />
                </Badge>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

/** 带搜索的用户筛选下拉 */
function UserFilterDropdown({
  value,
  users,
  onChange,
}: {
  value?: string;
  users: string[];
  onChange: (v: string | undefined) => void;
}) {
  const [open, setOpen] = useState(false);
  const [search, setSearch] = useState("");
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const handleClick = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", handleClick);
    return () => document.removeEventListener("mousedown", handleClick);
  }, []);

  const filtered = search
    ? users.filter((u) => u.toLowerCase().includes(search.toLowerCase()))
    : users;

  return (
    <div className="relative ml-2" ref={ref}>
      <button
        type="button"
        onClick={() => setOpen(!open)}
        className={cn(
          "flex h-8 w-[160px] items-center justify-between rounded-md border border-input bg-background px-3 text-sm",
          "hover:bg-accent/50 transition-colors"
        )}
      >
        <span className="text-foreground">
          {value || "全部用户"}
        </span>
        <ChevronDown className={cn("h-3.5 w-3.5 text-muted-foreground transition-transform", open && "rotate-180")} />
      </button>
      {open && (
        <div className="absolute left-0 z-50 mt-1 w-[220px] rounded-md border bg-popover text-popover-foreground shadow-lg animate-in fade-in-0 zoom-in-95 overflow-hidden">
          <div className="flex items-center border-b px-2 py-1.5">
            <Search className="mr-1.5 h-3.5 w-3.5 shrink-0 text-muted-foreground" />
            <input
              type="text"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="搜索用户..."
              className="flex-1 bg-transparent text-sm outline-none placeholder:text-muted-foreground"
              autoFocus
            />
          </div>
          <div className="max-h-48 overflow-y-auto p-1">
            <div
              onClick={() => { onChange(undefined); setOpen(false); setSearch(""); }}
              className={cn(
                "flex cursor-pointer items-center rounded-sm px-2 py-1.5 text-sm hover:bg-accent",
                !value && "bg-accent"
              )}
            >
              {!value && <Check className="mr-2 h-3.5 w-3.5" />}
              <span className={!value ? "" : "pl-5"}>全部用户</span>
            </div>
            {filtered.map((u) => (
              <div
                key={u}
                onClick={() => { onChange(u); setOpen(false); setSearch(""); }}
                className={cn(
                  "flex cursor-pointer items-center rounded-sm px-2 py-1.5 text-sm hover:bg-accent",
                  value === u && "bg-accent"
                )}
              >
                {value === u && <Check className="mr-2 h-3.5 w-3.5" />}
                <span className={value === u ? "" : "pl-5"}>{u}</span>
              </div>
            ))}
            {filtered.length === 0 && (
              <p className="px-2 py-3 text-center text-xs text-muted-foreground">未找到用户</p>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
