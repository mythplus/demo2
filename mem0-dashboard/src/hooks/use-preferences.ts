"use client";

import { useState, useEffect, useCallback } from "react";

/** 用户偏好设置 */
export interface UserPreferences {
  /** 每页显示条数 */
  pageSize: number;
  /** 默认排序方式 */
  sortOrder: "newest" | "oldest";
  /** 主题模式 */
  themeMode: "light" | "dark" | "system";
  /** API 地址 */
  apiUrl: string;
}

const DEFAULT_PREFERENCES: UserPreferences = {
  pageSize: 10,
  sortOrder: "newest",
  themeMode: "system",
  apiUrl: "http://localhost:8080",
};

const STORAGE_KEY = "mem0-preferences";

/**
 * 全局用户偏好设置 Hook
 * 使用 localStorage 持久化
 */
export function usePreferences() {
  const [preferences, setPreferences] =
    useState<UserPreferences>(DEFAULT_PREFERENCES);
  const [loaded, setLoaded] = useState(false);

  // 从 localStorage 加载
  useEffect(() => {
    try {
      const saved = localStorage.getItem(STORAGE_KEY);
      if (saved) {
        const parsed = JSON.parse(saved);
        setPreferences({ ...DEFAULT_PREFERENCES, ...parsed });
      }
      // 也读取环境变量中的 API 地址
      const envUrl = process.env.NEXT_PUBLIC_MEM0_API_URL;
      if (envUrl && !saved) {
        setPreferences((prev) => ({ ...prev, apiUrl: envUrl }));
      }
    } catch {
      // 忽略解析错误
    }
    setLoaded(true);
  }, []);

  // 保存到 localStorage
  const savePreferences = useCallback(
    (newPrefs: Partial<UserPreferences>) => {
      setPreferences((prev) => {
        const updated = { ...prev, ...newPrefs };
        localStorage.setItem(STORAGE_KEY, JSON.stringify(updated));
        return updated;
      });
    },
    []
  );

  // 重置为默认值
  const resetPreferences = useCallback(() => {
    setPreferences(DEFAULT_PREFERENCES);
    localStorage.removeItem(STORAGE_KEY);
  }, []);

  return {
    preferences,
    loaded,
    savePreferences,
    resetPreferences,
  };
}
