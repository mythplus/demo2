"use client";

import React, { useState, useEffect, useCallback } from "react";
import { useParams, useRouter } from "next/navigation";
import { ArrowLeft, Plus, Trash2, Key, Users as UsersIcon, Settings2 } from "lucide-react";
import {
  getTenantApi,
  listTenantUsersApi,
  createTenantUserApi,
  deleteTenantUserApi,
  listApiKeysApi,
  createApiKeyApi,
  deleteApiKeyApi,
  type Tenant,
  type TenantUser,
  type ApiKey,
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
  Tabs,
  TabsContent,
  TabsList,
  TabsTrigger,
} from "@/components/ui/tabs";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
  DialogTrigger,
} from "@/components/ui/dialog";
import { toast } from "@/hooks/use-toast";
import { TenantConfigPanel } from "@/components/tenant-config-panel";

export default function TenantDetailPage() {
  const params = useParams();
  const router = useRouter();
  const tenantId = params.id as string;

  const [tenant, setTenant] = useState<Tenant | null>(null);
  const [users, setUsers] = useState<TenantUser[]>([]);
  const [apiKeys, setApiKeys] = useState<ApiKey[]>([]);
  const [loading, setLoading] = useState(true);

  // 创建用户对话框
  const [userDialogOpen, setUserDialogOpen] = useState(false);
  const [newUsername, setNewUsername] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [newRole, setNewRole] = useState("member");

  // 创建 API Key 对话框
  const [keyDialogOpen, setKeyDialogOpen] = useState(false);
  const [newKeyName, setNewKeyName] = useState("");
  const [createdKey, setCreatedKey] = useState<string | null>(null);

  const fetchAll = useCallback(async () => {
    setLoading(true);
    try {
      const [t, u, k] = await Promise.all([
        getTenantApi(tenantId),
        listTenantUsersApi(tenantId),
        listApiKeysApi(tenantId),
      ]);
      setTenant(t);
      setUsers(u);
      setApiKeys(k);
    } catch (err) {
      toast({
        title: "加载失败",
        description: err instanceof Error ? err.message : "",
        variant: "destructive",
      });
    } finally {
      setLoading(false);
    }
  }, [tenantId]);

  useEffect(() => {
    fetchAll();
  }, [fetchAll]);

  const handleCreateUser = async () => {
    if (!newUsername || !newPassword) {
      toast({ title: "请填写用户名和密码", variant: "destructive" });
      return;
    }
    try {
      await createTenantUserApi(tenantId, {
        username: newUsername,
        password: newPassword,
        role: newRole,
      });
      toast({ title: "用户创建成功" });
      setUserDialogOpen(false);
      setNewUsername("");
      setNewPassword("");
      setNewRole("member");
      fetchAll();
    } catch (err) {
      toast({
        title: "创建失败",
        description: err instanceof Error ? err.message : "",
        variant: "destructive",
      });
    }
  };

  const handleDeleteUser = async (userId: string, username: string) => {
    if (!confirm(`确定删除用户 "${username}"？`)) return;
    try {
      await deleteTenantUserApi(tenantId, userId);
      toast({ title: "用户已删除" });
      fetchAll();
    } catch (err) {
      toast({
        title: "删除失败",
        description: err instanceof Error ? err.message : "",
        variant: "destructive",
      });
    }
  };

  const handleCreateKey = async () => {
    if (!newKeyName.trim()) {
      toast({ title: "请输入名称", variant: "destructive" });
      return;
    }
    try {
      const result = await createApiKeyApi(tenantId, newKeyName);
      setCreatedKey(result.raw_key || null);
      toast({ title: "API Key 创建成功" });
      setNewKeyName("");
      fetchAll();
    } catch (err) {
      toast({
        title: "创建失败",
        description: err instanceof Error ? err.message : "",
        variant: "destructive",
      });
    }
  };

  const handleDeleteKey = async (keyId: string, name: string) => {
    if (!confirm(`确定删除 API Key "${name}"？`)) return;
    try {
      await deleteApiKeyApi(tenantId, keyId);
      toast({ title: "API Key 已删除" });
      fetchAll();
    } catch (err) {
      toast({
        title: "删除失败",
        description: err instanceof Error ? err.message : "",
        variant: "destructive",
      });
    }
  };

  if (loading || !tenant) {
    return <div className="flex items-center justify-center py-12">加载中...</div>;
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-4">
        <Button variant="ghost" size="icon" onClick={() => router.push("/tenants")}>
          <ArrowLeft className="h-5 w-5" />
        </Button>
        <div>
          <h2 className="text-2xl font-bold">{tenant.display_name || tenant.name}</h2>
          <p className="text-sm text-muted-foreground">
            ID: {tenant.id} · 套餐: {tenant.plan} · 状态: {tenant.status}
          </p>
        </div>
      </div>

      {tenant.usage && (
        <div className="grid gap-4 md:grid-cols-3">
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm text-muted-foreground">今日记忆写入</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">{tenant.usage.today_memory_count}</div>
            </CardContent>
          </Card>
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm text-muted-foreground">今日API调用</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">{tenant.usage.today_api_call_count}</div>
              <div className="text-xs text-muted-foreground">
                上限: {tenant.max_api_calls_per_day}
              </div>
            </CardContent>
          </Card>
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm text-muted-foreground">总API调用</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">{tenant.usage.total_api_call_count}</div>
            </CardContent>
          </Card>
        </div>
      )}

      <Tabs defaultValue="users">
        <TabsList>
          <TabsTrigger value="users">
            <UsersIcon className="mr-2 h-4 w-4" />
            用户管理
          </TabsTrigger>
          <TabsTrigger value="keys">
            <Key className="mr-2 h-4 w-4" />
            API Key
          </TabsTrigger>
          <TabsTrigger value="config">
            <Settings2 className="mr-2 h-4 w-4" />
            配置覆盖
          </TabsTrigger>
        </TabsList>

        {/* 用户管理 Tab */}
        <TabsContent value="users" className="space-y-4">
          <div className="flex justify-end">
            <Dialog open={userDialogOpen} onOpenChange={setUserDialogOpen}>
              <DialogTrigger asChild>
                <Button size="sm">
                  <Plus className="mr-2 h-4 w-4" />
                  添加用户
                </Button>
              </DialogTrigger>
              <DialogContent>
                <DialogHeader>
                  <DialogTitle>添加用户</DialogTitle>
                </DialogHeader>
                <div className="space-y-4 py-4">
                  <div className="space-y-2">
                    <Label>用户名</Label>
                    <Input value={newUsername} onChange={(e) => setNewUsername(e.target.value)} />
                  </div>
                  <div className="space-y-2">
                    <Label>密码</Label>
                    <Input
                      type="password"
                      value={newPassword}
                      onChange={(e) => setNewPassword(e.target.value)}
                    />
                  </div>
                  <div className="space-y-2">
                    <Label>角色</Label>
                    <select
                      className="w-full rounded-md border bg-background px-3 py-2"
                      value={newRole}
                      onChange={(e) => setNewRole(e.target.value)}
                    >
                      <option value="member">member</option>
                      <option value="admin">admin</option>
                    </select>
                  </div>
                </div>
                <DialogFooter>
                  <Button variant="outline" onClick={() => setUserDialogOpen(false)}>取消</Button>
                  <Button onClick={handleCreateUser}>创建</Button>
                </DialogFooter>
              </DialogContent>
            </Dialog>
          </div>
          <Card>
            <CardContent className="p-0">
              <table className="w-full text-sm">
                <thead className="border-b">
                  <tr>
                    <th className="px-4 py-3 text-left font-medium">用户名</th>
                    <th className="px-4 py-3 text-left font-medium">角色</th>
                    <th className="px-4 py-3 text-left font-medium">状态</th>
                    <th className="px-4 py-3 text-left font-medium">创建时间</th>
                    <th className="px-4 py-3 text-right font-medium">操作</th>
                  </tr>
                </thead>
                <tbody>
                  {users.map((u) => (
                    <tr key={u.id} className="border-b last:border-0">
                      <td className="px-4 py-3">{u.username}</td>
                      <td className="px-4 py-3">{u.role}</td>
                      <td className="px-4 py-3">
                        <span className={u.status === "active" ? "text-green-600" : "text-red-600"}>
                          {u.status}
                        </span>
                      </td>
                      <td className="px-4 py-3 text-muted-foreground">{u.created_at}</td>
                      <td className="px-4 py-3 text-right">
                        <Button
                          variant="ghost"
                          size="icon"
                          className="h-8 w-8 text-red-500"
                          onClick={() => handleDeleteUser(u.id, u.username)}
                        >
                          <Trash2 className="h-4 w-4" />
                        </Button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
              {users.length === 0 && (
                <div className="py-8 text-center text-muted-foreground">暂无用户</div>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        {/* API Key Tab */}
        <TabsContent value="keys" className="space-y-4">
          <div className="flex justify-end">
            <Dialog open={keyDialogOpen} onOpenChange={(v) => { setKeyDialogOpen(v); if (!v) setCreatedKey(null); }}>
              <DialogTrigger asChild>
                <Button size="sm">
                  <Plus className="mr-2 h-4 w-4" />
                  生成 API Key
                </Button>
              </DialogTrigger>
              <DialogContent>
                <DialogHeader>
                  <DialogTitle>生成 API Key</DialogTitle>
                </DialogHeader>
                {createdKey ? (
                  <div className="space-y-4 py-4">
                    <div className="rounded-md border border-yellow-300 bg-yellow-50 p-3 text-sm dark:bg-yellow-950">
                      ⚠️ 此 Key 仅显示一次，请立即复制保存！
                    </div>
                    <div className="rounded-md border bg-muted p-3 font-mono text-sm break-all">
                      {createdKey}
                    </div>
                    <Button
                      variant="outline"
                      className="w-full"
                      onClick={() => navigator.clipboard.writeText(createdKey)}
                    >
                      复制到剪贴板
                    </Button>
                  </div>
                ) : (
                  <div className="space-y-4 py-4">
                    <div className="space-y-2">
                      <Label>名称</Label>
                      <Input
                        value={newKeyName}
                        onChange={(e) => setNewKeyName(e.target.value)}
                        placeholder="production-key"
                      />
                    </div>
                  </div>
                )}
                <DialogFooter>
                  {!createdKey && (
                    <>
                      <Button variant="outline" onClick={() => setKeyDialogOpen(false)}>取消</Button>
                      <Button onClick={handleCreateKey}>生成</Button>
                    </>
                  )}
                  {createdKey && (
                    <Button onClick={() => setKeyDialogOpen(false)}>完成</Button>
                  )}
                </DialogFooter>
              </DialogContent>
            </Dialog>
          </div>
          <Card>
            <CardContent className="p-0">
              <table className="w-full text-sm">
                <thead className="border-b">
                  <tr>
                    <th className="px-4 py-3 text-left font-medium">名称</th>
                    <th className="px-4 py-3 text-left font-medium">Key 前缀</th>
                    <th className="px-4 py-3 text-left font-medium">状态</th>
                    <th className="px-4 py-3 text-left font-medium">最后使用</th>
                    <th className="px-4 py-3 text-right font-medium">操作</th>
                  </tr>
                </thead>
                <tbody>
                  {apiKeys.map((k) => (
                    <tr key={k.id} className="border-b last:border-0">
                      <td className="px-4 py-3">{k.name}</td>
                      <td className="px-4 py-3 font-mono text-muted-foreground">{k.key_prefix}...</td>
                      <td className="px-4 py-3">
                        <span className="text-green-600">{k.status}</span>
                      </td>
                      <td className="px-4 py-3 text-muted-foreground">{k.last_used_at || "未使用"}</td>
                      <td className="px-4 py-3 text-right">
                        <Button
                          variant="ghost"
                          size="icon"
                          className="h-8 w-8 text-red-500"
                          onClick={() => handleDeleteKey(k.id, k.name)}
                        >
                          <Trash2 className="h-4 w-4" />
                        </Button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
              {apiKeys.length === 0 && (
                <div className="py-8 text-center text-muted-foreground">暂无 API Key</div>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        {/* 配置覆盖 Tab */}
        <TabsContent value="config">
          <TenantConfigPanel tenantId={tenant.id} />
        </TabsContent>
      </Tabs>
    </div>
  );
}
