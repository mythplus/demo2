"use client";

import React from "react";
import { Eye, Pencil, Trash2, MoreHorizontal } from "lucide-react";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { CategoryBadges } from "./category-badge";
import { StateBadge } from "./state-badge";
import type { Memory } from "@/lib/api";

interface MemoryTableProps {
  memories: Memory[];
  onView: (memory: Memory) => void;
  onEdit: (memory: Memory) => void;
  onDelete: (memory: Memory) => void;
}

export function MemoryTable({ memories, onView, onEdit, onDelete }: MemoryTableProps) {
  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead className="w-[40%]">记忆内容</TableHead>
          <TableHead className="w-[12%]">用户</TableHead>
          <TableHead className="w-[18%]">分类</TableHead>
          <TableHead className="w-[8%]">状态</TableHead>
          <TableHead className="w-[14%]">创建时间</TableHead>
          <TableHead className="w-[8%] text-right">操作</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {memories.map((memory) => (
          <TableRow
            key={memory.id}
            className="cursor-pointer"
            onClick={() => onView(memory)}
          >
            <TableCell>
              <p className="text-sm line-clamp-2 leading-relaxed">
                {memory.memory}
              </p>
            </TableCell>
            <TableCell>
              {memory.user_id && (
                <span className="text-xs text-muted-foreground">
                  {memory.user_id}
                </span>
              )}
            </TableCell>
            <TableCell>
              <CategoryBadges categories={memory.categories} max={2} />
            </TableCell>
            <TableCell>
              <StateBadge state={memory.state} />
            </TableCell>
            <TableCell>
              {memory.created_at && (
                <span className="text-xs text-muted-foreground">
                  {new Date(memory.created_at).toLocaleString("zh-CN", {
                    month: "2-digit",
                    day: "2-digit",
                    hour: "2-digit",
                    minute: "2-digit",
                  })}
                </span>
              )}
            </TableCell>
            <TableCell className="text-right">
              <DropdownMenu>
                <DropdownMenuTrigger asChild>
                  <Button
                    variant="ghost"
                    size="icon"
                    className="h-7 w-7"
                    onClick={(e) => e.stopPropagation()}
                  >
                    <MoreHorizontal className="h-4 w-4" />
                  </Button>
                </DropdownMenuTrigger>
                <DropdownMenuContent align="end">
                  <DropdownMenuItem onClick={(e) => { e.stopPropagation(); onView(memory); }}>
                    <Eye className="mr-2 h-4 w-4" />
                    查看详情
                  </DropdownMenuItem>
                  <DropdownMenuItem onClick={(e) => { e.stopPropagation(); onEdit(memory); }}>
                    <Pencil className="mr-2 h-4 w-4" />
                    编辑
                  </DropdownMenuItem>
                  <DropdownMenuSeparator />
                  <DropdownMenuItem
                    className="text-destructive focus:text-destructive"
                    onClick={(e) => { e.stopPropagation(); onDelete(memory); }}
                  >
                    <Trash2 className="mr-2 h-4 w-4" />
                    删除
                  </DropdownMenuItem>
                </DropdownMenuContent>
              </DropdownMenu>
            </TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
}
