/**
 * 分类与状态常量定义
 */
import type { Category, MemoryState } from "@/lib/api/types";

// ============ 分类常量 ============

export interface CategoryInfo {
  value: Category;
  label: string;
  color: string; // Tailwind 颜色类
  bgColor: string;
  textColor: string;
}

export const CATEGORY_LIST: CategoryInfo[] = [
  // --- 原有 8 个 ---
  { value: "personal", label: "个人", color: "blue", bgColor: "bg-blue-50 dark:bg-blue-950/40", textColor: "text-blue-600 dark:text-blue-400" },
  { value: "relationships", label: "关系", color: "red", bgColor: "bg-red-50 dark:bg-red-950/40", textColor: "text-red-600 dark:text-red-400" },
  { value: "preferences", label: "偏好", color: "pink", bgColor: "bg-pink-50 dark:bg-pink-950/40", textColor: "text-pink-600 dark:text-pink-400" },
  { value: "health", label: "健康", color: "green", bgColor: "bg-green-50 dark:bg-green-950/40", textColor: "text-green-600 dark:text-green-400" },
  { value: "travel", label: "旅行", color: "cyan", bgColor: "bg-cyan-50 dark:bg-cyan-950/40", textColor: "text-cyan-600 dark:text-cyan-400" },
  { value: "work", label: "工作", color: "purple", bgColor: "bg-purple-50 dark:bg-purple-950/40", textColor: "text-purple-600 dark:text-purple-400" },
  { value: "education", label: "教育", color: "indigo", bgColor: "bg-indigo-50 dark:bg-indigo-950/40", textColor: "text-indigo-600 dark:text-indigo-400" },
  { value: "finance", label: "财务", color: "orange", bgColor: "bg-orange-50 dark:bg-orange-950/40", textColor: "text-orange-600 dark:text-orange-400" },
  // --- 新增 12 个 ---
  { value: "projects", label: "项目", color: "violet", bgColor: "bg-violet-50 dark:bg-violet-950/40", textColor: "text-violet-600 dark:text-violet-400" },
  { value: "ai_ml_technology", label: "AI/技术", color: "sky", bgColor: "bg-sky-50 dark:bg-sky-950/40", textColor: "text-sky-600 dark:text-sky-400" },
  { value: "technical_support", label: "技术支持", color: "amber", bgColor: "bg-amber-50 dark:bg-amber-950/40", textColor: "text-amber-600 dark:text-amber-400" },
  { value: "shopping", label: "购物", color: "fuchsia", bgColor: "bg-fuchsia-50 dark:bg-fuchsia-950/40", textColor: "text-fuchsia-600 dark:text-fuchsia-400" },
  { value: "legal", label: "法律", color: "slate", bgColor: "bg-slate-100 dark:bg-slate-800/40", textColor: "text-slate-600 dark:text-slate-400" },
  { value: "entertainment", label: "娱乐", color: "rose", bgColor: "bg-rose-50 dark:bg-rose-950/40", textColor: "text-rose-600 dark:text-rose-400" },
  { value: "messages", label: "消息", color: "teal", bgColor: "bg-teal-50 dark:bg-teal-950/40", textColor: "text-teal-600 dark:text-teal-400" },
  { value: "customer_support", label: "客户支持", color: "lime", bgColor: "bg-lime-50 dark:bg-lime-950/40", textColor: "text-lime-600 dark:text-lime-400" },
  { value: "product_feedback", label: "产品反馈", color: "yellow", bgColor: "bg-yellow-50 dark:bg-yellow-950/40", textColor: "text-yellow-600 dark:text-yellow-400" },
  { value: "news", label: "新闻", color: "emerald", bgColor: "bg-emerald-50 dark:bg-emerald-950/40", textColor: "text-emerald-600 dark:text-emerald-400" },
  { value: "organization", label: "组织", color: "stone", bgColor: "bg-stone-100 dark:bg-stone-800/40", textColor: "text-stone-600 dark:text-stone-400" },
  { value: "goals", label: "目标", color: "amber", bgColor: "bg-amber-50 dark:bg-amber-950/40", textColor: "text-amber-700 dark:text-amber-300" },
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
}

export const STATE_LIST: StateInfo[] = [
  { value: "active", label: "活跃", color: "green", dotColor: "bg-green-500", bgColor: "bg-green-100 dark:bg-green-900/30", textColor: "text-green-700 dark:text-green-300" },
  { value: "paused", label: "暂停", color: "yellow", dotColor: "bg-yellow-500", bgColor: "bg-yellow-100 dark:bg-yellow-900/30", textColor: "text-yellow-700 dark:text-yellow-300" },
  { value: "deleted", label: "已删除", color: "red", dotColor: "bg-red-500", bgColor: "bg-red-100 dark:bg-red-900/30", textColor: "text-red-700 dark:text-red-300" },
];

/** 状态映射（快速查找） */
export const STATE_MAP = new Map(STATE_LIST.map((s) => [s.value, s]));

/** 获取状态信息 */
export function getStateInfo(state: MemoryState): StateInfo | undefined {
  return STATE_MAP.get(state);
}
