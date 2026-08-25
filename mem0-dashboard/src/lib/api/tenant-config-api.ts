/**
 * 租户配置管理 API 封装
 */
import { request } from "./http-client";

export interface TenantConfig {
  tenant_id: string;
  llm_config: {
    provider: string;
    config: Record<string, unknown>;
  } | null;
  embedder_config: {
    provider: string;
    config: Record<string, unknown>;
  } | null;
  custom_categories: string[] | null;
}

export interface TenantConfigUpdate {
  llm_config?: {
    provider?: string;
    config?: Record<string, unknown>;
  };
  embedder_config?: {
    provider?: string;
    config?: Record<string, unknown>;
  };
  custom_categories?: string[];
}

export async function getTenantConfigApi(tenantId: string) {
  return request<TenantConfig>(`/v1/tenants/${tenantId}/config`);
}

export async function updateTenantConfigApi(tenantId: string, data: TenantConfigUpdate) {
  return request<TenantConfig>(`/v1/tenants/${tenantId}/config`, {
    method: "PUT",
    body: JSON.stringify(data),
  });
}

export async function deleteTenantConfigApi(tenantId: string) {
  return request<{ detail: string }>(`/v1/tenants/${tenantId}/config`, {
    method: "DELETE",
  });
}

export async function getEffectiveConfigApi(tenantId: string) {
  return request<Record<string, unknown>>(`/v1/tenants/${tenantId}/config/effective`);
}
