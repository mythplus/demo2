"use client";

/**
 * 通用三态组件：Loading / Empty / Error
 *
 * 用于统一处理数据加载的三种中间状态，确保每个页面完整覆盖三态。
 */

import React from "react";
import { Loader2, Inbox, AlertCircle, RefreshCw } from "lucide-react";
import { Button } from "@/components/ui/button";

// ============ Loading 状态 ============

interface LoadingStateProps {
  /** 加载提示文本 */
  message?: string;
  /** 自定义图标尺寸 */
  size?: number;
  className?: string;
}

export function LoadingState({
  message = "加载中...",
  size = 32,
  className = "",
}: LoadingStateProps) {
  return (
    <div
      className={`flex flex-col items-center justify-center py-12 text-center ${className}`}
    >
      <Loader2 className="mb-3 text-primary animate-spin" style={{ width: size, height: size }} />
      <p className="text-sm text-muted-foreground">{message}</p>
    </div>
  );
}

// ============ Empty 状态 ============

interface EmptyStateProps {
  /** 空状态提示文本 */
  message?: string;
  /** 副标题描述 */
  description?: string;
  /** 自定义图标 */
  icon?: React.ReactNode;
  /** 操作按钮 */
  action?: React.ReactNode;
  className?: string;
}

export function EmptyState({
  message = "暂无数据",
  description,
  icon,
  action,
  className = "",
}: EmptyStateProps) {
  return (
    <div
      className={`flex flex-col items-center justify-center py-12 text-center ${className}`}
    >
      {icon ?? <Inbox className="mb-4 h-16 w-16 text-muted-foreground/30" />}
      <p className="text-lg font-medium text-muted-foreground">{message}</p>
      {description && (
        <p className="mt-1 text-sm text-muted-foreground">{description}</p>
      )}
      {action && <div className="mt-4">{action}</div>}
    </div>
  );
}

// ============ Error 状态 ============

interface ErrorStateProps {
  /** 错误信息 */
  message?: string;
  /** 重试回调 */
  onRetry?: () => void;
  /** 是否显示重试按钮 */
  showRetry?: boolean;
  className?: string;
}

export function ErrorState({
  message = "加载失败",
  onRetry,
  showRetry = true,
  className = "",
}: ErrorStateProps) {
  return (
    <div
      className={`flex flex-col items-center justify-center py-12 text-center ${className}`}
    >
      <AlertCircle className="mb-4 h-16 w-16 text-destructive/40" />
      <p className="text-lg font-medium text-destructive">{message}</p>
      {showRetry && onRetry && (
        <Button variant="outline" className="mt-4" onClick={onRetry}>
          <RefreshCw className="mr-2 h-4 w-4" />
          重试
        </Button>
      )}
    </div>
  );
}

// ============ 统一三态容器 ============

interface AsyncStateProps {
  loading: boolean;
  error?: string;
  empty?: boolean;
  /** 空状态提示 */
  emptyMessage?: string;
  emptyDescription?: string;
  emptyAction?: React.ReactNode;
  /** 重试回调 */
  onRetry?: () => void;
  /** 加载提示 */
  loadingMessage?: string;
  children: React.ReactNode;
  className?: string;
}

/**
 * 统一三态容器
 *
 * 根据 loading / error / empty 状态自动切换显示内容。
 * 三态都不满足时显示 children。
 *
 * @example
 * <AsyncState loading={loading} error={error} empty={data.length === 0} onRetry={fetchData}>
 *   <DataList data={data} />
 * </AsyncState>
 */
export function AsyncState({
  loading,
  error,
  empty,
  emptyMessage,
  emptyDescription,
  emptyAction,
  onRetry,
  loadingMessage,
  children,
  className = "",
}: AsyncStateProps) {
  if (loading) {
    return <LoadingState message={loadingMessage} className={className} />;
  }

  if (error) {
    return (
      <ErrorState message={error} onRetry={onRetry} className={className} />
    );
  }

  if (empty) {
    return (
      <EmptyState
        message={emptyMessage}
        description={emptyDescription}
        action={emptyAction}
        className={className}
      />
    );
  }

  return <>{children}</>;
}
