"use client";

import React, { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { Brain, Loader2, LogIn } from "lucide-react";
import { useAuthStore } from "@/store/auth-store";
import { loginApi } from "@/lib/api/auth-api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { toast } from "@/hooks/use-toast";

export default function LoginPage() {
  const router = useRouter();
  const { isAuthenticated, setAuth } = useAuthStore();
  const [tenantName, setTenantName] = useState("default");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (isAuthenticated) {
      router.replace("/");
    }
  }, [isAuthenticated, router]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!username || !password) {
      toast({ title: "请输入用户名和密码", variant: "destructive" });
      return;
    }
    setLoading(true);
    try {
      const res = await loginApi({ tenant_name: tenantName, username, password });
      setAuth({
        access_token: res.access_token,
        refresh_token: res.refresh_token,
        user: {
          user_id: res.user.user_id,
          username: res.user.username,
          role: res.user.role,
          tenant_id: res.user.tenant_id,
          tenant_name: res.user.tenant_name,
          tenant_display_name: res.user.tenant_display_name,
        },
      });
      toast({ title: "登录成功" });
      router.replace("/");
    } catch (err) {
      toast({
        title: "登录失败",
        description: err instanceof Error ? err.message : "未知错误",
        variant: "destructive",
      });
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex min-h-screen items-center justify-center bg-gradient-to-br from-slate-50 to-slate-100 dark:from-slate-950 dark:to-slate-900 p-4">
      <Card className="w-full max-w-md">
        <CardHeader className="space-y-3 text-center">
          <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-xl bg-primary text-primary-foreground">
            <Brain className="h-8 w-8" />
          </div>
          <CardTitle className="text-2xl">mem0-dashboard</CardTitle>
          <CardDescription>多租户记忆管理系统</CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSubmit} className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="tenant">租户名称</Label>
              <Input
                id="tenant"
                value={tenantName}
                onChange={(e) => setTenantName(e.target.value)}
                placeholder="default"
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="username">用户名</Label>
              <Input
                id="username"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                placeholder="admin"
                autoComplete="username"
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="password">密码</Label>
              <Input
                id="password"
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="••••••••"
                autoComplete="current-password"
              />
            </div>
            <Button type="submit" className="w-full" disabled={loading}>
              {loading ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  登录中...
                </>
              ) : (
                <>
                  <LogIn className="mr-2 h-4 w-4" />
                  登录
                </>
              )}
            </Button>
          </form>
          <p className="mt-4 text-center text-sm text-muted-foreground">
            默认管理员：admin / admin123456
          </p>
        </CardContent>
      </Card>
    </div>
  );
}
