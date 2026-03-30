/**
 * Mem0 API TypeScript 类型定义
 */

// ============ 分类与状态类型 ============

/** 记忆分类 */
export type Category =
  | "personal" | "relationships" | "preferences" | "health" | "travel"
  | "work" | "education" | "projects" | "ai_ml_technology" | "technical_support"
  | "finance" | "shopping" | "legal" | "entertainment" | "messages"
  | "customer_support" | "product_feedback" | "news" | "organization" | "goals";

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
  /** true: AI 自动提取关键记忆（可能拆分为多条）; false: 原文整条存储 */
  infer?: boolean;
  /** true: 未手动选择标签时由 AI 自动分类; false: 不自动分类 */
  auto_categorize?: boolean;
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
  /** true: 对当前内容重新 AI 自动分类 */
  auto_categorize?: boolean;
}

/** 记忆历史记录 */
export interface MemoryHistory {
  id: string;
  memory_id: string;
  old_memory: string | null;
  new_memory: string;
  event: "ADD" | "UPDATE" | "DELETE";
  created_at: string;
  categories?: string[];
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

// ============ 访问日志 ============

/** 访问日志项 */
export interface AccessLog {
  id: number;
  memory_id: string;
  action: "view" | "search" | "edit";
  memory_preview?: string;
  timestamp: string;
}

/** 访问日志响应 */
export interface AccessLogsResponse {
  logs: AccessLog[];
  total?: number;
}

// ============ 请求日志 ============

/** 请求日志项 */
export interface RequestLog {
  id: number;
  timestamp: string;
  method: string;
  path: string;
  request_type: string;
  user_id?: string;
  status_code: number;
  latency_ms: number;
  payload_summary?: string;
  error?: string;
}

/** 请求日志响应 */
export interface RequestLogsResponse {
  logs: RequestLog[];
  total: number;
}

/** 请求日志统计 */
export interface RequestLogsStats {
  total: number;
  type_distribution: Record<string, number>;
  daily_trend: Array<Record<string, unknown>>;
  types: string[];
}
