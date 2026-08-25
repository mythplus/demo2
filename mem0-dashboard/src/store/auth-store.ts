/**
 * 认证状态管理（Zustand）
 */
"use client";

import { create } from "zustand";
import { persist } from "zustand/middleware";

export interface AuthUser {
  user_id: string;
  username: string;
  role: string;
  tenant_id: string;
  tenant_name: string;
  tenant_display_name: string;
}

interface AuthState {
  user: AuthUser | null;
  accessToken: string | null;
  refreshToken: string | null;
  isAuthenticated: boolean;
  setAuth: (data: {
    access_token: string;
    refresh_token: string;
    user: AuthUser;
  }) => void;
  clearAuth: () => void;
  updateTokens: (accessToken: string, refreshToken: string) => void;
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set) => ({
      user: null,
      accessToken: null,
      refreshToken: null,
      isAuthenticated: false,
      setAuth: (data) =>
        set({
          accessToken: data.access_token,
          refreshToken: data.refresh_token,
          user: data.user,
          isAuthenticated: true,
        }),
      clearAuth: () =>
        set({
          user: null,
          accessToken: null,
          refreshToken: null,
          isAuthenticated: false,
        }),
      updateTokens: (accessToken, refreshToken) =>
        set({ accessToken, refreshToken }),
    }),
    {
      name: "mem0-auth",
      // 只持久化 token 和 user，不持久化函数
      partialize: (state) => ({
        user: state.user,
        accessToken: state.accessToken,
        refreshToken: state.refreshToken,
        isAuthenticated: state.isAuthenticated,
      }),
    }
  )
);
