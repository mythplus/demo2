/**
 * 认证 API 封装
 */
import { request } from "./http-client";

export interface LoginParams {
  tenant_name?: string;
  username: string;
  password: string;
}

export interface LoginResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
  expires_in: number;
  user: {
    user_id: string;
    username: string;
    role: string;
    tenant_id: string;
    tenant_name: string;
    tenant_display_name: string;
  };
}

export interface RefreshResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
}

export async function loginApi(params: LoginParams): Promise<LoginResponse> {
  return request<LoginResponse>("/v1/auth/login", {
    method: "POST",
    body: JSON.stringify({
      tenant_name: params.tenant_name || "default",
      username: params.username,
      password: params.password,
    }),
  });
}

export async function refreshTokenApi(refreshToken: string): Promise<RefreshResponse> {
  return request<RefreshResponse>("/v1/auth/refresh", {
    method: "POST",
    body: JSON.stringify({ refresh_token: refreshToken }),
  });
}

export async function getCurrentUserApi(): Promise<{
  user_id: string;
  username: string;
  role: string;
  tenant_id: string;
  tenant_name: string;
  tenant_display_name: string;
}> {
  return request("/v1/auth/me");
}

export async function logoutApi(): Promise<{ detail: string }> {
  return request<{ detail: string }>("/v1/auth/logout", { method: "POST" });
}
