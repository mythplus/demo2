import { type ClassValue, clsx } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

/**
 * 将 ISO 时间字符串或时间戳格式化为北京时间（UTC+8）
 * 输出格式：YYYY-MM-DD HH:mm:ss
 * @example formatDateTime("2026-04-17T06:10:19.184898+00:00") → "2026-04-17 14:10:19"
 * @example formatDateTime(1713340219184) → "2026-04-17 14:10:19"
 */
export function formatDateTime(input: string | number | undefined | null): string {
  if (input === undefined || input === null || input === "") return "";
  try {
    const date = new Date(input);
    if (isNaN(date.getTime())) return String(input);
    // 使用固定的 UTC+8 偏移，避免依赖浏览器本地时区
    const utc8 = new Date(date.getTime() + 8 * 60 * 60 * 1000);
    const y = utc8.getUTCFullYear();
    const M = String(utc8.getUTCMonth() + 1).padStart(2, "0");
    const d = String(utc8.getUTCDate()).padStart(2, "0");
    const h = String(utc8.getUTCHours()).padStart(2, "0");
    const m = String(utc8.getUTCMinutes()).padStart(2, "0");
    const s = String(utc8.getUTCSeconds()).padStart(2, "0");
    return `${y}-${M}-${d} ${h}:${m}:${s}`;
  } catch {
    return String(input);
  }
}

/**
 * 将 ISO 时间字符串或时间戳格式化为北京时间的短格式
 * 输出格式：MM/DD HH:mm（用于表格等紧凑场景）
 * @example formatShortDateTime("2026-04-17T06:10:19.184898+00:00") → "04/17 14:10"
 */
export function formatShortDateTime(input: string | number | undefined | null): string {
  if (input === undefined || input === null || input === "") return "";
  try {
    const date = new Date(input);
    if (isNaN(date.getTime())) return String(input);
    const utc8 = new Date(date.getTime() + 8 * 60 * 60 * 1000);
    const M = String(utc8.getUTCMonth() + 1).padStart(2, "0");
    const d = String(utc8.getUTCDate()).padStart(2, "0");
    const h = String(utc8.getUTCHours()).padStart(2, "0");
    const m = String(utc8.getUTCMinutes()).padStart(2, "0");
    return `${M}/${d} ${h}:${m}`;
  } catch {
    return String(input);
  }
}
