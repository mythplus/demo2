"use client";

import { useState, useEffect, useCallback, useRef } from "react";
import {
  type ChatSession,
  type PersistedChatMessage,
  getSession,
  saveSession,
  deleteSession,
} from "@/lib/playground-chat-db";

// 重新导出类型，方便外部使用
export type { ChatSession, PersistedChatMessage };

/** 前端使用的 ChatMessage（带 Date 类型的 timestamp） */
export interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  timestamp: Date;
  retrievedMemories?: {
    id: string;
    memory: string;
    score: number;
    user_id?: string;
  }[];
  newMemories?: {
    id: string;
    memory: string;
    event: string;
  }[];
  loading?: boolean;
}

/** 将前端 ChatMessage 转为可持久化的格式 */
function toPersisted(msg: ChatMessage): PersistedChatMessage {
  return {
    id: msg.id,
    role: msg.role,
    content: msg.content,
    timestamp: msg.timestamp.toISOString(),
    retrievedMemories: msg.retrievedMemories,
    newMemories: msg.newMemories,
  };
}

/** 将持久化的消息还原为前端 ChatMessage */
function fromPersisted(msg: PersistedChatMessage): ChatMessage {
  return {
    id: msg.id,
    role: msg.role,
    content: msg.content,
    timestamp: new Date(msg.timestamp),
    retrievedMemories: msg.retrievedMemories,
    newMemories: msg.newMemories,
    loading: false,
  };
}

/**
 * 自定义 Hook：Playground 对话持久化管理
 *
 * 将 IndexedDB 持久化存储与 React 状态同步，
 * 页面加载时自动从 IndexedDB 恢复对话记录，
 * 每次消息变更自动同步到 IndexedDB。
 */
export function usePlaygroundChat(userId: string) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [loaded, setLoaded] = useState(false);

  // 用 ref 追踪当前 userId，避免闭包问题
  const userIdRef = useRef(userId);
  userIdRef.current = userId;

  // B4 P1-8: 用 ref 追踪最新 messages，避免 flushSave 闭包捕获旧值
  const messagesRef = useRef<ChatMessage[]>(messages);
  messagesRef.current = messages;

  // 防抖保存定时器
  const saveTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // 标记是否正在从 DB 加载（避免加载时触发保存）
  const isLoadingRef = useRef(false);

  // 标记是否正在流式输出（流式期间暂停自动持久化，减少 IO 开销）
  const isStreamingRef = useRef(false);

  // 当 userId 变化时，从 IndexedDB 加载对话记录
  useEffect(() => {
    isLoadingRef.current = true;
    setLoaded(false);

    if (!userId) {
      setMessages([]);
      setLoaded(true);
      isLoadingRef.current = false;
      return;
    }

    getSession(userId)
      .then((session) => {
        if (session && session.messages.length > 0) {
          setMessages(session.messages.map(fromPersisted));
        } else {
          setMessages([]);
        }
      })
      .catch((err) => {
        console.error("从 IndexedDB 加载对话记录失败:", err);
        setMessages([]);
      })
      .finally(() => {
        setLoaded(true);
        // 延迟一帧再关闭 loading 标记，确保 setMessages 已生效
        requestAnimationFrame(() => {
          isLoadingRef.current = false;
        });
      });
  }, [userId]);

  // 持久化保存（防抖，300ms；流式输出期间自动跳过，由 flushSave 统一保存）
  const persistMessages = useCallback(
    (msgs: ChatMessage[]) => {
      if (isLoadingRef.current || isStreamingRef.current) return;
      const uid = userIdRef.current;
      if (!uid) return;

      if (saveTimerRef.current) {
        clearTimeout(saveTimerRef.current);
      }

      saveTimerRef.current = setTimeout(() => {
        // 只保存非 loading 状态的消息（正在生成中的消息不保存空内容）
        const toSave = msgs
          .filter((m) => !m.loading || m.content.length > 0)
          .map(toPersisted);

        const session: ChatSession = {
          id: uid,
          userId: uid,
          messages: toSave,
          updatedAt: new Date().toISOString(),
        };

        saveSession(session).catch((err) => {
          console.error("保存对话记录到 IndexedDB 失败:", err);
        });
      }, 300);
    },
    []
  );

  /**
   * 更新消息列表（同时触发持久化）
   */
  const updateMessages = useCallback(
    (updater: ChatMessage[] | ((prev: ChatMessage[]) => ChatMessage[])) => {
      setMessages((prev) => {
        const next =
          typeof updater === "function" ? updater(prev) : updater;
        persistMessages(next);
        return next;
      });
    },
    [persistMessages]
  );

  /**
   * 清空当前用户的对话记录
   */
  const clearMessages = useCallback(() => {
    setMessages([]);
    const uid = userIdRef.current;
    if (uid) {
      deleteSession(uid).catch((err) => {
        console.error("清空 IndexedDB 对话记录失败:", err);
      });
    }
  }, []);

  /**
   * 强制立即保存当前消息（用于重要节点，如 AI 回复完成时）
   * B4 P1-8: 不再依赖 messages state，改用 messagesRef 获取最新值
   */
  const flushSave = useCallback(
    (msgs?: ChatMessage[]) => {
      if (saveTimerRef.current) {
        clearTimeout(saveTimerRef.current);
        saveTimerRef.current = null;
      }
      const uid = userIdRef.current;
      if (!uid) return;

      const toSave = (msgs || messagesRef.current)
        .filter((m) => !m.loading || m.content.length > 0)
        .map(toPersisted);

      const session: ChatSession = {
        id: uid,
        userId: uid,
        messages: toSave,
        updatedAt: new Date().toISOString(),
      };

      saveSession(session).catch((err) => {
        console.error("强制保存对话记录失败:", err);
      });
    },
    [] // 不再依赖 messages，通过 messagesRef 获取最新值
  );

  // 组件卸载时清理定时器
  useEffect(() => {
    return () => {
      if (saveTimerRef.current) {
        clearTimeout(saveTimerRef.current);
      }
    };
  }, []);

  /**
   * 暂停自动持久化（流式输出开始时调用）
   */
  const pausePersist = useCallback(() => {
    isStreamingRef.current = true;
    // 清除可能已排队的防抖保存
    if (saveTimerRef.current) {
      clearTimeout(saveTimerRef.current);
      saveTimerRef.current = null;
    }
  }, []);

  /**
   * 恢复自动持久化（流式输出结束时调用）
   */
  const resumePersist = useCallback(() => {
    isStreamingRef.current = false;
  }, []);

  return {
    /** 当前对话消息列表 */
    messages,
    /** 是否已从 IndexedDB 加载完成 */
    loaded,
    /** 更新消息列表（自动持久化，流式期间自动跳过） */
    updateMessages,
    /** 清空当前用户的对话记录 */
    clearMessages,
    /** 强制立即保存 */
    flushSave,
    /** 暂停自动持久化（流式输出期间调用） */
    pausePersist,
    /** 恢复自动持久化（流式输出结束后调用） */
    resumePersist,
    /** 直接设置消息（不触发持久化，用于内部加载） */
    setMessages,
  };
}
