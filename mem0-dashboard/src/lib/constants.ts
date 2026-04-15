/**
 * 分类与状态常量定义
 */
import type { Category, MemoryState } from "@/lib/api/types";

// ============ 分类常量 ============

export interface CategoryInfo {
  value: Category;
  label: string;
  color: string;       // 主色调 hex
  lightBg: string;     // 浅色模式背景色
  lightText: string;   // 浅色模式文字色
  darkBg: string;      // 深色模式背景色
  darkText: string;    // 深色模式文字色
}

export const CATEGORY_LIST: CategoryInfo[] = [
  // --- 原有 8 个 ---
  { value: "personal",    label: "个人",     color: "#3b82f6", lightBg: "#eff6ff", lightText: "#2563eb", darkBg: "rgba(59,130,246,0.15)",  darkText: "#60a5fa" },
  { value: "relationships", label: "关系",   color: "#ef4444", lightBg: "#fef2f2", lightText: "#dc2626", darkBg: "rgba(239,68,68,0.15)",   darkText: "#f87171" },
  { value: "preferences", label: "偏好",     color: "#ec4899", lightBg: "#fdf2f8", lightText: "#db2777", darkBg: "rgba(236,72,153,0.15)",  darkText: "#f472b6" },
  { value: "health",      label: "健康",     color: "#22c55e", lightBg: "#f0fdf4", lightText: "#16a34a", darkBg: "rgba(34,197,94,0.15)",   darkText: "#4ade80" },
  { value: "travel",      label: "旅行",     color: "#06b6d4", lightBg: "#ecfeff", lightText: "#0891b2", darkBg: "rgba(6,182,212,0.15)",   darkText: "#22d3ee" },
  { value: "work",        label: "工作",     color: "#a855f7", lightBg: "#faf5ff", lightText: "#9333ea", darkBg: "rgba(168,85,247,0.15)",  darkText: "#c084fc" },
  { value: "education",   label: "教育",     color: "#6366f1", lightBg: "#eef2ff", lightText: "#4f46e5", darkBg: "rgba(99,102,241,0.15)",  darkText: "#818cf8" },
  { value: "finance",     label: "财务",     color: "#f97316", lightBg: "#fff7ed", lightText: "#ea580c", darkBg: "rgba(249,115,22,0.15)",  darkText: "#fb923c" },
  // --- 新增 12 个 ---
  { value: "projects",    label: "项目",     color: "#8b5cf6", lightBg: "#f5f3ff", lightText: "#7c3aed", darkBg: "rgba(139,92,246,0.15)",  darkText: "#a78bfa" },
  { value: "ai_ml_technology", label: "AI/技术", color: "#0ea5e9", lightBg: "#f0f9ff", lightText: "#0284c7", darkBg: "rgba(14,165,233,0.15)", darkText: "#38bdf8" },
  { value: "technical_support", label: "技术支持", color: "#f59e0b", lightBg: "#fffbeb", lightText: "#d97706", darkBg: "rgba(245,158,11,0.15)", darkText: "#fbbf24" },
  { value: "shopping",    label: "购物",     color: "#d946ef", lightBg: "#fdf4ff", lightText: "#c026d3", darkBg: "rgba(217,70,239,0.15)",  darkText: "#e879f9" },
  { value: "legal",       label: "法律",     color: "#64748b", lightBg: "#f8fafc", lightText: "#475569", darkBg: "rgba(100,116,139,0.15)", darkText: "#94a3b8" },
  { value: "entertainment", label: "娱乐",   color: "#f43f5e", lightBg: "#fff1f2", lightText: "#e11d48", darkBg: "rgba(244,63,94,0.15)",   darkText: "#fb7185" },
  { value: "messages",    label: "消息",     color: "#14b8a6", lightBg: "#f0fdfa", lightText: "#0d9488", darkBg: "rgba(20,184,166,0.15)",  darkText: "#2dd4bf" },
  { value: "customer_support", label: "客户支持", color: "#84cc16", lightBg: "#f7fee7", lightText: "#65a30d", darkBg: "rgba(132,204,22,0.15)", darkText: "#a3e635" },
  { value: "product_feedback", label: "产品反馈", color: "#eab308", lightBg: "#fefce8", lightText: "#ca8a04", darkBg: "rgba(234,179,8,0.15)",   darkText: "#facc15" },
  { value: "news",        label: "新闻",     color: "#10b981", lightBg: "#ecfdf5", lightText: "#059669", darkBg: "rgba(16,185,129,0.15)",  darkText: "#34d399" },
  { value: "organization", label: "组织",    color: "#78716c", lightBg: "#fafaf9", lightText: "#57534e", darkBg: "rgba(120,113,108,0.15)", darkText: "#a8a29e" },
  { value: "goals",       label: "目标",     color: "#f59e0b", lightBg: "#fffbeb", lightText: "#b45309", darkBg: "rgba(245,158,11,0.15)",  darkText: "#fcd34d" },
];

/** 分类颜色映射（快速查找） */
export const CATEGORY_MAP = new Map(CATEGORY_LIST.map((c) => [c.value, c]));

/** 获取分类信息 */
export function getCategoryInfo(category: Category): CategoryInfo | undefined {
  return CATEGORY_MAP.get(category);
}

// ============ 状态常量 ============

export interface StateInfo {
  value: MemoryState;
  label: string;
  color: string;
  dotColor: string;
  bgColor: string;
  textColor: string;
  borderColor: string;
}

export const STATE_LIST: StateInfo[] = [
  { value: "active", label: "活跃", color: "green", dotColor: "bg-green-500", bgColor: "bg-green-100 dark:bg-green-900/30", textColor: "text-green-700 dark:text-green-300", borderColor: "border-green-200 dark:border-green-700/40" },
  { value: "paused", label: "暂停", color: "yellow", dotColor: "bg-yellow-500", bgColor: "bg-yellow-100 dark:bg-yellow-900/30", textColor: "text-yellow-700 dark:text-yellow-300", borderColor: "border-yellow-200 dark:border-yellow-700/40" },
  { value: "archived", label: "已归档", color: "blue", dotColor: "bg-blue-500", bgColor: "bg-blue-100 dark:bg-blue-900/30", textColor: "text-blue-700 dark:text-blue-300", borderColor: "border-blue-200 dark:border-blue-700/40" },
];

/** 状态映射（快速查找） */
export const STATE_MAP = new Map(STATE_LIST.map((s) => [s.value, s]));

/** 获取状态信息 */
export function getStateInfo(state: MemoryState): StateInfo | undefined {
  return STATE_MAP.get(state);
}
