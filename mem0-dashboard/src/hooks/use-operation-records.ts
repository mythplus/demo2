"use client";

import { useState, useEffect, useCallback, useRef } from "react";
import {
  type OperationRecord,
  getAllRecords,
  addRecord as dbAddRecord,
  updateRecord as dbUpdateRecord,
  clearAllRecords,
  MAX_RECORDS,
} from "@/lib/operation-records-db";

// 重新导出类型，方便外部使用
export type { OperationRecord };

/**
 * 自定义 Hook：操作记录管理
 *
 * 将 IndexedDB 持久化存储与 React 状态同步，
 * 页面加载时自动从 IndexedDB 读取历史记录，
 * 每次增删改操作同时更新内存状态和 IndexedDB。
 */
export function useOperationRecords() {
  const [records, setRecords] = useState<OperationRecord[]>([]);
  const [loading, setLoading] = useState(true);

  // 动态计算：当前 records 中是否存在"导入中"状态的记录
  const hasImportingRecord = records.some((r) => r.status === "导入中");

  // 用 ref 追踪是否已初始化，避免重复加载
  const initializedRef = useRef(false);

  // 页面加载时从 IndexedDB 读取所有记录
  useEffect(() => {
    if (initializedRef.current) return;
    initializedRef.current = true;

    getAllRecords()
      .then((data) => {
        // 初始化时也只保留最近 MAX_RECORDS 条
        setRecords(data.slice(0, MAX_RECORDS));
      })
      .catch((err) => {
        console.error("读取操作记录失败:", err);
      })
      .finally(() => {
        setLoading(false);
      });
  }, []);

  // 生成时间字符串
  const getTimeStr = () => {
    const now = new Date();
    return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}-${String(now.getDate()).padStart(2, "0")} ${String(now.getHours()).padStart(2, "0")}:${String(now.getMinutes()).padStart(2, "0")}:${String(now.getSeconds()).padStart(2, "0")}`;
  };

  /**
   * 添加一条操作记录
   * 同时写入 IndexedDB 和更新 React 状态
   * @returns 新记录的 id
   */
  const addRecord = useCallback(
    (record: Omit<OperationRecord, "id" | "time">) => {
      const id = `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
      const newRecord: OperationRecord = {
        id,
        time: getTimeStr(),
        ...record,
      };

      // 先更新内存状态（保证 UI 即时响应，只保留最近 MAX_RECORDS 条）
      setRecords((prev) => [newRecord, ...prev].slice(0, MAX_RECORDS));

      // 异步写入 IndexedDB
      dbAddRecord(newRecord).catch((err) => {
        console.error("写入操作记录到 IndexedDB 失败:", err);
      });

      return id;
    },
    []
  );

  /**
   * 更新一条操作记录
   * 同时更新 IndexedDB 和 React 状态
   */
  const updateRecord = useCallback(
    (id: string, updates: Partial<Omit<OperationRecord, "id">>) => {
      // 先更新内存状态
      setRecords((prev) =>
        prev.map((r) => (r.id === id ? { ...r, ...updates } : r))
      );

      // 异步更新 IndexedDB
      dbUpdateRecord(id, updates).catch((err) => {
        console.error("更新操作记录到 IndexedDB 失败:", err);
      });
    },
    []
  );

  /**
   * 清空所有操作记录
   * 同时清空 IndexedDB 和 React 状态
   */
  const clearRecords = useCallback(() => {
    setRecords([]);
    clearAllRecords().catch((err) => {
      console.error("清空 IndexedDB 操作记录失败:", err);
    });
  }, []);

  /**
   * 下载操作记录中的文件
   */
  const downloadRecord = useCallback((record: OperationRecord) => {
    if (!record.blob) return;
    const url = URL.createObjectURL(record.blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = record.filename;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
  }, []);

  return {
    /** 操作记录列表（按时间倒序） */
    records,
    /** 是否正在从 IndexedDB 加载 */
    loading,
    /** 是否存在"导入中"状态的记录（动态计算） */
    hasImportingRecord,
    /** 添加记录，返回 id */
    addRecord,
    /** 更新记录 */
    updateRecord,
    /** 清空所有记录 */
    clearRecords,
    /** 下载记录中的文件 */
    downloadRecord,
  };
}
