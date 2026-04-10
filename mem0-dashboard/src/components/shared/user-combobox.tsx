"use client";

import React, { useState, useEffect, useRef } from "react";
import { Search, ChevronDown, Check } from "lucide-react";

interface UserComboboxProps {
  /** 当前选中的用户 ID（空字符串=未选择） */
  value: string;
  /** 用户列表 */
  users: string[];
  /** 选择回调 */
  onChange: (userId: string) => void;
  /** 占位文本 */
  placeholder?: string;
  /** 宽度 class */
  className?: string;
  /** 是否显示"全部用户"选项 */
  showAll?: boolean;
}

/**
 * 统一的用户选择下拉框（带搜索）
 * 替代各页面的自定义实现，保持一致的交互体验
 */
export function UserCombobox({
  value,
  users,
  onChange,
  placeholder = "选择用户",
  className = "w-[200px]",
  showAll = false,
}: UserComboboxProps) {
  const [open, setOpen] = useState(false);
  const [search, setSearch] = useState("");
  const ref = useRef<HTMLDivElement>(null);

  // 点击外部关闭
  useEffect(() => {
    const handle = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        setOpen(false);
      }
    };
    document.addEventListener("mousedown", handle);
    return () => document.removeEventListener("mousedown", handle);
  }, []);

  const filtered = search
    ? users.filter((u) => u.toLowerCase().includes(search.toLowerCase()))
    : users;

  return (
    <div className={`relative ${className}`} ref={ref}>
      <button
        type="button"
        onClick={() => setOpen(!open)}
        className="flex h-8 w-full items-center justify-between rounded-md border border-input bg-background px-3 text-sm hover:bg-accent/50 transition-colors"
      >
        <span className={value ? "text-foreground truncate" : "text-muted-foreground"}>
          {value || placeholder}
        </span>
        <ChevronDown
          className={`h-4 w-4 shrink-0 text-muted-foreground transition-transform ${open ? "rotate-180" : ""}`}
        />
      </button>
      {open && (
        <div className="absolute z-50 mt-1 w-full rounded-md border bg-popover text-popover-foreground shadow-lg animate-in fade-in-0 zoom-in-95">
          {/* 搜索框 */}
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
          {/* 选项列表 */}
          <div className="max-h-48 overflow-y-auto p-1">
            {showAll && (
              <div
                onClick={() => {
                  onChange("");
                  setOpen(false);
                  setSearch("");
                }}
                className={`flex cursor-pointer items-center rounded-sm px-2 py-1.5 text-sm hover:bg-accent ${
                  !value ? "bg-accent" : ""
                }`}
              >
                {!value && <Check className="mr-2 h-3.5 w-3.5" />}
                <span className={!value ? "" : "pl-5"}>全部用户</span>
              </div>
            )}
            {filtered.map((u) => (
              <div
                key={u}
                onClick={() => {
                  onChange(u);
                  setOpen(false);
                  setSearch("");
                }}
                className={`flex cursor-pointer items-center rounded-sm px-2 py-1.5 text-sm hover:bg-accent ${
                  value === u ? "bg-accent" : ""
                }`}
              >
                {value === u && <Check className="mr-2 h-3.5 w-3.5" />}
                <span className={value === u ? "" : "pl-5"}>{u}</span>
              </div>
            ))}
            {filtered.length === 0 && (
              <p className="px-2 py-3 text-center text-xs text-muted-foreground">
                未找到用户
              </p>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
