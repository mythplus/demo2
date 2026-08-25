/**
 * 配额管理 API 封装
 */
import { request } from "./http-client";

export interface QuotaUsage {
  tenant_id: string;
  date: string;
  today_memory_count: number;
  today_api_call_count: number;
  total_api_call_count: number;
  limits: {
    max_memories: number;
    max_api_calls_per_day: number;
    rate_limit_per_minute: number;
    rate_limit_per_hour: number;
    plan: string;
  };
  rate_limit_status: {
    enabled: boolean;
  };
}

export async function getQuotaUsageApi() {
  return request<QuotaUsage>("/v1/quota/usage");
}

export async function checkRateLimitApi() {
  return request<{ allowed: boolean; reason: string; tenant_id: string }>(
    "/v1/quota/check"
  );
}
