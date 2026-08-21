/**
 * Mem0 API - 统一导出入口
 *
 * 将按资源类型拆分的 API 模块统一导出。
 * 原 client.ts 中的 mem0Api 对象保留向后兼容，
 * 同时推荐使用按资源拆分的 memoriesApi / graphApi / logsApi / configApi / usersApi。
 */

export { request, buildQuery, buildAuthHeaders, API_BASE, API_KEY } from "./http-client";
export { memoriesApi } from "./memories-api";
export { graphApi } from "./graph-api";
export { logsApi } from "./logs-api";
export { configApi } from "./config-api";
export { usersApi } from "./users-api";
export type {
  UserListResponse,
  UserDetailResponse,
} from "./users-api";

// ============ 向后兼容：mem0Api 聚合对象 ============
import { memoriesApi } from "./memories-api";
import { graphApi } from "./graph-api";
import { logsApi } from "./logs-api";
import { configApi } from "./config-api";

/**
 * @deprecated 推荐使用按资源拆分的 API 模块（memoriesApi / graphApi 等）。
 * 此对象保留向后兼容，内部委托给拆分后的模块。
 */
export const mem0Api = {
  // 记忆 CRUD
  addMemory: memoriesApi.addMemory.bind(memoriesApi),
  batchImport: memoriesApi.batchImport.bind(memoriesApi),
  getMemories: memoriesApi.getMemories.bind(memoriesApi),
  getMemory: memoriesApi.getMemory.bind(memoriesApi),
  updateMemory: memoriesApi.updateMemory.bind(memoriesApi),
  deleteMemory: memoriesApi.deleteMemory.bind(memoriesApi),
  batchDeleteMemories: memoriesApi.batchDeleteMemories.bind(memoriesApi),
  deleteAllMemories: memoriesApi.deleteAllMemories.bind(memoriesApi),
  searchMemories: memoriesApi.searchMemories.bind(memoriesApi),
  getMemoryHistory: memoriesApi.getMemoryHistory.bind(memoriesApi),
  getRelatedMemories: memoriesApi.getRelatedMemories.bind(memoriesApi),
  getAccessLogs: memoriesApi.getAccessLogs.bind(memoriesApi),
  healthCheck: memoriesApi.healthCheck.bind(memoriesApi),

  // 统计
  getStats: logsApi.getStats.bind(logsApi),

  // 请求日志
  getRequestLogs: logsApi.getRequestLogs.bind(logsApi),
  getRequestLogsStats: logsApi.getRequestLogsStats.bind(logsApi),

  // 图谱
  getGraphStats: graphApi.getGraphStats.bind(graphApi),
  getGraphEntities: graphApi.getGraphEntities.bind(graphApi),
  getGraphRelations: graphApi.getGraphRelations.bind(graphApi),
  searchGraph: graphApi.searchGraph.bind(graphApi),
  getUserGraph: graphApi.getUserGraph.bind(graphApi),
  getAllGraph: graphApi.getAllGraph.bind(graphApi),
  deleteGraphEntity: graphApi.deleteGraphEntity.bind(graphApi),
  deleteGraphRelation: graphApi.deleteGraphRelation.bind(graphApi),
  graphHealthCheck: graphApi.graphHealthCheck.bind(graphApi),

  // 系统配置
  getConfigInfo: configApi.getConfigInfo.bind(configApi),
  testLLMConnection: configApi.testLLMConnection.bind(configApi),
  testEmbedderConnection: configApi.testEmbedderConnection.bind(configApi),
};

// 类型导出
export * from "./types";
