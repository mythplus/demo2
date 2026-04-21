import { create } from "zustand";

export interface UserPreferences {
  /** 每页显示条数 */
  pageSize: number;
  /** 默认排序方式 */
  sortOrder: "newest" | "oldest";
  /** 主题模式 */
  themeMode: "light" | "dark" | "system";
}

export const DEFAULT_PREFERENCES: UserPreferences = {
  pageSize: 10,
  sortOrder: "newest",
  themeMode: "light",
};

export const PREFERENCES_STORAGE_KEY = "mem0-preferences";

export function normalizePreferences(raw: unknown): UserPreferences {
  if (!raw || typeof raw !== "object") {
    return { ...DEFAULT_PREFERENCES };
  }

  const parsed = raw as Partial<UserPreferences> & { themeMode?: string };

  return {
    pageSize:
      typeof parsed.pageSize === "number"
        ? parsed.pageSize
        : DEFAULT_PREFERENCES.pageSize,
    sortOrder: parsed.sortOrder === "oldest" ? "oldest" : "newest",
    themeMode: parsed.themeMode === "dark" ? "dark" : parsed.themeMode === "system" ? "system" : "light",
  };
}

interface PreferencesState {
  preferences: UserPreferences;
  loaded: boolean;
  hydratePreferences: () => void;
  savePreferences: (newPrefs: Partial<UserPreferences>) => void;
  resetPreferences: () => void;
}

export const usePreferencesStore = create<PreferencesState>((set, get) => ({
  preferences: DEFAULT_PREFERENCES,
  loaded: false,

  hydratePreferences: () => {
    if (get().loaded || typeof window === "undefined") {
      return;
    }

    try {
      const saved = localStorage.getItem(PREFERENCES_STORAGE_KEY);
      if (saved) {
        const normalized = normalizePreferences(JSON.parse(saved));
        localStorage.setItem(PREFERENCES_STORAGE_KEY, JSON.stringify(normalized));
        set({ preferences: normalized, loaded: true });
        return;
      }
    } catch {
      // 忽略解析错误，直接回退默认值
    }

    set({ loaded: true });
  },

  savePreferences: (newPrefs) =>
    set((state) => {
      const updated = { ...state.preferences, ...newPrefs };
      if (typeof window !== "undefined") {
        localStorage.setItem(PREFERENCES_STORAGE_KEY, JSON.stringify(updated));
      }
      return { preferences: updated };
    }),

  resetPreferences: () => {
    if (typeof window !== "undefined") {
      localStorage.removeItem(PREFERENCES_STORAGE_KEY);
    }
    set({ preferences: DEFAULT_PREFERENCES });
  },
}));
