"use client";

import { useState, useEffect, useCallback } from "react";

/** 用户偏好设置 */
export interface UserPreferences {
  /** 每页显示条数 */
  pageSize: number;
  /** 默认排序方式 */
  sortOrder: "newest" | "oldest";
  /** 主题模式 */
  themeMode: "light" | "dark";
  /** API 地址 */
  apiUrl: string;
}

const DEFAULT_PREFERENCES: UserPreferences = {
  pageSize: 10,
  sortOrder: "newest",
  themeMode: "light",
  apiUrl: "http://localhost:8080",
};

const STORAGE_KEY = "mem0-preferences";

/** 自定义事件名，用于同一页面内跨组件同步 */
const SYNC_EVENT = "mem0-preferences-sync";

/**
 * 全局用户偏好设置 Hook
 * 使用 localStorage 持久化，支持跨组件实时同步
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
        // 兼容旧数据：如果存储的是 "system"，自动迁移为 "light"
        if (parsed.themeMode === "system") {
          parsed.themeMode = "light";
        }
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

  // 监听同页面内其他组件的偏好变更（自定义事件）
  useEffect(() => {
    const handleSync = () => {
      try {
        const saved = localStorage.getItem(STORAGE_KEY);
        if (saved) {
          const parsed = JSON.parse(saved);
          if (parsed.themeMode === "system") {
            parsed.themeMode = "light";
          }
          setPreferences({ ...DEFAULT_PREFERENCES, ...parsed });
        }
      } catch {
        // 忽略
      }
    };

    // 监听自定义同步事件（同一标签页内跨组件）
    window.addEventListener(SYNC_EVENT, handleSync);
    // 监听 storage 事件（跨标签页同步）
    window.addEventListener("storage", (e) => {
      if (e.key === STORAGE_KEY) handleSync();
    });

    return () => {
      window.removeEventListener(SYNC_EVENT, handleSync);
      window.removeEventListener("storage", handleSync);
    };
  }, []);

  // 保存到 localStorage 并通知其他组件
  const savePreferences = useCallback(
    (newPrefs: Partial<UserPreferences>) => {
      setPreferences((prev) => {
        const updated = { ...prev, ...newPrefs };
        localStorage.setItem(STORAGE_KEY, JSON.stringify(updated));
        // 派发自定义事件，通知同页面内其他使用此 hook 的组件
        window.dispatchEvent(new Event(SYNC_EVENT));
        return updated;
      });
    },
    []
  );

  // 重置为默认值
  const resetPreferences = useCallback(() => {
    setPreferences(DEFAULT_PREFERENCES);
    localStorage.removeItem(STORAGE_KEY);
    window.dispatchEvent(new Event(SYNC_EVENT));
  }, []);

  return {
    preferences,
    loaded,
    savePreferences,
    resetPreferences,
  };
}
