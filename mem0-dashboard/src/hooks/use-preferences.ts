"use client";

import { useEffect } from "react";
import {
  PREFERENCES_STORAGE_KEY,
  usePreferencesStore,
  type UserPreferences,
} from "@/store/preferences-store";

export type { UserPreferences } from "@/store/preferences-store";

/**
 * 全局用户偏好设置 Hook
 * 使用单一 store 持久化，支持跨组件实时同步与跨标签页同步。
 */
export function usePreferences() {
  const preferences = usePreferencesStore((state) => state.preferences);
  const loaded = usePreferencesStore((state) => state.loaded);
  const hydratePreferences = usePreferencesStore((state) => state.hydratePreferences);
  const savePreferences = usePreferencesStore((state) => state.savePreferences);
  const resetPreferences = usePreferencesStore((state) => state.resetPreferences);

  useEffect(() => {
    hydratePreferences();
  }, [hydratePreferences]);

  useEffect(() => {
    if (typeof window === "undefined") {
      return;
    }

    const handleStorage = (event: StorageEvent) => {
      if (event.key === PREFERENCES_STORAGE_KEY) {
        usePreferencesStore.setState({ loaded: false });
        hydratePreferences();
      }
    };

    window.addEventListener("storage", handleStorage);
    return () => {
      window.removeEventListener("storage", handleStorage);
    };
  }, [hydratePreferences]);

  return {
    preferences,
    loaded,
    savePreferences: (newPrefs: Partial<UserPreferences>) => savePreferences(newPrefs),
    resetPreferences,
  };
}
