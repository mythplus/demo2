/**
 * Mem0 API TypeScript 类型定义
 */

// ============ 分类类型 ============

/** 记忆分类 */
export type Category =
  | "personal" | "relationships" | "preferences" | "health" | "travel"
  | "work" | "education" | "projects" | "ai_ml_technology" | "technical_support"
  | "finance" | "shopping" | "legal" | "entertainment" | "messages"
  | "customer_support" | "product_feedback" | "news" | "organization" | "goals";

// ============ 记忆相关类型 ============

/** 单条记忆（对齐 mem0 云平台架构） */
export interface Memory {
  id: string;
  memory: string;
  user_id?: string;
  agent_id?: string;
  run_id?: string;
  hash?: string;
  metadata?: Record<string, unknown>;
  categories?: Category[];
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
  created_at?: string;
  updated_at?: string;
}

/** 搜索记忆响应 */
export interface SearchMemoryResponse {
  results: SearchResult[];
}

/** 更新记忆请求（扩展支持 metadata、categories） */
export interface UpdateMemoryRequest {
  text?: string;
  metadata?: Record<string, unknown>;
  categories?: Category[];
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
  old_categories?: string[];
}

// ============ 筛选参数 ============

/** 多维筛选参数 */
export interface FilterParams {
  search?: string;
  user_id?: string;
  categories?: Category[];
  date_from?: string;
  date_to?: string;
  sort_by?: "created_at" | "updated_at";
  sort_order?: "asc" | "desc";
  page?: number;
  page_size?: number;
}

/** 分页记忆列表响应 */
export interface PaginatedMemoriesResponse {
  items: Memory[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

// ============ 统计数据 ============

/** 统计响应 */
export interface StatsResponse {
  total_memories: number;
  total_users: number;
  category_distribution: Record<Category, number>;
  uncategorized_count?: number;
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

/** Dashboard 摘要响应 */
export interface MemorySummaryResponse {
  recent_memories: Memory[];
  top_users: UserInfo[];
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
  /** 数据粒度：'30min' 表示30分钟粒度，'day' 表示按天 */
  granularity?: "30min" | "day";
}

// ============ 批量导入 ============

/** 批量导入单条记忆 */
export interface BatchImportItem {
  content: string;
  user_id?: string;
  metadata?: Record<string, unknown>;
  categories?: Category[];
}

/** 批量导入请求 */
export interface BatchImportRequest {
  items: BatchImportItem[];
  default_user_id?: string;
  infer?: boolean;
  auto_categorize?: boolean;
}

/** 批量导入结果项 */
export interface BatchImportResultItem {
  index: number;
  success: boolean;
  id?: string;
  memory?: string;
  error?: string;
}

/** 批量导入响应 */
export interface BatchImportResponse {
  total: number;
  success: number;
  failed: number;
  results: BatchImportResultItem[];
}

// ============ 图谱记忆 (Graph Memory) ============

/** 图谱节点 */
export interface GraphNode {
  id: string;
  name: string;
  user_id?: string;
  labels?: string[];
  val?: number;
}

/** 图谱边/链接 */
export interface GraphLink {
  source: string;
  target: string;
  relation: string;
}

/** 图谱数据（用于可视化） */
export interface GraphData {
  nodes: GraphNode[];
  links: GraphLink[];
  node_count: number;
  link_count: number;
}

/** 图谱实体 */
export interface GraphEntity {
  name: string;
  user_id?: string;
  labels?: string[];
  element_id?: string;
  relation_count?: number;
}

/** 图谱实体列表响应 */
export interface GraphEntitiesResponse {
  entities: GraphEntity[];
  total: number;
  limit: number;
  offset: number;
}

/** 图谱关系三元组 */
export interface GraphRelation {
  source: string;
  relation: string;
  target: string;
  source_user_id?: string;
  target_user_id?: string;
  element_id?: string;
}

/** 图谱关系列表响应 */
export interface GraphRelationsResponse {
  relations: GraphRelation[];
  total: number;
  limit: number;
  offset: number;
}

// ============ 系统配置信息 (Config) ============

/** 系统配置信息响应 */
export interface ConfigInfoResponse {
  llm: {
    provider: string;
    model: string;
    base_url: string;
    temperature: number;
  };
  embedder: {
    provider: string;
    model: string;
    base_url: string;
  };
  vector_store: {
    provider: string;
    collection_name: string;
    embedding_model_dims: number;
  };
  graph_store: {
    provider: string;
    url: string;
  };
}

/** 服务连接测试响应 */
export interface ServiceTestResponse {
  status: "connected" | "error";
  provider: string;
  model: string;
  base_url: string;
  model_available?: boolean;
  test_response?: string;
  embedding_dims?: number;
  message: string;
}

/** 图谱搜索请求 */
export interface GraphSearchRequest {
  query: string;
  user_id?: string;
  limit?: number;
}

/** 图谱搜索响应 */
export interface GraphSearchResponse {
  relations: GraphRelation[];
  isolated_entities: GraphEntity[];
  total: number;
}

/** 图谱统计 */
export interface GraphStatsResponse {
  entity_count: number;
  relation_count: number;
  relation_type_distribution: Record<string, number>;
  user_entity_distribution: Record<string, number>;
}

/** 图谱健康检查 */
export interface GraphHealthResponse {
  status: "connected" | "disconnected" | "error";
  message: string;
}

// ============ 批量删除 ============

/** 批量删除请求 */
export interface BatchDeleteRequest {
  memory_ids: string[];
}

/** 批量删除响应 */
export interface BatchDeleteResponse {
  total: number;
  success: number;
  failed: number;
  results: Array<{
    id: string;
    success: boolean;
    error?: string;
  }>;
}

// ============ Playground 对话 ============

/** Playground 对话消息 */
export interface PlaygroundMessage {
  role: "user" | "assistant" | "system";
  content: string;
}

/** Playground 对话请求 */
export interface PlaygroundChatRequest {
  message: string;
  user_id?: string;
  history?: PlaygroundMessage[];
  memory_limit?: number;
  stream?: boolean;
}

/** Playground 检索到的记忆 */
export interface PlaygroundRetrievedMemory {
  id: string;
  memory: string;
  score: number;
  user_id?: string;
}

/** Playground 新增的记忆 */
export interface PlaygroundNewMemory {
  id: string;
  memory: string;
  event: "ADD" | "UPDATE";
}

/** Playground 对话响应（非流式） */
export interface PlaygroundChatResponse {
  reply: string;
  retrieved_memories: PlaygroundRetrievedMemory[];
  new_memories: PlaygroundNewMemory[];
}

/** Playground SSE 事件类型 */
export type PlaygroundSSEEvent =
  | { type: "memories"; retrieved_memories: PlaygroundRetrievedMemory[] }
  | { type: "content"; content: string }
  | { type: "done"; new_memories: PlaygroundNewMemory[] }
  | { type: "error"; error: string };
