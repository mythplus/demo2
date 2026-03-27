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
  { value: "personal", label: "个人", color: "blue", bgColor: "bg-blue-100 dark:bg-blue-900/30", textColor: "text-blue-700 dark:text-blue-300" },
  { value: "relationships", label: "关系", color: "red", bgColor: "bg-red-100 dark:bg-red-900/30", textColor: "text-red-700 dark:text-red-300" },
  { value: "preferences", label: "偏好", color: "pink", bgColor: "bg-pink-100 dark:bg-pink-900/30", textColor: "text-pink-700 dark:text-pink-300" },
  { value: "health", label: "健康", color: "green", bgColor: "bg-green-100 dark:bg-green-900/30", textColor: "text-green-700 dark:text-green-300" },
  { value: "travel", label: "旅行", color: "cyan", bgColor: "bg-cyan-100 dark:bg-cyan-900/30", textColor: "text-cyan-700 dark:text-cyan-300" },
  { value: "work", label: "工作", color: "purple", bgColor: "bg-purple-100 dark:bg-purple-900/30", textColor: "text-purple-700 dark:text-purple-300" },
  { value: "education", label: "教育", color: "indigo", bgColor: "bg-indigo-100 dark:bg-indigo-900/30", textColor: "text-indigo-700 dark:text-indigo-300" },
  { value: "finance", label: "财务", color: "orange", bgColor: "bg-orange-100 dark:bg-orange-900/30", textColor: "text-orange-700 dark:text-orange-300" },
  // --- 新增 12 个 ---
  { value: "projects", label: "项目", color: "violet", bgColor: "bg-violet-100 dark:bg-violet-900/30", textColor: "text-violet-700 dark:text-violet-300" },
  { value: "ai_ml_technology", label: "AI/技术", color: "sky", bgColor: "bg-sky-100 dark:bg-sky-900/30", textColor: "text-sky-700 dark:text-sky-300" },
  { value: "technical_support", label: "技术支持", color: "amber", bgColor: "bg-amber-100 dark:bg-amber-900/30", textColor: "text-amber-700 dark:text-amber-300" },
  { value: "shopping", label: "购物", color: "fuchsia", bgColor: "bg-fuchsia-100 dark:bg-fuchsia-900/30", textColor: "text-fuchsia-700 dark:text-fuchsia-300" },
  { value: "legal", label: "法律", color: "slate", bgColor: "bg-slate-200 dark:bg-slate-700/30", textColor: "text-slate-700 dark:text-slate-300" },
  { value: "entertainment", label: "娱乐", color: "rose", bgColor: "bg-rose-100 dark:bg-rose-900/30", textColor: "text-rose-700 dark:text-rose-300" },
  { value: "messages", label: "消息", color: "teal", bgColor: "bg-teal-100 dark:bg-teal-900/30", textColor: "text-teal-700 dark:text-teal-300" },
  { value: "customer_support", label: "客户支持", color: "lime", bgColor: "bg-lime-100 dark:bg-lime-900/30", textColor: "text-lime-700 dark:text-lime-300" },
  { value: "product_feedback", label: "产品反馈", color: "yellow", bgColor: "bg-yellow-100 dark:bg-yellow-900/30", textColor: "text-yellow-700 dark:text-yellow-300" },
  { value: "news", label: "新闻", color: "emerald", bgColor: "bg-emerald-100 dark:bg-emerald-900/30", textColor: "text-emerald-700 dark:text-emerald-300" },
  { value: "organization", label: "组织", color: "stone", bgColor: "bg-stone-200 dark:bg-stone-700/30", textColor: "text-stone-700 dark:text-stone-300" },
  { value: "goals", label: "目标", color: "red", bgColor: "bg-red-50 dark:bg-red-900/20", textColor: "text-red-600 dark:text-red-400" },
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
