/**
 * Mem0 API - 系统配置接口
 */

import type {
  ConfigInfoResponse,
  ServiceTestResponse,
} from "./types";
import { request } from "./http-client";

export const configApi = {
  /** 获取系统配置信息（LLM、Embedder、向量数据库、图数据库） */
  async getConfigInfo(): Promise<ConfigInfoResponse> {
    return request<ConfigInfoResponse>("/v1/config/info");
  },

  /** 测试 LLM 大模型连接 */
  async testLLMConnection(): Promise<ServiceTestResponse> {
    return request<ServiceTestResponse>("/v1/config/test-llm");
  },

  /** 测试 Embedder 嵌入模型连接 */
  async testEmbedderConnection(): Promise<ServiceTestResponse> {
    return request<ServiceTestResponse>("/v1/config/test-embedder");
  },
};
