/**
 * 数据导入/导出工具
 */
import type { Memory } from "@/lib/api";

// ============ 导出功能 ============

/**
 * 将记忆数据导出为 JSON 文件
 */
export function exportToJSON(memories: Memory[], filename?: string) {
  const exportData = {
    version: "1.1",
    exported_at: new Date().toISOString(),
    total_count: memories.length,
    memories: memories.map((m) => ({
      id: m.id,
      memory: m.memory,
      user_id: m.user_id || null,
      agent_id: m.agent_id || null,
      metadata: m.metadata || {},
      categories: m.categories || [],
      state: m.state || "active",
      created_at: m.created_at || null,
      updated_at: m.updated_at || null,
    })),
  };

  const blob = new Blob([JSON.stringify(exportData, null, 2)], {
    type: "application/json",
  });
  downloadBlob(blob, filename || `mem0-export-${formatDate()}.json`);
}

/**
 * 将记忆数据导出为 CSV 文件
 */
export function exportToCSV(memories: Memory[], filename?: string) {
  const headers = [
    "ID",
    "记忆内容",
    "用户ID",
    "AgentID",
    "分类",
    "状态",
    "创建时间",
    "更新时间",
  ];

  const rows = memories.map((m) => [
    m.id,
    // CSV 中双引号需要转义
    `"${(m.memory || "").replace(/"/g, '""')}"`,
    m.user_id || "",
    m.agent_id || "",
    (m.categories || []).join(";"),
    m.state || "active",
    m.created_at || "",
    m.updated_at || "",
  ]);

  const csvContent = [
    // BOM 头，确保 Excel 正确识别 UTF-8
    "\uFEFF",
    headers.join(","),
    ...rows.map((row) => row.join(",")),
  ].join("\n");

  const blob = new Blob([csvContent], { type: "text/csv;charset=utf-8;" });
  downloadBlob(blob, filename || `mem0-export-${formatDate()}.csv`);
}

// ============ 导入功能 ============

/** 导入结果 */
export interface ImportResult {
  success: number;
  failed: number;
  errors: string[];
}

/** 导入数据项 */
export interface ImportItem {
  content: string;
  user_id?: string;
  metadata?: Record<string, unknown>;
}

/**
 * 解析 JSON 导入文件
 * 支持两种格式：
 * 1. 标准导出格式 { memories: [...] }
 * 2. 简单数组格式 [{ content: "...", user_id: "..." }]
 */
export function parseImportJSON(text: string): ImportItem[] {
  const data = JSON.parse(text);

  // 格式 1：标准导出格式
  if (data.memories && Array.isArray(data.memories)) {
    return data.memories.map((m: Record<string, unknown>) => ({
      content: (m.memory as string) || (m.content as string) || "",
      user_id: (m.user_id as string) || undefined,
      metadata: (m.metadata as Record<string, unknown>) || undefined,
    }));
  }

  // 格式 2：简单数组
  if (Array.isArray(data)) {
    return data.map((item: Record<string, unknown>) => {
      if (typeof item === "string") {
        return { content: item };
      }
      return {
        content: (item.memory as string) || (item.content as string) || (item.text as string) || "",
        user_id: (item.user_id as string) || undefined,
        metadata: (item.metadata as Record<string, unknown>) || undefined,
      };
    });
  }

  throw new Error("不支持的 JSON 格式，请使用标准导出格式或数组格式");
}

/**
 * 验证导入数据
 */
export function validateImportItems(items: ImportItem[]): {
  valid: ImportItem[];
  errors: string[];
} {
  const valid: ImportItem[] = [];
  const errors: string[] = [];

  items.forEach((item, index) => {
    if (!item.content || !item.content.trim()) {
      errors.push(`第 ${index + 1} 条：内容为空，已跳过`);
    } else {
      valid.push(item);
    }
  });

  return { valid, errors };
}

// ============ 工具函数 ============

function downloadBlob(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  URL.revokeObjectURL(url);
}

function formatDate(): string {
  const now = new Date();
  return `${now.getFullYear()}${String(now.getMonth() + 1).padStart(2, "0")}${String(now.getDate()).padStart(2, "0")}_${String(now.getHours()).padStart(2, "0")}${String(now.getMinutes()).padStart(2, "0")}`;
}
