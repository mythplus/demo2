/**
 * Mem0 API TypeScript 类型定义
 */

// ============ 分类与状态类型 ============

/** 记忆分类 */
export type Category = "personal" | "work" | "health" | "finance" | "travel" | "education" | "preferences" | "relationships";

/** 记忆状态 */
export type MemoryState = "active" | "paused" | "archived" | "deleted";

// ============ 记忆相关类型 ============

/** 单条记忆 */
export interface Memory {
  id: string;
  memory: string;
  user_id?: string;
  agent_id?: string;
  run_id?: string;
  hash?: string;
  metadata?: Record<string, unknown>;
  categories?: Category[];
  state?: MemoryState;
  created_at?: string;
  updated_at?: string;
}

/** 添加记忆的消息格式 */
export interface MemoryMessage {
  role: "user" | "assistant" | "system";
  content: string;
}

/** 添加记忆请求 */
export interface AddMemoryRequest {
  messages: MemoryMessage[];
  user_id?: string;
  agent_id?: string;
  run_id?: string;
  metadata?: Record<string, unknown>;
  categories?: Category[];
  state?: MemoryState;
}

/** 添加记忆响应 */
export interface AddMemoryResponse {
  results: Array<{
    id: string;
    memory: string;
    event: "ADD" | "UPDATE" | "DELETE" | "NONE";
  }>;
}

/** 搜索记忆请求 */
export interface SearchMemoryRequest {
  query: string;
  user_id?: string;
  agent_id?: string;
  run_id?: string;
  limit?: number;
}

/** 搜索结果项 */
export interface SearchResult {
  id: string;
  memory: string;
  score: number;
  user_id?: string;
  agent_id?: string;
  metadata?: Record<string, unknown>;
  categories?: Category[];
  state?: MemoryState;
  created_at?: string;
  updated_at?: string;
}

/** 搜索记忆响应 */
export interface SearchMemoryResponse {
  results: SearchResult[];
}

/** 更新记忆请求（扩展支持 metadata、categories、state） */
export interface UpdateMemoryRequest {
  text?: string;
  metadata?: Record<string, unknown>;
  categories?: Category[];
  state?: MemoryState;
}

/** 记忆历史记录 */
export interface MemoryHistory {
  id: string;
  memory_id: string;
  old_memory: string | null;
  new_memory: string;
  event: "ADD" | "UPDATE" | "DELETE";
  created_at: string;
}

// ============ 筛选参数 ============

/** 多维筛选参数 */
export interface FilterParams {
  search?: string;
  user_id?: string;
  categories?: Category[];
  state?: MemoryState;
  date_from?: string;
  date_to?: string;
  sort_by?: "created_at" | "updated_at";
  sort_order?: "asc" | "desc";
}

// ============ 统计数据 ============

/** 统计响应 */
export interface StatsResponse {
  total_memories: number;
  total_users: number;
  category_distribution: Record<Category, number>;
  state_distribution: Record<MemoryState, number>;
  daily_trend: Array<{ date: string; count: number }>;
}

// ============ API 响应通用类型 ============

/** API 错误响应 */
export interface ApiError {
  detail: string;
}

/** 删除响应 */
export interface DeleteResponse {
  message: string;
}

// ============ 前端扩展类型 ============

/** 用户信息（从记忆数据聚合） */
export interface UserInfo {
  user_id: string;
  memory_count: number;
  last_active?: string;
}

/** Dashboard 统计数据 */
export interface DashboardStats {
  total_memories: number;
  total_users: number;
  recent_memories: Memory[];
}

/** API 连接状态 */
export type ConnectionStatus = "connected" | "disconnected" | "checking";

// ============ 关联记忆 ============

/** 关联记忆项 */
export interface RelatedMemory {
  id: string;
  memory: string;
  score: number;
  user_id?: string;
  categories?: Category[];
  state?: MemoryState;
  created_at?: string;
}

/** 关联记忆响应 */
export interface RelatedMemoriesResponse {
  results: RelatedMemory[];
}
