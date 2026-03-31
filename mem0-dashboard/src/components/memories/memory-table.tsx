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
import { Badge } from "@/components/ui/badge";
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
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";

interface MemoryTableProps {
  memories: Memory[];
  onView: (memory: Memory) => void;
  onEdit: (memory: Memory) => void;
  onDelete: (memory: Memory) => void;
}

export function MemoryTable({ memories, onView, onEdit, onDelete }: MemoryTableProps) {
  return (
    <TooltipProvider>
      <div className="rounded-md border overflow-x-auto">
        <Table className="min-w-[800px]">
          <TableHeader>
            <TableRow className="bg-muted/40">
              <TableHead className="min-w-[280px] py-3 font-semibold text-xs uppercase tracking-wider">记忆内容</TableHead>
              <TableHead className="min-w-[70px] w-[80px] py-3 font-semibold text-xs uppercase tracking-wider">用户</TableHead>
              <TableHead className="min-w-[160px] w-[180px] py-3 font-semibold text-xs uppercase tracking-wider">分类</TableHead>
              <TableHead className="min-w-[70px] w-[80px] py-3 font-semibold text-xs uppercase tracking-wider">状态</TableHead>
              <TableHead className="min-w-[100px] w-[120px] py-3 font-semibold text-xs uppercase tracking-wider">创建时间</TableHead>
              <TableHead className="w-[50px] py-3 font-semibold text-xs uppercase tracking-wider text-right">操作</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {memories.map((memory) => (
              <TableRow
                key={memory.id}
                className="cursor-pointer hover:bg-accent/50 transition-colors"
                onClick={() => onView(memory)}
              >
                <TableCell className="py-3">
                  <Tooltip>
                    <TooltipTrigger asChild>
                      <p className="text-sm line-clamp-2 leading-relaxed break-words">
                        {memory.memory}
                      </p>
                    </TooltipTrigger>
                    <TooltipContent side="bottom" className="max-w-sm">
                      <p className="text-xs">{memory.memory}</p>
                    </TooltipContent>
                  </Tooltip>
                </TableCell>
                <TableCell className="py-3">
                  {memory.user_id && (
                    <Badge variant="secondary" className="text-xs font-normal">
                      {memory.user_id}
                    </Badge>
                  )}
                </TableCell>
                <TableCell className="py-3">
                  <CategoryBadges categories={memory.categories} max={2} nowrap />
                </TableCell>
                <TableCell className="py-3 whitespace-nowrap">
                  <StateBadge state={memory.state} />
                </TableCell>
                <TableCell className="py-3 whitespace-nowrap">
                  {memory.created_at && (
                    <Tooltip>
                      <TooltipTrigger asChild>
                        <span className="text-xs text-muted-foreground">
                          {new Date(memory.created_at).toLocaleString("zh-CN", {
                            month: "2-digit",
                            day: "2-digit",
                            hour: "2-digit",
                            minute: "2-digit",
                          })}
                        </span>
                      </TooltipTrigger>
                      <TooltipContent>
                        <p className="text-xs">{new Date(memory.created_at).toLocaleString("zh-CN")}</p>
                      </TooltipContent>
                    </Tooltip>
                  )}
                </TableCell>
                <TableCell className="py-3 text-right">
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
      </div>
    </TooltipProvider>
  );
}
