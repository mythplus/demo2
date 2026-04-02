"use client";

import React, { useEffect, useState, useCallback, useMemo } from "react";
import dynamic from "next/dynamic";
import {
  Search,
  Network,
  CircleDot,
  ArrowRightLeft,
  Trash2,
  RefreshCw,
  Users,
  Filter,
  AlertCircle,
  CheckCircle2,
  Loader2,
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
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  Tabs,
  TabsContent,
  TabsList,
  TabsTrigger,
} from "@/components/ui/tabs";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { mem0Api } from "@/lib/api";
import type {
  GraphData,
  GraphEntity,
  GraphRelation,
  GraphStatsResponse,
  GraphHealthResponse,
} from "@/lib/api";

// 动态导入图谱可视化组件（完全禁用 SSR，避免 window is not defined）
const ForceGraphViewer = dynamic(
  () => import("@/components/graph/force-graph-viewer"),
  {
    ssr: false,
    loading: () => (
      <div className="flex h-full items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
      </div>
    ),
  }
);

// ============ 颜色工具 ============

// 为不同用户分配颜色
const USER_COLORS = [
  "#3b82f6", "#ef4444", "#10b981", "#f59e0b", "#8b5cf6",
  "#ec4899", "#06b6d4", "#f97316", "#14b8a6", "#6366f1",
];

function getUserColor(userId: string | undefined, userList: string[]): string {
  if (!userId) return "#94a3b8";
  const idx = userList.indexOf(userId);
  return idx >= 0 ? USER_COLORS[idx % USER_COLORS.length] : "#94a3b8";
}

// ============ 统计卡片 ============

function StatCard({
  title,
  value,
  icon: Icon,
  description,
}: {
  title: string;
  value: string | number;
  icon: React.ElementType;
  description?: string;
}) {
  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
        <CardTitle className="text-sm font-medium">{title}</CardTitle>
        <Icon className="h-4 w-4 text-muted-foreground" />
      </CardHeader>
      <CardContent>
        <div className="text-2xl font-bold">{value}</div>
        {description && (
          <p className="text-xs text-muted-foreground">{description}</p>
        )}
      </CardContent>
    </Card>
  );
}

// ============ 主页面 ============

export default function GraphMemoryPage() {
  // 状态
  const [graphHealth, setGraphHealth] = useState<GraphHealthResponse | null>(null);
  const [graphStats, setGraphStats] = useState<GraphStatsResponse | null>(null);
  const [graphData, setGraphData] = useState<GraphData | null>(null);
  const [entities, setEntities] = useState<GraphEntity[]>([]);
  const [entitiesTotalCount, setEntitiesTotalCount] = useState(0);
  const [relations, setRelations] = useState<GraphRelation[]>([]);
  const [relationsTotalCount, setRelationsTotalCount] = useState(0);
  const [loading, setLoading] = useState(true);
  const [graphLoading, setGraphLoading] = useState(false);

  // 筛选
  const [selectedUserId, setSelectedUserId] = useState<string>("__all__");
  const [searchQuery, setSearchQuery] = useState("");
  const [entitySearch, setEntitySearch] = useState("");
  const [relationSearch, setRelationSearch] = useState("");

  // 搜索结果
  const [searchResults, setSearchResults] = useState<{
    relations: GraphRelation[];
    isolated_entities: GraphEntity[];
    total: number;
  } | null>(null);
  const [searching, setSearching] = useState(false);

  // 用户列表（从统计数据中提取）
  const userList = useMemo(() => {
    if (!graphStats?.user_entity_distribution) return [];
    return Object.keys(graphStats.user_entity_distribution);
  }, [graphStats]);

  // ============ 数据加载 ============

  const fetchHealth = useCallback(async () => {
    try {
      const health = await mem0Api.graphHealthCheck();
      setGraphHealth(health);
      return health.status === "connected";
    } catch {
      setGraphHealth({ status: "disconnected", message: "无法连接" });
      return false;
    }
  }, []);

  const fetchStats = useCallback(async () => {
    try {
      const stats = await mem0Api.getGraphStats();
      setGraphStats(stats);
    } catch (e) {
      console.error("获取图谱统计失败:", e);
    }
  }, []);

  const fetchGraphData = useCallback(async (userId?: string) => {
    setGraphLoading(true);
    try {
      const data = userId && userId !== "__all__"
        ? await mem0Api.getUserGraph(userId)
        : await mem0Api.getAllGraph();
      setGraphData(data);
    } catch (e) {
      console.error("获取图谱数据失败:", e);
    } finally {
      setGraphLoading(false);
    }
  }, []);

  const fetchEntities = useCallback(async (userId?: string, search?: string) => {
    try {
      const params: any = { limit: 100 };
      if (userId && userId !== "__all__") params.user_id = userId;
      if (search) params.search = search;
      const res = await mem0Api.getGraphEntities(params);
      setEntities(res.entities);
      setEntitiesTotalCount(res.total);
    } catch (e) {
      console.error("获取实体列表失败:", e);
    }
  }, []);

  const fetchRelations = useCallback(async (userId?: string, search?: string) => {
    try {
      const params: any = { limit: 100 };
      if (userId && userId !== "__all__") params.user_id = userId;
      if (search) params.search = search;
      const res = await mem0Api.getGraphRelations(params);
      setRelations(res.relations);
      setRelationsTotalCount(res.total);
    } catch (e) {
      console.error("获取关系列表失败:", e);
    }
  }, []);

  // 初始加载
  useEffect(() => {
    const init = async () => {
      setLoading(true);
      const connected = await fetchHealth();
      if (connected) {
        await Promise.all([
          fetchStats(),
          fetchGraphData(),
          fetchEntities(),
          fetchRelations(),
        ]);
      }
      setLoading(false);
    };
    init();
  }, []);

  // 用户筛选变化时重新加载
  useEffect(() => {
    if (!graphHealth || graphHealth.status !== "connected") return;
    const uid = selectedUserId === "__all__" ? undefined : selectedUserId;
    fetchGraphData(uid);
    fetchEntities(uid, entitySearch);
    fetchRelations(uid, relationSearch);
  }, [selectedUserId]);

  // 刷新全部数据
  const handleRefresh = async () => {
    setLoading(true);
    const uid = selectedUserId === "__all__" ? undefined : selectedUserId;
    await Promise.all([
      fetchStats(),
      fetchGraphData(uid),
      fetchEntities(uid, entitySearch),
      fetchRelations(uid, relationSearch),
    ]);
    setLoading(false);
  };

  // ============ 搜索 ============

  const handleSearch = async () => {
    if (!searchQuery.trim()) {
      setSearchResults(null);
      return;
    }
    setSearching(true);
    try {
      const uid = selectedUserId === "__all__" ? undefined : selectedUserId;
      const res = await mem0Api.searchGraph({
        query: searchQuery,
        user_id: uid,
        limit: 50,
      });
      setSearchResults(res);
    } catch (e) {
      console.error("图谱搜索失败:", e);
    } finally {
      setSearching(false);
    }
  };

  // 实体搜索
  const handleEntitySearch = () => {
    const uid = selectedUserId === "__all__" ? undefined : selectedUserId;
    fetchEntities(uid, entitySearch);
  };

  // 关系搜索
  const handleRelationSearch = () => {
    const uid = selectedUserId === "__all__" ? undefined : selectedUserId;
    fetchRelations(uid, relationSearch);
  };

  // ============ 删除操作 ============

  const handleDeleteEntity = async (entityName: string) => {
    if (!confirm(`确定要删除实体「${entityName}」及其所有关联关系吗？`)) return;
    try {
      const uid = selectedUserId === "__all__" ? undefined : selectedUserId;
      await mem0Api.deleteGraphEntity(entityName, uid);
      handleRefresh();
    } catch (e: any) {
      alert(`删除失败: ${e.message}`);
    }
  };

  const handleDeleteRelation = async (source: string, relation: string, target: string) => {
    if (!confirm(`确定要删除关系「${source} → ${relation} → ${target}」吗？`)) return;
    try {
      await mem0Api.deleteGraphRelation(source, relation, target);
      handleRefresh();
    } catch (e: any) {
      alert(`删除失败: ${e.message}`);
    }
  };

  // ============ 图谱可视化配置 ============

  const graphDataForViz = useMemo(() => {
    if (!graphData) return { nodes: [], links: [] };
    return {
      nodes: graphData.nodes.map((n) => ({
        ...n,
        color: getUserColor(n.user_id, userList),
      })),
      links: graphData.links.map((l) => ({
        ...l,
      })),
    };
  }, [graphData, userList]);

  // ============ 连接断开提示 ============

  if (graphHealth && graphHealth.status !== "connected" && !loading) {
    return (
      <div className="space-y-6">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold">图谱记忆</h1>
            <p className="text-muted-foreground">知识图谱可视化与管理</p>
          </div>
        </div>
        <Card className="border-destructive">
          <CardContent className="flex items-center gap-3 p-6">
            <AlertCircle className="h-5 w-5 text-destructive" />
            <div>
              <p className="font-medium text-destructive">Neo4j 图数据库未连接</p>
              <p className="text-sm text-muted-foreground">
                {graphHealth.message || "请检查 Neo4j 服务是否正常运行"}
              </p>
            </div>
            <Button variant="outline" size="sm" className="ml-auto" onClick={fetchHealth}>
              <RefreshCw className="mr-2 h-4 w-4" />
              重试
            </Button>
          </CardContent>
        </Card>
      </div>
    );
  }

  // ============ 渲染 ============

  return (
    <div className="space-y-6">
      {/* 页面标题 */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">图谱记忆</h1>
          <p className="text-muted-foreground">知识图谱可视化与管理</p>
        </div>
        <div className="flex items-center gap-2">
          {graphHealth?.status === "connected" && (
            <Badge variant="outline" className="text-green-600 border-green-300">
              <CheckCircle2 className="mr-1 h-3 w-3" />
              Neo4j 已连接
            </Badge>
          )}
          <Button variant="outline" size="sm" onClick={handleRefresh} disabled={loading}>
            <RefreshCw className={`mr-2 h-4 w-4 ${loading ? "animate-spin" : ""}`} />
            刷新
          </Button>
        </div>
      </div>

      {/* 统计卡片 */}
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
        <StatCard
          title="实体总数"
          value={loading ? "..." : graphStats?.entity_count ?? 0}
          icon={CircleDot}
          description="知识图谱中的节点数"
        />
        <StatCard
          title="关系总数"
          value={loading ? "..." : graphStats?.relation_count ?? 0}
          icon={ArrowRightLeft}
          description="实体之间的连接数"
        />
        <StatCard
          title="关系类型"
          value={loading ? "..." : Object.keys(graphStats?.relation_type_distribution ?? {}).length}
          icon={Network}
          description="不同的关系类型数量"
        />
        <StatCard
          title="涉及用户"
          value={loading ? "..." : Object.keys(graphStats?.user_entity_distribution ?? {}).length}
          icon={Users}
          description="拥有图谱数据的用户数"
        />
      </div>

      {/* 筛选栏 */}
      <Card>
        <CardContent className="flex items-center gap-4 p-4">
          <Filter className="h-4 w-4 text-muted-foreground" />
          <div className="flex items-center gap-2">
            <span className="text-sm text-muted-foreground">用户筛选:</span>
            <Select value={selectedUserId} onValueChange={setSelectedUserId}>
              <SelectTrigger className="w-[180px]">
                <SelectValue placeholder="全部用户" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="__all__">全部用户</SelectItem>
                {userList.map((uid) => (
                  <SelectItem key={uid} value={uid}>
                    <div className="flex items-center gap-2">
                      <div
                        className="h-2.5 w-2.5 rounded-full"
                        style={{ backgroundColor: getUserColor(uid, userList) }}
                      />
                      {uid}
                    </div>
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className="flex flex-1 items-center gap-2">
            <Input
              placeholder="搜索实体或关系..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && handleSearch()}
              className="max-w-sm"
            />
            <Button size="sm" onClick={handleSearch} disabled={searching}>
              {searching ? (
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              ) : (
                <Search className="mr-2 h-4 w-4" />
              )}
              搜索
            </Button>
            {searchResults && (
              <Button
                size="sm"
                variant="ghost"
                onClick={() => {
                  setSearchResults(null);
                  setSearchQuery("");
                }}
              >
                清除搜索
              </Button>
            )}
          </div>
        </CardContent>
      </Card>

      {/* 搜索结果 */}
      {searchResults && (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">
              搜索结果
              <Badge variant="secondary" className="ml-2">
                {searchResults.total} 条
              </Badge>
            </CardTitle>
          </CardHeader>
          <CardContent>
            {searchResults.relations.length > 0 && (
              <div className="mb-4">
                <h4 className="text-sm font-medium mb-2">关系匹配</h4>
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>源实体</TableHead>
                      <TableHead>关系</TableHead>
                      <TableHead>目标实体</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {searchResults.relations.map((rel, idx) => (
                      <TableRow key={idx}>
                        <TableCell className="font-medium">{rel.source}</TableCell>
                        <TableCell>
                          <Badge variant="outline">{rel.relation}</Badge>
                        </TableCell>
                        <TableCell className="font-medium">{rel.target}</TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </div>
            )}
            {searchResults.isolated_entities.length > 0 && (
              <div>
                <h4 className="text-sm font-medium mb-2">孤立实体</h4>
                <div className="flex flex-wrap gap-2">
                  {searchResults.isolated_entities.map((entity, idx) => (
                    <Badge key={idx} variant="secondary">
                      {entity.name}
                    </Badge>
                  ))}
                </div>
              </div>
            )}
            {searchResults.total === 0 && (
              <p className="text-sm text-muted-foreground text-center py-4">
                未找到匹配的实体或关系
              </p>
            )}
          </CardContent>
        </Card>
      )}

      {/* 图谱可视化 */}
      <Card>
        <CardHeader className="flex flex-row items-center justify-between">
          <div>
            <CardTitle>知识图谱</CardTitle>
            <CardDescription>
              {graphData
                ? `${graphData.node_count} 个节点, ${graphData.link_count} 条关系`
                : "加载中..."}
            </CardDescription>
          </div>
        </CardHeader>
        <CardContent className="p-0">
          <div className="relative h-[500px] w-full border-t">
            {graphLoading ? (
              <div className="flex h-full items-center justify-center">
                <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
              </div>
            ) : graphDataForViz.nodes.length > 0 ? (
              <ForceGraphViewer
                nodes={graphDataForViz.nodes}
                links={graphDataForViz.links}
              />
            ) : (
              <div className="flex h-full flex-col items-center justify-center text-muted-foreground">
                <Network className="mb-3 h-12 w-12 opacity-50" />
                <p className="text-sm">暂无图谱数据</p>
                <p className="text-xs">添加记忆后，系统会自动提取实体和关系</p>
              </div>
            )}
          </div>
          {/* 用户颜色图例 */}
          {userList.length > 0 && (
            <div className="flex flex-wrap items-center gap-3 border-t px-4 py-2">
              <span className="text-xs text-muted-foreground">用户图例:</span>
              {userList.map((uid) => (
                <div key={uid} className="flex items-center gap-1">
                  <div
                    className="h-2.5 w-2.5 rounded-full"
                    style={{ backgroundColor: getUserColor(uid, userList) }}
                  />
                  <span className="text-xs">{uid}</span>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      {/* 实体和关系列表 */}
      <Tabs defaultValue="entities">
        <TabsList>
          <TabsTrigger value="entities">
            <CircleDot className="mr-2 h-4 w-4" />
            实体列表
            <Badge variant="secondary" className="ml-2">
              {entitiesTotalCount}
            </Badge>
          </TabsTrigger>
          <TabsTrigger value="relations">
            <ArrowRightLeft className="mr-2 h-4 w-4" />
            关系列表
            <Badge variant="secondary" className="ml-2">
              {relationsTotalCount}
            </Badge>
          </TabsTrigger>
          <TabsTrigger value="distribution">
            <Network className="mr-2 h-4 w-4" />
            关系类型分布
          </TabsTrigger>
        </TabsList>

        {/* 实体列表 */}
        <TabsContent value="entities">
          <Card>
            <CardHeader>
              <div className="flex items-center justify-between">
                <CardTitle className="text-base">实体列表</CardTitle>
                <div className="flex items-center gap-2">
                  <Input
                    placeholder="搜索实体名称..."
                    value={entitySearch}
                    onChange={(e) => setEntitySearch(e.target.value)}
                    onKeyDown={(e) => e.key === "Enter" && handleEntitySearch()}
                    className="w-[200px]"
                  />
                  <Button size="sm" variant="outline" onClick={handleEntitySearch}>
                    <Search className="h-4 w-4" />
                  </Button>
                </div>
              </div>
            </CardHeader>
            <CardContent>
              {entities.length > 0 ? (
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>实体名称</TableHead>
                      <TableHead>用户</TableHead>
                      <TableHead>标签</TableHead>
                      <TableHead className="text-right">关系数</TableHead>
                      <TableHead className="w-[80px]">操作</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {entities.map((entity, idx) => (
                      <TableRow key={idx}>
                        <TableCell className="font-medium">{entity.name}</TableCell>
                        <TableCell>
                          {entity.user_id ? (
                            <div className="flex items-center gap-1.5">
                              <div
                                className="h-2 w-2 rounded-full"
                                style={{ backgroundColor: getUserColor(entity.user_id, userList) }}
                              />
                              <span className="text-sm">{entity.user_id}</span>
                            </div>
                          ) : (
                            <span className="text-muted-foreground">-</span>
                          )}
                        </TableCell>
                        <TableCell>
                          <div className="flex flex-wrap gap-1">
                            {(entity.labels || []).map((label, i) => (
                              <Badge key={i} variant="outline" className="text-xs">
                                {label}
                              </Badge>
                            ))}
                          </div>
                        </TableCell>
                        <TableCell className="text-right">
                          {entity.relation_count ?? 0}
                        </TableCell>
                        <TableCell>
                          <Button
                            variant="ghost"
                            size="icon"
                            className="h-8 w-8 text-destructive hover:text-destructive"
                            onClick={() => handleDeleteEntity(entity.name)}
                          >
                            <Trash2 className="h-4 w-4" />
                          </Button>
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              ) : (
                <div className="flex flex-col items-center justify-center py-8 text-muted-foreground">
                  <CircleDot className="mb-2 h-8 w-8 opacity-50" />
                  <p className="text-sm">暂无实体数据</p>
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        {/* 关系列表 */}
        <TabsContent value="relations">
          <Card>
            <CardHeader>
              <div className="flex items-center justify-between">
                <CardTitle className="text-base">关系列表</CardTitle>
                <div className="flex items-center gap-2">
                  <Input
                    placeholder="搜索实体名称..."
                    value={relationSearch}
                    onChange={(e) => setRelationSearch(e.target.value)}
                    onKeyDown={(e) => e.key === "Enter" && handleRelationSearch()}
                    className="w-[200px]"
                  />
                  <Button size="sm" variant="outline" onClick={handleRelationSearch}>
                    <Search className="h-4 w-4" />
                  </Button>
                </div>
              </div>
            </CardHeader>
            <CardContent>
              {relations.length > 0 ? (
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>源实体</TableHead>
                      <TableHead>关系</TableHead>
                      <TableHead>目标实体</TableHead>
                      <TableHead>用户</TableHead>
                      <TableHead className="w-[80px]">操作</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {relations.map((rel, idx) => (
                      <TableRow key={idx}>
                        <TableCell className="font-medium">{rel.source}</TableCell>
                        <TableCell>
                          <Badge variant="outline">{rel.relation}</Badge>
                        </TableCell>
                        <TableCell className="font-medium">{rel.target}</TableCell>
                        <TableCell>
                          {(rel.source_user_id || rel.target_user_id) ? (
                            <span className="text-sm">
                              {rel.source_user_id || rel.target_user_id}
                            </span>
                          ) : (
                            <span className="text-muted-foreground">-</span>
                          )}
                        </TableCell>
                        <TableCell>
                          <Button
                            variant="ghost"
                            size="icon"
                            className="h-8 w-8 text-destructive hover:text-destructive"
                            onClick={() =>
                              handleDeleteRelation(rel.source, rel.relation, rel.target)
                            }
                          >
                            <Trash2 className="h-4 w-4" />
                          </Button>
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              ) : (
                <div className="flex flex-col items-center justify-center py-8 text-muted-foreground">
                  <ArrowRightLeft className="mb-2 h-8 w-8 opacity-50" />
                  <p className="text-sm">暂无关系数据</p>
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        {/* 关系类型分布 */}
        <TabsContent value="distribution">
          <Card>
            <CardHeader>
              <CardTitle className="text-base">关系类型分布</CardTitle>
              <CardDescription>各类关系的数量统计</CardDescription>
            </CardHeader>
            <CardContent>
              {graphStats?.relation_type_distribution &&
              Object.keys(graphStats.relation_type_distribution).length > 0 ? (
                <div className="space-y-3">
                  {Object.entries(graphStats.relation_type_distribution)
                    .sort(([, a], [, b]) => b - a)
                    .map(([type, count]) => {
                      const maxCount = Math.max(
                        ...Object.values(graphStats.relation_type_distribution)
                      );
                      const percentage = maxCount > 0 ? (count / maxCount) * 100 : 0;
                      return (
                        <div key={type} className="flex items-center gap-3">
                          <div className="w-[140px] truncate text-sm font-medium" title={type}>
                            {type}
                          </div>
                          <div className="flex-1">
                            <div className="h-6 w-full rounded-full bg-muted">
                              <div
                                className="h-6 rounded-full bg-primary/80 flex items-center justify-end pr-2"
                                style={{ width: `${Math.max(percentage, 5)}%` }}
                              >
                                <span className="text-xs font-medium text-primary-foreground">
                                  {count}
                                </span>
                              </div>
                            </div>
                          </div>
                        </div>
                      );
                    })}
                </div>
              ) : (
                <div className="flex flex-col items-center justify-center py-8 text-muted-foreground">
                  <Network className="mb-2 h-8 w-8 opacity-50" />
                  <p className="text-sm">暂无关系类型数据</p>
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  );
}
