"use client";

import React, { useState, useEffect, useCallback } from "react";
import {
  Webhook,
  Plus,
  Trash2,
  Pencil,
  ToggleLeft,
  ToggleRight,
  Copy,
  Check,
  X,
  AlertCircle,
  CheckCircle2,
  ExternalLink,
  Clock,
  Loader2,
  RefreshCw,
} from "lucide-react";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Checkbox } from "@/components/ui/checkbox";
import { cn } from "@/lib/utils";
import { mem0Api } from "@/lib/api";

// ============ 类型 ============

interface WebhookConfig {
  id: string;
  name: string;
  url: string;
  enabled: boolean;
  events: string[];
  secret?: string;
  created_at: string;
  last_triggered?: string;
  last_status?: "success" | "failed";
}

// 支持的事件类型
const EVENT_TYPES = [
  { value: "memory.added", label: "记忆新增", description: "当新记忆被创建时触发" },
  { value: "memory.updated", label: "记忆更新", description: "当记忆内容或元数据被修改时触发" },
  { value: "memory.deleted", label: "记忆删除", description: "当记忆被删除时触发" },
  { value: "memory.searched", label: "记忆检索", description: "当执行语义搜索时触发" },
  { value: "user.hard_deleted", label: "用户删除", description: "当用户被删除（永久清除所有数据）时触发" },
];

function generateId(): string {
  return `wh_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`;
}

// ============ 主页面 ============

export default function WebhooksPage() {
  const [webhooks, setWebhooks] = useState<WebhookConfig[]>([]);
  const [loading, setLoading] = useState(true);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [showForm, setShowForm] = useState(false);
  const [copiedId, setCopiedId] = useState<string | null>(null);
  const [testingId, setTestingId] = useState<string | null>(null);
  const [togglingId, setTogglingId] = useState<string | null>(null);

  // 表单状态
  const [formName, setFormName] = useState("");
  const [formUrl, setFormUrl] = useState("");
  const [formEvents, setFormEvents] = useState<string[]>([]);
  const [formSecret, setFormSecret] = useState("");
  const [formError, setFormError] = useState("");
  const [saving, setSaving] = useState(false);

  // 加载列表
  const fetchWebhooks = useCallback(async () => {
    setLoading(true);
    try {
      const res = await mem0Api.getWebhooks();
      setWebhooks(res.webhooks || []);
    } catch {
      setWebhooks([]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchWebhooks();
  }, [fetchWebhooks]);

  // 切换新增表单（展开/收起）
  const handleAdd = () => {
    if (showForm && !editingId) {
      // 当前已打开新增表单，再次点击则收起
      setShowForm(false);
      return;
    }
    setEditingId(null);
    setFormName("");
    setFormUrl("");
    setFormEvents(["memory.added", "memory.updated", "memory.deleted"]);
    setFormSecret("");
    setFormError("");
    setShowForm(true);
  };

  // 打开编辑表单
  const handleEdit = (webhook: WebhookConfig) => {
    setEditingId(webhook.id);
    setFormName(webhook.name);
    setFormUrl(webhook.url);
    setFormEvents([...webhook.events]);
    setFormSecret("");
    setFormError("");
    setShowForm(true);
  };

  // 保存
  const handleSave = async () => {
    if (!formName.trim()) { setFormError("请输入 Webhook 名称"); return; }
    if (!formUrl.trim()) { setFormError("请输入 Webhook URL"); return; }
    try { new URL(formUrl); } catch { setFormError("请输入合法的 URL"); return; }
    // 企业微信 URL 校验：key 参数不能为空
    if (formUrl.includes("qyapi.weixin.qq.com/cgi-bin/webhook/send")) {
      try {
        const urlObj = new URL(formUrl);
        const key = urlObj.searchParams.get("key");
        if (!key || !key.trim()) {
          setFormError("企业微信 Webhook URL 的 key 参数不能为空"); return;
        }
      } catch { /* URL 格式错误已在上方校验 */ }
    }
    if (formEvents.length === 0) { setFormError("请至少选择一个触发事件"); return; }

    setSaving(true);
    try {
      if (editingId) {
        await mem0Api.updateWebhook(editingId, {
          name: formName.trim(),
          url: formUrl.trim(),
          events: formEvents,
          secret: formSecret.trim() || undefined,
        });
      } else {
        await mem0Api.createWebhook({
          id: generateId(),
          name: formName.trim(),
          url: formUrl.trim(),
          enabled: true,
          events: formEvents,
          secret: formSecret.trim() || undefined,
        });
      }
      setShowForm(false);
      fetchWebhooks();
    } catch (err) {
      setFormError(err instanceof Error ? err.message : "保存失败");
    } finally {
      setSaving(false);
    }
  };

  // 删除
  const handleDelete = async (id: string) => {
    try {
      await mem0Api.deleteWebhook(id);
      fetchWebhooks();
    } catch {}
  };

  // 启用/禁用
  const handleToggle = async (id: string) => {
    setTogglingId(id);
    try {
      await mem0Api.toggleWebhook(id);
      fetchWebhooks();
    } catch {}
    setTogglingId(null);
  };

  // 切换事件选择
  const toggleEvent = (event: string) => {
    setFormEvents((prev) =>
      prev.includes(event) ? prev.filter((e) => e !== event) : [...prev, event]
    );
  };

  // 复制 URL
  const handleCopy = (id: string, url: string) => {
    navigator.clipboard.writeText(url);
    setCopiedId(id);
    setTimeout(() => setCopiedId(null), 2000);
  };

  // 测试
  const handleTest = async (id: string) => {
    setTestingId(id);
    try {
      await mem0Api.testWebhook(id);
      fetchWebhooks();
    } catch {}
    setTestingId(null);
  };

  const enabledCount = webhooks.filter((w) => w.enabled).length;

  return (
    <div className="space-y-4">
      {/* 页面头部 */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-bold tracking-tight">Webhooks</h2>
          <p className="text-sm text-muted-foreground">
            配置事件通知，当记忆发生变化时自动推送到指定 URL（支持企业微信群机器人）
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="outline" size="sm" onClick={fetchWebhooks} className="h-8 gap-1.5">
            <RefreshCw className={`h-3.5 w-3.5 ${loading ? "animate-spin" : ""}`} />
            刷新
          </Button>
          <Button size="sm" variant={showForm && !editingId ? "default" : "outline"} onClick={handleAdd}>
            <Plus className="mr-1.5 h-4 w-4" />
            添加 Webhook
          </Button>
        </div>
      </div>

      {/* 统计概览 */}
      <div className="grid gap-3 grid-cols-3">
        <Card>
          <CardContent className="flex items-center gap-3 py-3">
            <Webhook className="h-4 w-4 text-muted-foreground" />
            <div>
              <p className="text-lg font-bold">{webhooks.length}</p>
              <p className="text-xs text-muted-foreground">Webhook 总数</p>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="flex items-center gap-3 py-3">
            <CheckCircle2 className="h-4 w-4 text-emerald-500" />
            <div>
              <p className="text-lg font-bold">{enabledCount}</p>
              <p className="text-xs text-muted-foreground">已启用</p>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="flex items-center gap-3 py-3">
            <AlertCircle className="h-4 w-4 text-muted-foreground" />
            <div>
              <p className="text-lg font-bold">{webhooks.length - enabledCount}</p>
              <p className="text-xs text-muted-foreground">已禁用</p>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* 新增/编辑表单 */}
      {showForm && (
        <Card className="border-primary/30">
          <CardHeader className="pb-3">
            <CardTitle className="text-base">
              {editingId ? "编辑 Webhook" : "添加 Webhook"}
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            {formError && (
              <div className="flex items-center gap-2 text-sm text-destructive bg-destructive/10 rounded-md px-3 py-2">
                <AlertCircle className="h-3.5 w-3.5 shrink-0" />
                {formError}
              </div>
            )}

            <div className="space-y-1.5">
              <label className="text-sm font-medium">名称</label>
              <Input
                placeholder="例如：企微群通知"
                value={formName}
                onChange={(e) => { setFormName(e.target.value); setFormError(""); }}
              />
            </div>

            <div className="space-y-1.5">
              <label className="text-sm font-medium">Webhook URL</label>
              <Input
                placeholder="https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=..."
                value={formUrl}
                onChange={(e) => { setFormUrl(e.target.value); setFormError(""); }}
                autoComplete="off"
              />
            </div>

            <div className="space-y-1.5">
              <label className="text-sm font-medium">签名密钥（可选）</label>
              <Input
                placeholder="用于验证请求的 HMAC 签名（企业微信无需填写）"
                value={formSecret}
                onChange={(e) => setFormSecret(e.target.value)}
                autoComplete="off"
              />
            </div>

            <div className="space-y-2">
              <label className="text-sm font-medium">触发事件</label>
              <div className="grid gap-2 sm:grid-cols-2">
                {EVENT_TYPES.map((event) => (
                  <label
                    key={event.value}
                    className={cn(
                      "flex items-start gap-3 rounded-lg border p-3 cursor-pointer transition-colors",
                      formEvents.includes(event.value)
                        ? "border-primary/50 bg-primary/5"
                        : "hover:bg-muted/50"
                    )}
                  >
                    <Checkbox
                      checked={formEvents.includes(event.value)}
                      onCheckedChange={() => { toggleEvent(event.value); setFormError(""); }}
                      className="mt-0.5"
                    />
                    <div>
                      <p className="text-sm font-medium">{event.label}</p>
                      <p className="text-xs text-muted-foreground">{event.description}</p>
                    </div>
                  </label>
                ))}
              </div>
            </div>

            <div className="flex items-center gap-2 pt-2">
              <Button size="sm" onClick={handleSave} disabled={saving}>
                {saving && <Loader2 className="mr-1.5 h-3.5 w-3.5 animate-spin" />}
                {editingId ? "保存修改" : "创建 Webhook"}
              </Button>
              <Button size="sm" variant="outline" onClick={() => setShowForm(false)}>
                取消
              </Button>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Webhook 列表 */}
      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-lg">Webhook 列表</CardTitle>
        </CardHeader>
        <CardContent>
          {loading ? (
            <div className="flex items-center justify-center py-10">
              <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
            </div>
          ) : webhooks.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-10 text-center">
              <Webhook className="mb-3 h-10 w-10 text-muted-foreground/30" />
              <p className="text-sm text-muted-foreground">暂无 Webhook</p>
              <p className="mt-1 text-xs text-muted-foreground">
                点击「添加 Webhook」创建你的第一个事件通知
              </p>
              <Button size="sm" variant="outline" className="mt-4" onClick={handleAdd}>
                <Plus className="mr-1.5 h-3.5 w-3.5" />
                添加 Webhook
              </Button>
            </div>
          ) : (
            <div className="space-y-3">
              {webhooks.map((webhook) => (
                <div
                  key={webhook.id}
                  className={cn(
                    "rounded-lg border p-5 transition-colors",
                    webhook.enabled ? "hover:bg-muted/30" : "opacity-60"
                  )}
                >
                  {/* 名称 + 状态 + 操作 */}
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2.5">
                      <button
                        onClick={() => handleToggle(webhook.id)}
                        disabled={togglingId === webhook.id}
                        title={webhook.enabled ? "点击禁用" : "点击启用"}
                      >
                        {togglingId === webhook.id ? (
                          <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
                        ) : webhook.enabled ? (
                          <ToggleRight className="h-6 w-6 text-emerald-500" />
                        ) : (
                          <ToggleLeft className="h-6 w-6 text-muted-foreground" />
                        )}
                      </button>
                      <span className="text-base font-semibold">{webhook.name}</span>
                      <Badge variant={webhook.enabled ? "default" : "secondary"} className="text-xs h-5.5 px-2">
                        {webhook.enabled ? "已启用" : "已禁用"}
                      </Badge>
                    </div>
                    <div className="flex items-center gap-1">
                      <Button
                        variant="ghost" size="icon" className="h-8 w-8"
                        onClick={() => handleTest(webhook.id)}
                        disabled={testingId === webhook.id}
                        title="发送测试"
                      >
                        {testingId === webhook.id ? (
                          <Loader2 className="h-4 w-4 animate-spin" />
                        ) : (
                          <ExternalLink className="h-4 w-4" />
                        )}
                      </Button>
                      <Button variant="ghost" size="icon" className="h-8 w-8" onClick={() => handleEdit(webhook)} title="编辑">
                        <Pencil className="h-4 w-4" />
                      </Button>
                      <Button variant="ghost" size="icon" className="h-8 w-8 text-destructive hover:text-destructive" onClick={() => handleDelete(webhook.id)} title="删除">
                        <Trash2 className="h-4 w-4" />
                      </Button>
                    </div>
                  </div>

                  {/* URL */}
                  <div className="mt-3 flex items-center gap-2">
                    <code className="flex-1 truncate text-sm text-muted-foreground bg-muted rounded px-3 py-2">
                      {webhook.url}
                    </code>
                    <Button variant="ghost" size="icon" className="h-7 w-7 shrink-0" onClick={() => handleCopy(webhook.id, webhook.url)} title="复制 URL">
                      {copiedId === webhook.id ? <Check className="h-3.5 w-3.5 text-emerald-500" /> : <Copy className="h-3.5 w-3.5" />}
                    </Button>
                  </div>

                  {/* 事件标签 + 状态 */}
                  <div className="mt-3 flex items-center justify-between">
                    <div className="flex items-center gap-2 flex-wrap">
                      {webhook.events.map((event) => {
                        const info = EVENT_TYPES.find((e) => e.value === event);
                        return (
                          <Badge key={event} variant="outline" className="text-xs font-normal px-2 py-0.5">
                            {info?.label || event}
                          </Badge>
                        );
                      })}
                    </div>
                    <div className="flex items-center gap-2 text-sm text-muted-foreground shrink-0">
                      {webhook.last_triggered && (
                        <span className="flex items-center gap-1.5">
                          <Clock className="h-3.5 w-3.5" />
                          {new Date(webhook.last_triggered).toLocaleString("zh-CN", {
                            month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit",
                          })}
                          {webhook.last_status === "success" && <CheckCircle2 className="h-3.5 w-3.5 text-emerald-500" />}
                          {webhook.last_status === "failed" && <AlertCircle className="h-3.5 w-3.5 text-red-500" />}
                        </span>
                      )}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
