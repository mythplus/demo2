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
  { value: "personal", label: "个人", color: "blue", bgColor: "bg-blue-100 dark:bg-blue-900/30", textColor: "text-blue-700 dark:text-blue-300" },
  { value: "work", label: "工作", color: "purple", bgColor: "bg-purple-100 dark:bg-purple-900/30", textColor: "text-purple-700 dark:text-purple-300" },
  { value: "health", label: "健康", color: "green", bgColor: "bg-green-100 dark:bg-green-900/30", textColor: "text-green-700 dark:text-green-300" },
  { value: "finance", label: "财务", color: "orange", bgColor: "bg-orange-100 dark:bg-orange-900/30", textColor: "text-orange-700 dark:text-orange-300" },
  { value: "travel", label: "旅行", color: "cyan", bgColor: "bg-cyan-100 dark:bg-cyan-900/30", textColor: "text-cyan-700 dark:text-cyan-300" },
  { value: "education", label: "教育", color: "indigo", bgColor: "bg-indigo-100 dark:bg-indigo-900/30", textColor: "text-indigo-700 dark:text-indigo-300" },
  { value: "preferences", label: "偏好", color: "pink", bgColor: "bg-pink-100 dark:bg-pink-900/30", textColor: "text-pink-700 dark:text-pink-300" },
  { value: "relationships", label: "关系", color: "red", bgColor: "bg-red-100 dark:bg-red-900/30", textColor: "text-red-700 dark:text-red-300" },
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
  { value: "archived", label: "归档", color: "gray", dotColor: "bg-gray-400", bgColor: "bg-gray-100 dark:bg-gray-800/30", textColor: "text-gray-600 dark:text-gray-400" },
  { value: "deleted", label: "已删除", color: "red", dotColor: "bg-red-500", bgColor: "bg-red-100 dark:bg-red-900/30", textColor: "text-red-700 dark:text-red-300" },
];

/** 状态映射（快速查找） */
export const STATE_MAP = new Map(STATE_LIST.map((s) => [s.value, s]));

/** 获取状态信息 */
export function getStateInfo(state: MemoryState): StateInfo | undefined {
  return STATE_MAP.get(state);
}
