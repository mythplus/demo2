/**
 * IndexedDB 封装工具 —— Playground 对话持久化存储
 *
 * 使用浏览器原生 IndexedDB 存储 Playground 的对话会话记录，
 * 页面刷新或切换页面后数据不丢失。
 */

/** 数据库名称 & 版本 */
const DB_NAME = "mem0-playground-chat";
const DB_VERSION = 1;
/** 对象仓库名称 */
const STORE_NAME = "sessions";

/** 单条对话消息（与页面中 ChatMessage 保持一致） */
export interface PersistedChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  timestamp: string; // ISO 字符串，方便序列化
  /** 该轮对话检索到的记忆 */
  retrievedMemories?: {
    id: string;
    memory: string;
    score: number;
    user_id?: string;
  }[];
  /** 该轮对话新增的记忆 */
  newMemories?: {
    id: string;
    memory: string;
    event: string;
  }[];
}

/** 对话会话记录 */
export interface ChatSession {
  /** 会话 ID = userId（每个用户一个会话） */
  id: string;
  /** 用户 ID */
  userId: string;
  /** 对话消息列表 */
  messages: PersistedChatMessage[];
  /** 最后更新时间 */
  updatedAt: string;
}

/** 最多保留的会话数 */
export const MAX_SESSIONS = 50;

/**
 * 打开（或创建）IndexedDB 数据库
 */
function openDB(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    const request = indexedDB.open(DB_NAME, DB_VERSION);

    request.onupgradeneeded = () => {
      const db = request.result;
      if (!db.objectStoreNames.contains(STORE_NAME)) {
        const store = db.createObjectStore(STORE_NAME, { keyPath: "id" });
        store.createIndex("updatedAt", "updatedAt", { unique: false });
      }
    };

    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error);
  });
}

/**
 * 获取指定用户的对话会话
 */
export async function getSession(userId: string): Promise<ChatSession | null> {
  const db = await openDB();
  return new Promise((resolve, reject) => {
    const tx = db.transaction(STORE_NAME, "readonly");
    const store = tx.objectStore(STORE_NAME);
    const request = store.get(userId);

    request.onsuccess = () => {
      resolve((request.result as ChatSession) || null);
    };
    request.onerror = () => reject(request.error);
    tx.oncomplete = () => db.close();
  });
}

/**
 * 保存（创建或更新）对话会话
 */
export async function saveSession(session: ChatSession): Promise<void> {
  const db = await openDB();
  return new Promise((resolve, reject) => {
    const tx = db.transaction(STORE_NAME, "readwrite");
    const store = tx.objectStore(STORE_NAME);
    store.put(session);

    tx.oncomplete = () => {
      db.close();
      resolve();
    };
    tx.onerror = () => {
      db.close();
      reject(tx.error);
    };
  });
}

/**
 * 删除指定用户的对话会话
 */
export async function deleteSession(userId: string): Promise<void> {
  const db = await openDB();
  return new Promise((resolve, reject) => {
    const tx = db.transaction(STORE_NAME, "readwrite");
    const store = tx.objectStore(STORE_NAME);
    store.delete(userId);

    tx.oncomplete = () => {
      db.close();
      resolve();
    };
    tx.onerror = () => {
      db.close();
      reject(tx.error);
    };
  });
}

/**
 * 获取所有会话列表（按更新时间倒序）
 */
export async function getAllSessions(): Promise<ChatSession[]> {
  const db = await openDB();
  return new Promise((resolve, reject) => {
    const tx = db.transaction(STORE_NAME, "readonly");
    const store = tx.objectStore(STORE_NAME);
    const request = store.getAll();

    request.onsuccess = () => {
      const sessions = request.result as ChatSession[];
      sessions.sort((a, b) =>
        b.updatedAt > a.updatedAt ? 1 : b.updatedAt < a.updatedAt ? -1 : 0
      );
      resolve(sessions);
    };
    request.onerror = () => reject(request.error);
    tx.oncomplete = () => db.close();
  });
}

/**
 * 清空所有对话会话
 */
export async function clearAllSessions(): Promise<void> {
  const db = await openDB();
  return new Promise((resolve, reject) => {
    const tx = db.transaction(STORE_NAME, "readwrite");
    const store = tx.objectStore(STORE_NAME);
    store.clear();

    tx.oncomplete = () => {
      db.close();
      resolve();
    };
    tx.onerror = () => {
      db.close();
      reject(tx.error);
    };
  });
}
