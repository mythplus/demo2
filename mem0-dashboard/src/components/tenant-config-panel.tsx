"use client";

import React, { useState, useEffect, useCallback } from "react";
import { Save, RotateCcw, Settings2 } from "lucide-react";
import {
  getTenantConfigApi,
  updateTenantConfigApi,
  deleteTenantConfigApi,
  getEffectiveConfigApi,
  type TenantConfig,
} from "@/lib/api/tenant-config-api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { toast } from "@/hooks/use-toast";

export function TenantConfigPanel({ tenantId }: { tenantId: string }) {
  const [config, setConfig] = useState<TenantConfig | null>(null);
  const [effective, setEffective] = useState<Record<string, unknown> | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  // 编辑态
  const [llmProvider, setLlmProvider] = useState("");
  const [llmConfigJson, setLlmConfigJson] = useState("");
  const [embedderProvider, setEmbedderProvider] = useState("");
  const [embedderConfigJson, setEmbedderConfigJson] = useState("");

  const fetchConfig = useCallback(async () => {
    setLoading(true);
    try {
      const [cfg, eff] = await Promise.all([
        getTenantConfigApi(tenantId),
        getEffectiveConfigApi(tenantId),
      ]);
      setConfig(cfg);
      setEffective(eff);

      // 填充编辑态
      setLlmProvider(cfg.llm_config?.provider || "");
      setLlmConfigJson(
        cfg.llm_config?.config ? JSON.stringify(cfg.llm_config.config, null, 2) : ""
      );
      setEmbedderProvider(cfg.embedder_config?.provider || "");
      setEmbedderConfigJson(
        cfg.embedder_config?.config
          ? JSON.stringify(cfg.embedder_config.config, null, 2)
          : ""
      );
    } catch (err) {
      toast({
        title: "加载配置失败",
        description: err instanceof Error ? err.message : "",
        variant: "destructive",
      });
    } finally {
      setLoading(false);
    }
  }, [tenantId]);

  useEffect(() => {
    fetchConfig();
  }, [fetchConfig]);

  const handleSave = async () => {
    setSaving(true);
    try {
      // 解析 JSON 配置
      let llmConfig: Record<string, unknown> | undefined;
      if (llmConfigJson.trim()) {
        llmConfig = JSON.parse(llmConfigJson);
      }

      let embedderConfig: Record<string, unknown> | undefined;
      if (embedderConfigJson.trim()) {
        embedderConfig = JSON.parse(embedderConfigJson);
      }

      await updateTenantConfigApi(tenantId, {
        llm_config: llmProvider ? { provider: llmProvider, config: llmConfig || {} } : undefined,
        embedder_config: embedderProvider
          ? { provider: embedderProvider, config: embedderConfig || {} }
          : undefined,
      });
      toast({ title: "配置已保存，Memory 实例已刷新" });
      fetchConfig();
    } catch (err) {
      toast({
        title: "保存失败",
        description: err instanceof Error ? err.message : "JSON 格式错误",
        variant: "destructive",
      });
    } finally {
      setSaving(false);
    }
  };

  const handleReset = async () => {
    if (!confirm("确定重置为全局默认配置？")) return;
    try {
      await deleteTenantConfigApi(tenantId);
      toast({ title: "已重置为全局默认配置" });
      fetchConfig();
    } catch (err) {
      toast({
        title: "重置失败",
        description: err instanceof Error ? err.message : "",
        variant: "destructive",
      });
    }
  };

  if (loading) {
    return <div className="py-8 text-center text-muted-foreground">加载中...</div>;
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Settings2 className="h-5 w-5 text-muted-foreground" />
          <h3 className="text-lg font-semibold">租户级配置覆盖</h3>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" size="sm" onClick={handleReset}>
            <RotateCcw className="mr-2 h-4 w-4" />
            重置为默认
          </Button>
          <Button size="sm" onClick={handleSave} disabled={saving}>
            <Save className="mr-2 h-4 w-4" />
            {saving ? "保存中..." : "保存配置"}
          </Button>
        </div>
      </div>

      <div className="grid gap-4 md:grid-cols-2">
        {/* LLM 配置 */}
        <Card>
          <CardHeader>
            <CardTitle className="text-base">LLM 配置覆盖</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            <div className="space-y-2">
              <Label>Provider</Label>
              <Input
                value={llmProvider}
                onChange={(e) => setLlmProvider(e.target.value)}
                placeholder="ollama / openai / anthropic"
              />
            </div>
            <div className="space-y-2">
              <Label>Config (JSON)</Label>
              <Textarea
                value={llmConfigJson}
                onChange={(e) => setLlmConfigJson(e.target.value)}
                placeholder='{"model": "qwen2.5:7b", "ollama_base_url": "http://..."}'
                className="font-mono text-xs"
                rows={6}
              />
            </div>
          </CardContent>
        </Card>

        {/* Embedder 配置 */}
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Embedder 配置覆盖</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            <div className="space-y-2">
              <Label>Provider</Label>
              <Input
                value={embedderProvider}
                onChange={(e) => setEmbedderProvider(e.target.value)}
                placeholder="ollama / openai"
              />
            </div>
            <div className="space-y-2">
              <Label>Config (JSON)</Label>
              <Textarea
                value={embedderConfigJson}
                onChange={(e) => setEmbedderConfigJson(e.target.value)}
                placeholder='{"model": "nomic-embed-text", "ollama_base_url": "http://..."}'
                className="font-mono text-xs"
                rows={6}
              />
            </div>
          </CardContent>
        </Card>
      </div>

      {/* 最终生效配置 */}
      {effective && (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">最终生效配置（只读）</CardTitle>
          </CardHeader>
          <CardContent>
            <pre className="rounded-md border bg-muted p-3 text-xs overflow-x-auto">
              {JSON.stringify(effective, null, 2)}
            </pre>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
