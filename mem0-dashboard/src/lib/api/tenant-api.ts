/**
 * 租户管理 API 封装
 */
import { request } from "./http-client";

export interface Tenant {
  id: string;
  name: string;
  display_name: string;
  status: string;
  plan: string;
  max_memories: number;
  max_api_calls_per_day: number;
  rate_limit_per_minute: number;
  rate_limit_per_hour: number;
  created_at: string;
  updated_at: string;
  usage?: {
    tenant_id: string;
    date: string;
    today_memory_count: number;
    today_api_call_count: number;
    total_api_call_count: number;
  };
}

export interface TenantUser {
  id: string;
  username: string;
  role: string;
  status: string;
  created_at: string;
}

export interface ApiKey {
  id: string;
  tenant_id: string;
  name: string;
  key_prefix: string;
  raw_key?: string;
  status: string;
  created_at: string;
  last_used_at: string | null;
}

export async function listTenantsApi(offset = 0, limit = 50) {
  return request<{ items: Tenant[]; total: number; offset: number; limit: number }>(
    `/v1/tenants?offset=${offset}&limit=${limit}`
  );
}

export async function getTenantApi(tenantId: string) {
  return request<Tenant>(`/v1/tenants/${tenantId}`);
}

export async function createTenantApi(data: {
  name: string;
  display_name?: string;
  plan?: string;
  max_memories?: number;
  max_api_calls_per_day?: number;
}) {
  return request<Tenant>("/v1/tenants", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export async function updateTenantApi(tenantId: string, data: Partial<Tenant>) {
  return request<Tenant>(`/v1/tenants/${tenantId}`, {
    method: "PUT",
    body: JSON.stringify(data),
  });
}

export async function deleteTenantApi(tenantId: string) {
  return request<{ detail: string }>(`/v1/tenants/${tenantId}`, { method: "DELETE" });
}

export async function listTenantUsersApi(tenantId: string) {
  return request<TenantUser[]>(`/v1/tenants/${tenantId}/users`);
}

export async function createTenantUserApi(tenantId: string, data: {
  username: string;
  password: string;
  role?: string;
}) {
  return request<TenantUser>(`/v1/tenants/${tenantId}/users`, {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export async function deleteTenantUserApi(tenantId: string, userId: string) {
  return request<{ detail: string }>(`/v1/tenants/${tenantId}/users/${userId}`, {
    method: "DELETE",
  });
}

export async function listApiKeysApi(tenantId: string) {
  return request<ApiKey[]>(`/v1/tenants/${tenantId}/api-keys`);
}

export async function createApiKeyApi(tenantId: string, name: string) {
  return request<ApiKey>(`/v1/tenants/${tenantId}/api-keys`, {
    method: "POST",
    body: JSON.stringify({ name }),
  });
}

export async function deleteApiKeyApi(tenantId: string, keyId: string) {
  return request<{ detail: string }>(`/v1/tenants/${tenantId}/api-keys/${keyId}`, {
    method: "DELETE",
  });
}
