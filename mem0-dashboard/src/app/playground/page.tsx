"use client";

import React, { useState, useRef, useEffect, useCallback } from "react";
import {
  Send,
  Brain,
  Sparkles,
  Loader2,
  Trash2,
  ChevronRight,
  Plus,
  User,
  Bot,
  Clock,
  ArrowDown,
  RefreshCw,
  MessageSquare,
  PanelRightOpen,
  Square,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { mem0Api } from "@/lib/api";
import type {
  PlaygroundMessage,
  PlaygroundRetrievedMemory,
  PlaygroundNewMemory,
  PlaygroundSSEEvent,
  Memory,
} from "@/lib/api";
import { UserCombobox } from "@/components/shared/user-combobox";

// ============ 类型定义 ============

/** 对话消息（前端扩展，包含记忆信息） */
interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  timestamp: Date;
  /** 该轮对话检索到的记忆 */
  retrievedMemories?: PlaygroundRetrievedMemory[];
  /** 该轮对话新增的记忆 */
  newMemories?: PlaygroundNewMemory[];
  /** 是否正在生成中 */
  loading?: boolean;
}

// ============ 辅助函数 ============

function generateId(): string {
  return `msg_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`;
}

// ============ 消息气泡组件 ============

function MessageBubble({
  message,
  onShowMemories,
}: {
  message: ChatMessage;
  onShowMemories?: (memories: PlaygroundRetrievedMemory[]) => void;
}) {
  const isUser = message.role === "user";

  return (
    <div className={`flex gap-3 ${isUser ? "flex-row-reverse" : ""}`}>
      {/* 头像 */}
      <div
        className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-full ${
          isUser
            ? "bg-primary text-primary-foreground"
            : "bg-muted text-muted-foreground"
        }`}
      >
        {isUser ? <User className="h-4 w-4" /> : <Bot className="h-4 w-4" />}
      </div>

      {/* 消息内容 */}
      <div className={`flex flex-col gap-1 max-w-[75%] ${isUser ? "items-end" : "items-start"}`}>
        <div
          className={`rounded-2xl px-4 py-2.5 text-sm leading-relaxed whitespace-pre-wrap break-words ${
            isUser
              ? "bg-primary text-primary-foreground rounded-tr-md"
              : "bg-muted rounded-tl-md"
          }`}
        >
          {message.content}
          {message.loading && !message.content && (
            <span className="inline-flex gap-1">
              <span className="h-1.5 w-1.5 rounded-full bg-current animate-bounce" />
              <span className="h-1.5 w-1.5 rounded-full bg-current animate-bounce" style={{ animationDelay: "0.15s" }} />
              <span className="h-1.5 w-1.5 rounded-full bg-current animate-bounce" style={{ animationDelay: "0.3s" }} />
            </span>
          )}
        </div>

        {/* 消息底部信息 */}
        <div className={`flex items-center gap-2 px-1 ${isUser ? "flex-row-reverse" : ""}`}>
          <span className="text-[11px] text-muted-foreground/50">
            {message.timestamp.toLocaleTimeString("zh-CN", {
              hour: "2-digit",
              minute: "2-digit",
            })}
          </span>

          {/* 检索到的记忆标记 */}
          {!isUser && message.retrievedMemories && message.retrievedMemories.length > 0 && (
            <button
              className="inline-flex items-center gap-1 text-[11px] text-primary/70 hover:text-primary transition-colors"
              onClick={() => onShowMemories?.(message.retrievedMemories!)}
            >
              <Brain className="h-3 w-3" />
              引用了 {message.retrievedMemories.length} 条记忆
            </button>
          )}

          {/* 新增记忆标记 */}
          {!isUser && message.newMemories && message.newMemories.length > 0 && (
            <span className="inline-flex items-center gap-1 text-[11px] text-emerald-600 dark:text-emerald-400">
              <Plus className="h-3 w-3" />
              新增 {message.newMemories.length} 条记忆
            </span>
          )}
        </div>
      </div>
    </div>
  );
}

// ============ 记忆侧边栏组件 ============

function MemorySidebar({
  open,
  onToggle,
  userMemories,
  loadingMemories,
  onRefresh,
  highlightMemoryIds,
}: {
  open: boolean;
  onToggle: () => void;
  userMemories: Memory[];
  loadingMemories: boolean;
  onRefresh: () => void;
  highlightMemoryIds: Set<string>;
}) {
  return (
    <div
      className={`flex flex-col border-l bg-card transition-all duration-300 ${
        open ? "w-80" : "w-0 overflow-hidden border-l-0"
      }`}
    >
      {open && (
        <>
          <div className="flex items-center justify-between border-b px-4 h-12">
            <div className="flex items-center gap-2">
              <Brain className="h-4 w-4 text-primary" />
              <span className="text-sm font-semibold">用户记忆</span>
              <Badge variant="secondary" className="text-[11px] h-5 px-1.5">
                {userMemories.length}
              </Badge>
            </div>
            <div className="flex items-center gap-1">
              <Button
                variant="ghost"
                size="icon"
                className="h-7 w-7"
                onClick={onRefresh}
                title="刷新记忆"
              >
                <RefreshCw className={`h-3.5 w-3.5 ${loadingMemories ? "animate-spin" : ""}`} />
              </Button>
              <Button
                variant="ghost"
                size="icon"
                className="h-7 w-7"
                onClick={onToggle}
                title="收起面板"
              >
                <ChevronRight className="h-4 w-4" />
              </Button>
            </div>
          </div>

          <div className="flex-1 overflow-y-auto p-3 space-y-1.5">
            {loadingMemories ? (
              <div className="flex items-center justify-center py-8">
                <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
              </div>
            ) : userMemories.length > 0 ? (
              userMemories.map((mem) => (
                <div
                  key={mem.id}
                  className={`rounded-lg border p-2.5 text-sm transition-all duration-300 ${
                    highlightMemoryIds.has(mem.id)
                      ? "border-primary/50 bg-primary/5 shadow-sm"
                      : "border-transparent hover:bg-muted/50"
                  }`}
                >
                  <p className="leading-relaxed text-[13px] break-words">{mem.memory}</p>
                  <div className="mt-1.5 flex items-center gap-2">
                    {highlightMemoryIds.has(mem.id) && (
                      <Badge variant="default" className="text-[10px] h-4 px-1.5">
                        本轮引用
                      </Badge>
                    )}
                    {mem.created_at && (
                      <span className="text-[10px] text-muted-foreground/50">
                        <Clock className="mr-0.5 inline h-2.5 w-2.5" />
                        {new Date(mem.created_at).toLocaleDateString("zh-CN")}
                      </span>
                    )}
                  </div>
                </div>
              ))
            ) : (
              <div className="flex flex-col items-center justify-center py-12 text-center">
                <Brain className="mb-3 h-8 w-8 text-muted-foreground/20" />
                <p className="text-xs text-muted-foreground">暂无记忆</p>
                <p className="mt-1 text-[11px] text-muted-foreground/60">
                  开始对话后，AI 会自动提取并存储记忆
                </p>
              </div>
            )}
          </div>
        </>
      )}
    </div>
  );
}

// ============ 主页面 ============

export default function PlaygroundPage() {
  // 对话状态
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [inputValue, setInputValue] = useState("");
  const [isGenerating, setIsGenerating] = useState(false);

  // 用户选择
  const [userId, setUserId] = useState("");
  const [users, setUsers] = useState<string[]>([]);

  // 记忆侧边栏
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [userMemories, setUserMemories] = useState<Memory[]>([]);
  const [loadingMemories, setLoadingMemories] = useState(false);
  const [highlightMemoryIds, setHighlightMemoryIds] = useState<Set<string>>(new Set());

  // 自动滚动
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const messagesContainerRef = useRef<HTMLDivElement>(null);
  const [showScrollDown, setShowScrollDown] = useState(false);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  // 中止控制器
  const abortControllerRef = useRef<AbortController | null>(null);

  // 加载用户列表
  useEffect(() => {
    const loadUsers = async () => {
      try {
        const memories = await mem0Api.getMemories();
        const uniqueUsers = Array.from(
          new Set(
            (Array.isArray(memories) ? memories : [])
              .map((m: Memory) => m.user_id)
              .filter(Boolean)
          )
        ) as string[];
        setUsers(uniqueUsers);
      } catch {}
    };
    loadUsers();
  }, []);

  // 加载用户记忆
  const loadUserMemories = useCallback(async () => {
    if (!userId) return;
    setLoadingMemories(true);
    try {
      const memories = await mem0Api.getMemories(userId);
      const active = (Array.isArray(memories) ? memories : []).filter(
        (m) => m.state !== "deleted"
      );
      setUserMemories(active);
    } catch {
      setUserMemories([]);
    } finally {
      setLoadingMemories(false);
    }
  }, [userId]);

  useEffect(() => {
    loadUserMemories();
  }, [loadUserMemories]);

  // 自动滚动到底部
  const scrollToBottom = useCallback(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, []);

  useEffect(() => {
    scrollToBottom();
  }, [messages, scrollToBottom]);

  // 监听滚动位置
  useEffect(() => {
    const container = messagesContainerRef.current;
    if (!container) return;
    const handleScroll = () => {
      const { scrollTop, scrollHeight, clientHeight } = container;
      setShowScrollDown(scrollHeight - scrollTop - clientHeight > 100);
    };
    container.addEventListener("scroll", handleScroll);
    return () => container.removeEventListener("scroll", handleScroll);
  }, []);

  // 发送消息
  const handleSend = async () => {
    const text = inputValue.trim();
    if (!text || isGenerating) return;

    setInputValue("");
    // 重置输入框高度
    if (inputRef.current) {
      inputRef.current.style.height = "auto";
    }
    setIsGenerating(true);

    const userMsg: ChatMessage = {
      id: generateId(),
      role: "user",
      content: text,
      timestamp: new Date(),
    };

    const aiMsgId = generateId();
    const aiMsg: ChatMessage = {
      id: aiMsgId,
      role: "assistant",
      content: "",
      timestamp: new Date(),
      loading: true,
    };

    setMessages((prev) => [...prev, userMsg, aiMsg]);

    const history: PlaygroundMessage[] = messages.map((m) => ({
      role: m.role,
      content: m.content,
    }));

    const controller = new AbortController();
    abortControllerRef.current = controller;

    try {
      await mem0Api.playgroundChatStream(
        {
          message: text,
          user_id: userId,
          history,
          memory_limit: 5,
          stream: true,
        },
        (event: PlaygroundSSEEvent) => {
          switch (event.type) {
            case "memories":
              setMessages((prev) =>
                prev.map((m) =>
                  m.id === aiMsgId
                    ? { ...m, retrievedMemories: event.retrieved_memories }
                    : m
                )
              );
              const ids = new Set(event.retrieved_memories.map((rm) => rm.id));
              setHighlightMemoryIds(ids);
              break;

            case "content":
              setMessages((prev) =>
                prev.map((m) =>
                  m.id === aiMsgId
                    ? { ...m, content: m.content + event.content }
                    : m
                )
              );
              break;

            case "done":
              setMessages((prev) =>
                prev.map((m) =>
                  m.id === aiMsgId
                    ? { ...m, loading: false, newMemories: event.new_memories }
                    : m
                )
              );
              if (event.new_memories && event.new_memories.length > 0) {
                loadUserMemories();
              }
              break;

            case "error":
              setMessages((prev) =>
                prev.map((m) =>
                  m.id === aiMsgId
                    ? { ...m, content: `⚠️ 错误: ${event.error}`, loading: false }
                    : m
                )
              );
              break;
          }
        },
        controller.signal,
      );
    } catch (err) {
      if (err instanceof DOMException && err.name === "AbortError") {
        setMessages((prev) =>
          prev.map((m) =>
            m.id === aiMsgId
              ? { ...m, content: m.content || "（已取消）", loading: false }
              : m
          )
        );
      } else {
        setMessages((prev) =>
          prev.map((m) =>
            m.id === aiMsgId
              ? {
                  ...m,
                  content: `⚠️ 请求失败: ${err instanceof Error ? err.message : "未知错误"}`,
                  loading: false,
                }
              : m
          )
        );
      }
    } finally {
      setIsGenerating(false);
      abortControllerRef.current = null;
      setTimeout(() => setHighlightMemoryIds(new Set()), 5000);
    }
  };

  const handleStop = () => {
    abortControllerRef.current?.abort();
  };

  const handleClear = () => {
    setMessages([]);
    setHighlightMemoryIds(new Set());
  };

  const handleUserChange = (newUserId: string) => {
    setUserId(newUserId);
    setMessages([]);
    setHighlightMemoryIds(new Set());
  };

  const handleShowMemories = (memories: PlaygroundRetrievedMemory[]) => {
    if (!sidebarOpen) setSidebarOpen(true);
    setHighlightMemoryIds(new Set(memories.map((m) => m.id)));
    setTimeout(() => setHighlightMemoryIds(new Set()), 5000);
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const handleInputChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    setInputValue(e.target.value);
    const textarea = e.target;
    textarea.style.height = "auto";
    textarea.style.height = `${Math.min(textarea.scrollHeight, 150)}px`;
  };

  return (
    <div className="space-y-6">
      {/* 页面标题区域 — 与其他页面统一 */}
      <div>
        <h2 className="text-2xl font-bold tracking-tight">调试台</h2>
        <p className="text-sm text-muted-foreground">
          与 AI 进行记忆增强对话，实时查看记忆的检索与存储过程
        </p>
      </div>

      {/* 对话主体区域 — Card 包裹 */}
      <Card className="overflow-hidden">
        <div className="flex" style={{ height: "calc(100vh - 13rem)" }}>
          {/* 对话区域 */}
          <div className="flex flex-1 flex-col min-w-0">
            {/* 用户选择栏 */}
            <div className="flex items-center justify-between border-b px-4 h-12">
              <div className="flex items-center gap-3">
                <div className="flex items-center gap-2 text-sm">
                  <MessageSquare className="h-4 w-4 text-muted-foreground" />
                  <span className="font-medium text-foreground">对话用户</span>
                </div>
                <Separator orientation="vertical" className="h-5" />
                <UserCombobox
                  value={userId}
                  users={users}
                  onChange={handleUserChange}
                  placeholder="选择用户"
                />
              </div>
              <div className="flex items-center gap-2">
                <Button
                  variant="outline"
                  size="sm"
                  onClick={handleClear}
                  disabled={messages.length === 0}
                  className="h-8 gap-1.5"
                >
                  <Trash2 className="h-3.5 w-3.5" />
                  清空对话
                </Button>
                {!sidebarOpen && (
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => setSidebarOpen(true)}
                    className="h-7 gap-1.5 text-xs"
                  >
                    <PanelRightOpen className="h-3.5 w-3.5" />
                    记忆面板
                  </Button>
                )}
              </div>
            </div>

            {/* 消息列表 */}
            <div
              ref={messagesContainerRef}
              className="relative flex-1 overflow-y-auto"
            >
              {messages.length === 0 ? (
                /* 空状态引导 */
                <div className="flex flex-col items-center justify-center h-full text-center px-4">
                  <div className="flex h-16 w-16 items-center justify-center rounded-2xl bg-primary/10 mb-5">
                    <Sparkles className="h-8 w-8 text-primary" />
                  </div>
                  <h3 className="text-lg font-semibold mb-2">开始对话</h3>
                  <p className="text-sm text-muted-foreground max-w-md mb-8 leading-relaxed">
                    在下方输入消息开始与 AI 对话。AI 会自动记住你说过的重要信息，
                    并在后续对话中运用这些记忆，提供个性化的回复。
                  </p>
                  <div className="grid grid-cols-2 gap-3 max-w-lg">
                    {[
                      "你好，我叫小明，我是一名前端工程师",
                      "我喜欢蓝色，最近在学 React",
                      "帮我推荐一本技术书籍",
                      "我住在北京，喜欢吃火锅",
                    ].map((suggestion) => (
                      <button
                        key={suggestion}
                        className="rounded-xl border bg-card px-4 py-3 text-left text-[13px] text-muted-foreground hover:bg-muted hover:text-foreground hover:border-primary/20 transition-all"
                        onClick={() => {
                          setInputValue(suggestion);
                          inputRef.current?.focus();
                        }}
                      >
                        {suggestion}
                      </button>
                    ))}
                  </div>
                </div>
              ) : (
                <div className="max-w-3xl mx-auto space-y-6 px-6 py-6">
                  {messages.map((msg) => (
                    <MessageBubble
                      key={msg.id}
                      message={msg}
                      onShowMemories={handleShowMemories}
                    />
                  ))}
                  <div ref={messagesEndRef} />
                </div>
              )}

              {/* 滚动到底部按钮 */}
              {showScrollDown && (
                <div className="sticky bottom-4 flex justify-center pointer-events-none">
                  <Button
                    variant="secondary"
                    size="sm"
                    className="rounded-full shadow-lg pointer-events-auto"
                    onClick={scrollToBottom}
                  >
                    <ArrowDown className="mr-1 h-3.5 w-3.5" />
                    回到底部
                  </Button>
                </div>
              )}
            </div>

            {/* 输入区域 */}
            <div className="border-t bg-background px-6 py-4">
              <div className="max-w-3xl mx-auto">
                <div className="flex items-end gap-3 rounded-xl border bg-muted/30 p-2 focus-within:ring-2 focus-within:ring-primary/20 focus-within:border-primary/30 transition-all">
                  <textarea
                    ref={inputRef}
                    value={inputValue}
                    onChange={handleInputChange}
                    onKeyDown={handleKeyDown}
                    placeholder="输入消息... (Enter 发送, Shift+Enter 换行)"
                    className="flex-1 resize-none bg-transparent px-2 py-1.5 text-sm leading-relaxed placeholder:text-muted-foreground/50 focus:outline-none"
                    rows={1}
                    style={{ maxHeight: "120px" }}
                    disabled={isGenerating}
                  />
                  {isGenerating ? (
                    <Button
                      variant="destructive"
                      size="icon"
                      className="h-8 w-8 rounded-lg shrink-0"
                      onClick={handleStop}
                      title="停止生成"
                    >
                      <Square className="h-3 w-3 fill-current" />
                    </Button>
                  ) : (
                    <Button
                      size="icon"
                      className="h-8 w-8 rounded-lg shrink-0"
                      onClick={handleSend}
                      disabled={!inputValue.trim()}
                      title="发送消息"
                    >
                      <Send className="h-3.5 w-3.5" />
                    </Button>
                  )}
                </div>
                <p className="mt-2 text-center text-[11px] text-muted-foreground/40">
                  AI 会自动提取对话中的关键信息作为记忆存储
                </p>
              </div>
            </div>
          </div>

          {/* 记忆侧边栏 */}
          <MemorySidebar
            open={sidebarOpen}
            onToggle={() => setSidebarOpen(false)}
            userMemories={userMemories}
            loadingMemories={loadingMemories}
            onRefresh={loadUserMemories}
            highlightMemoryIds={highlightMemoryIds}
          />
        </div>
      </Card>
    </div>
  );
}
