"use client";

import React, { useState, useEffect, useCallback } from "react";
import { Plus, Building2, Trash2, RefreshCw } from "lucide-react";
import {
  listTenantsApi,
  createTenantApi,
  deleteTenantApi,
  type Tenant,
} from "@/lib/api/tenant-api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
  DialogTrigger,
} from "@/components/ui/dialog";
import { toast } from "@/hooks/use-toast";
import Link from "next/link";

export default function TenantsPage() {
  const [tenants, setTenants] = useState<Tenant[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(false);
  const [createOpen, setCreateOpen] = useState(false);
  const [newName, setNewName] = useState("");
  const [newDisplayName, setNewDisplayName] = useState("");

  const fetchTenants = useCallback(async () => {
    setLoading(true);
    try {
      const res = await listTenantsApi(0, 100);
      setTenants(res.items);
      setTotal(res.total);
    } catch (err) {
      toast({
        title: "获取租户列表失败",
        description: err instanceof Error ? err.message : "",
        variant: "destructive",
      });
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchTenants();
  }, [fetchTenants]);

  const handleCreate = async () => {
    if (!newName.trim()) {
      toast({ title: "请输入租户名称", variant: "destructive" });
      return;
    }
    try {
      await createTenantApi({ name: newName, display_name: newDisplayName });
      toast({ title: "租户创建成功" });
      setCreateOpen(false);
      setNewName("");
      setNewDisplayName("");
      fetchTenants();
    } catch (err) {
      toast({
        title: "创建失败",
        description: err instanceof Error ? err.message : "",
        variant: "destructive",
      });
    }
  };

  const handleDelete = async (id: string, name: string) => {
    if (!confirm(`确定删除租户 "${name}"？此操作不可恢复。`)) return;
    try {
      await deleteTenantApi(id);
      toast({ title: "租户已删除" });
      fetchTenants();
    } catch (err) {
      toast({
        title: "删除失败",
        description: err instanceof Error ? err.message : "",
        variant: "destructive",
      });
    }
  };

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold">租户管理</h2>
          <p className="text-sm text-muted-foreground">共 {total} 个租户</p>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" size="sm" onClick={fetchTenants} disabled={loading}>
            <RefreshCw className="mr-2 h-4 w-4" />
            刷新
          </Button>
          <Dialog open={createOpen} onOpenChange={setCreateOpen}>
            <DialogTrigger asChild>
              <Button size="sm">
                <Plus className="mr-2 h-4 w-4" />
                新建租户
              </Button>
            </DialogTrigger>
            <DialogContent>
              <DialogHeader>
                <DialogTitle>新建租户</DialogTitle>
              </DialogHeader>
              <div className="space-y-4 py-4">
                <div className="space-y-2">
                  <Label>租户名称（唯一标识）</Label>
                  <Input
                    value={newName}
                    onChange={(e) => setNewName(e.target.value)}
                    placeholder="my-company"
                  />
                </div>
                <div className="space-y-2">
                  <Label>显示名称</Label>
                  <Input
                    value={newDisplayName}
                    onChange={(e) => setNewDisplayName(e.target.value)}
                    placeholder="我的公司"
                  />
                </div>
              </div>
              <DialogFooter>
                <Button variant="outline" onClick={() => setCreateOpen(false)}>
                  取消
                </Button>
                <Button onClick={handleCreate}>创建</Button>
              </DialogFooter>
            </DialogContent>
          </Dialog>
        </div>
      </div>

      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
        {tenants.map((tenant) => (
          <Card key={tenant.id} className="hover:shadow-md transition-shadow">
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <div className="flex items-center gap-2">
                <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary/10">
                  <Building2 className="h-4 w-4 text-primary" />
                </div>
                <CardTitle className="text-base">
                  <Link href={`/tenants/${tenant.id}`} className="hover:underline">
                    {tenant.display_name || tenant.name}
                  </Link>
                </CardTitle>
              </div>
              <Button
                variant="ghost"
                size="icon"
                className="h-8 w-8 text-red-500"
                onClick={() => handleDelete(tenant.id, tenant.name)}
              >
                <Trash2 className="h-4 w-4" />
              </Button>
            </CardHeader>
            <CardContent>
              <div className="space-y-1 text-sm">
                <div className="flex justify-between">
                  <span className="text-muted-foreground">标识</span>
                  <span className="font-mono">{tenant.name}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-muted-foreground">套餐</span>
                  <span className="badge">{tenant.plan}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-muted-foreground">状态</span>
                  <span className={tenant.status === "active" ? "text-green-600" : "text-red-600"}>
                    {tenant.status}
                  </span>
                </div>
                {tenant.usage && (
                  <div className="flex justify-between">
                    <span className="text-muted-foreground">今日API调用</span>
                    <span>{tenant.usage.today_api_call_count}</span>
                  </div>
                )}
              </div>
            </CardContent>
          </Card>
        ))}
      </div>

      {tenants.length === 0 && !loading && (
        <div className="text-center py-12 text-muted-foreground">
          暂无租户，点击"新建租户"创建
        </div>
      )}
    </div>
  );
}
