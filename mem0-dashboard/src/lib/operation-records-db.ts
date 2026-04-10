/**
 * IndexedDB 封装工具 —— 操作记录持久化存储
 *
 * 使用浏览器原生 IndexedDB 存储导入/导出操作记录，
 * 支持 Blob 文件存储，页面刷新后数据不丢失。
 */

/** 数据库名称 & 版本 */
const DB_NAME = "mem0-operation-records";
const DB_VERSION = 1;
/** 对象仓库名称 */
const STORE_NAME = "records";

/** 操作记录状态（与页面中的状态展示保持一致） */
export type OperationRecordStatus =
  | "成功"
  | "失败"
  | "导入中"
  | "部分成功"
  | "已取消";

/** 操作记录类型（与页面中保持一致） */
export interface OperationRecord {
  id: string;
  type: "导入" | "导出";
  time: string;
  status: OperationRecordStatus;
  filename: string;
  blob: Blob | null;
  detail?: string;
}

/**
 * 打开（或创建）IndexedDB 数据库
 */
function openDB(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    const request = indexedDB.open(DB_NAME, DB_VERSION);

    request.onupgradeneeded = () => {
      const db = request.result;
      if (!db.objectStoreNames.contains(STORE_NAME)) {
        // 以 id 为主键，创建时间索引方便按时间排序
        const store = db.createObjectStore(STORE_NAME, { keyPath: "id" });
        store.createIndex("time", "time", { unique: false });
      }
    };

    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error);
  });
}

/**
 * 获取所有操作记录（按时间倒序）
 */
export async function getAllRecords(): Promise<OperationRecord[]> {
  const db = await openDB();
  return new Promise((resolve, reject) => {
    const tx = db.transaction(STORE_NAME, "readonly");
    const store = tx.objectStore(STORE_NAME);
    const request = store.getAll();

    request.onsuccess = () => {
      const records = request.result as OperationRecord[];
      // 按时间倒序排列（最新的在前）
      records.sort((a, b) => (b.time > a.time ? 1 : b.time < a.time ? -1 : 0));
      resolve(records);
    };
    request.onerror = () => reject(request.error);
    tx.oncomplete = () => db.close();
  });
}

/** 最多保留的记录数 */
export const MAX_RECORDS = 20;

/**
 * 添加一条操作记录，并自动清理超出 MAX_RECORDS 的旧记录
 */
export async function addRecord(record: OperationRecord): Promise<void> {
  const db = await openDB();
  return new Promise((resolve, reject) => {
    const tx = db.transaction(STORE_NAME, "readwrite");
    const store = tx.objectStore(STORE_NAME);
    store.add(record);

    // 添加后检查总数，超出限制则删除最旧的记录
    const countReq = store.count();
    countReq.onsuccess = () => {
      const total = countReq.result;
      if (total > MAX_RECORDS) {
        // 获取所有记录，按时间排序后删除最旧的
        const allReq = store.getAll();
        allReq.onsuccess = () => {
          const all = (allReq.result as OperationRecord[])
            .sort((a, b) => (b.time > a.time ? 1 : b.time < a.time ? -1 : 0));
          // 删除超出部分（保留前 MAX_RECORDS 条）
          const toDelete = all.slice(MAX_RECORDS);
          for (const r of toDelete) {
            store.delete(r.id);
          }
        };
      }
    };

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
 * 更新一条操作记录（局部更新）
 */
export async function updateRecord(
  id: string,
  updates: Partial<Omit<OperationRecord, "id">>
): Promise<void> {
  const db = await openDB();
  return new Promise((resolve, reject) => {
    const tx = db.transaction(STORE_NAME, "readwrite");
    const store = tx.objectStore(STORE_NAME);
    const getReq = store.get(id);

    getReq.onsuccess = () => {
      const existing = getReq.result as OperationRecord | undefined;
      if (!existing) {
        // 记录不存在，静默跳过
        db.close();
        resolve();
        return;
      }
      store.put({ ...existing, ...updates });
    };

    getReq.onerror = () => {
      db.close();
      reject(getReq.error);
    };

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
 * 清空所有操作记录
 */
export async function clearAllRecords(): Promise<void> {
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

/**
 * 获取记录总数
 */
export async function getRecordCount(): Promise<number> {
  const db = await openDB();
  return new Promise((resolve, reject) => {
    const tx = db.transaction(STORE_NAME, "readonly");
    const store = tx.objectStore(STORE_NAME);
    const request = store.count();

    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error);
    tx.oncomplete = () => db.close();
  });
}
