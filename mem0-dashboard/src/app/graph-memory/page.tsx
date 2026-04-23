"use client";

import React, { useEffect, useState, useCallback, useMemo, useRef } from "react";
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
  ZoomIn,
  ZoomOut,
  Maximize,
  Minimize,
  Focus,
  X,
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
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";
import {
  Command,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
} from "@/components/ui/command";
import { Check, ChevronsUpDown } from "lucide-react";
import { mem0Api } from "@/lib/api";
import { DeleteConfirmDialog } from "@/components/memories/delete-confirm-dialog";
import { useToast } from "@/hooks/use-toast";
import type {
  GraphData,
  GraphEntity,
  GraphRelation,
  GraphStatsResponse,
  GraphHealthResponse,
} from "@/lib/api";
import type {
  ForceGraphViewerHandle,
  ForceGraphViewerProps,
} from "@/components/graph/force-graph-viewer";

// 动态导入图谱可视化组件（完全禁用 SSR，避免 window is not defined）
const ForceGraphViewerDynamic = dynamic<ForceGraphViewerProps>(
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

// 包装动态组件以支持 ref 转发
const ForceGraphViewer = React.forwardRef<
  ForceGraphViewerHandle,
  Omit<ForceGraphViewerProps, "forwardedRef">
>(
  (props, ref) => <ForceGraphViewerDynamic {...props} forwardedRef={ref} />
);
ForceGraphViewer.displayName = "ForceGraphViewer";

// ============ 颜色工具 ============

// 图谱内节点颜色调色板（用于在同一用户的图谱内区分不同节点）
const NODE_COLORS = [
  "#3b82f6", "#ef4444", "#10b981", "#f59e0b", "#8b5cf6",
  "#ec4899", "#06b6d4", "#f97316", "#14b8a6", "#6366f1",
  "#f43f5e", "#84cc16", "#22d3ee", "#a855f7", "#fb923c",
];

/** 根据节点索引分配颜色，让图谱内不同节点呈现不同颜色 */
function getNodeColor(index: number): string {
  return NODE_COLORS[index % NODE_COLORS.length];
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
  const [selectedUserId, setSelectedUserId] = useState<string>("");
  const [userComboboxOpen, setUserComboboxOpen] = useState(false);
  const [entitySearch, setEntitySearch] = useState("");
  const [relationSearch, setRelationSearch] = useState("");

  // 实体/关系分页
  const GRAPH_PAGE_SIZE = 50;
  const [entitiesPage, setEntitiesPage] = useState(0);
  const [relationsPage, setRelationsPage] = useState(0);

  // 删除确认弹窗状态
  const [deleteEntityDialogOpen, setDeleteEntityDialogOpen] = useState(false);
  const [deleteEntityName, setDeleteEntityName] = useState("");
  const [deleteEntityLoading, setDeleteEntityLoading] = useState(false);
  const [deleteRelationDialogOpen, setDeleteRelationDialogOpen] = useState(false);
  const [deleteRelationInfo, setDeleteRelationInfo] = useState<{ source: string; relation: string; target: string } | null>(null);
  const [deleteRelationLoading, setDeleteRelationLoading] = useState(false);
  const [deleteUserGraphDialogOpen, setDeleteUserGraphDialogOpen] = useState(false);
  const [deleteUserGraphLoading, setDeleteUserGraphLoading] = useState(false);

  const { toast } = useToast();

  // 图谱可视化 ref（用于缩放控制）
  const graphViewerRef = useRef<ForceGraphViewerHandle>(null);
  const graphContainerRef = useRef<HTMLDivElement>(null);
  const [isFullscreen, setIsFullscreen] = useState(false);

  // 监听全屏状态变化（兼容 Safari webkitfullscreenchange）
  useEffect(() => {
    const handleFullscreenChange = () => {
      setIsFullscreen(!!(document.fullscreenElement || (document as any).webkitFullscreenElement));
    };
    document.addEventListener("fullscreenchange", handleFullscreenChange);
    document.addEventListener("webkitfullscreenchange", handleFullscreenChange);
    return () => {
      document.removeEventListener("fullscreenchange", handleFullscreenChange);
      document.removeEventListener("webkitfullscreenchange", handleFullscreenChange);
    };
  }, []);

  // 全屏切换（兼容 Safari webkitRequestFullscreen / webkitExitFullscreen）
  const toggleFullscreen = useCallback(async () => {
    if (!graphContainerRef.current) return;
    try {
      const el = graphContainerRef.current as any;
      const doc = document as any;
      const isFs = !!(document.fullscreenElement || doc.webkitFullscreenElement);
      if (!isFs) {
        if (el.requestFullscreen) {
          await el.requestFullscreen();
        } else if (el.webkitRequestFullscreen) {
          el.webkitRequestFullscreen();
        }
      } else {
        if (document.exitFullscreen) {
          await document.exitFullscreen();
        } else if (doc.webkitExitFullscreen) {
          doc.webkitExitFullscreen();
        }
      }
    } catch (e) {
      console.error("全屏切换失败:", e);
    }
  }, []);

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
    if (!userId) return;
    setGraphLoading(true);
    try {
      const data = await mem0Api.getUserGraph(userId);
      setGraphData(data);
    } catch (e) {
      console.error("获取图谱数据失败:", e);
    } finally {
      setGraphLoading(false);
    }
  }, []);

  const fetchEntities = useCallback(async (userId?: string, search?: string, offset = 0) => {
    try {
      const params: any = { limit: GRAPH_PAGE_SIZE, offset };
      if (userId) params.user_id = userId;
      if (search) params.search = search;
      const res = await mem0Api.getGraphEntities(params);
      setEntities(res.entities);
      setEntitiesTotalCount(res.total);
    } catch (e) {
      console.error("获取实体列表失败:", e);
    }
  }, []);

  const fetchRelations = useCallback(async (userId?: string, search?: string, offset = 0) => {
    try {
      const params: any = { limit: GRAPH_PAGE_SIZE, offset };
      if (userId) params.user_id = userId;
      if (search) params.search = search;
      const res = await mem0Api.getGraphRelations(params);
      setRelations(res.relations);
      setRelationsTotalCount(res.total);
    } catch (e) {
      console.error("获取关系列表失败:", e);
    }
  }, []);

  // 初始加载（仅加载健康检查和统计数据，不加载图谱）
  useEffect(() => {
    const init = async () => {
      setLoading(true);
      const connected = await fetchHealth();
      if (connected) {
        await fetchStats();
      }
      setLoading(false);
    };
    init();
  }, [fetchHealth, fetchStats]);

  // 用户筛选变化时重新加载（仅在选择了具体用户后才加载）
  useEffect(() => {
    if (!graphHealth || graphHealth.status !== "connected") return;
    if (!selectedUserId) {
      // 未选择用户时清空数据
      setGraphData(null);
      setEntities([]);
      setEntitiesTotalCount(0);
      setRelations([]);
      setRelationsTotalCount(0);
      return;
    }
    fetchGraphData(selectedUserId);
    fetchEntities(selectedUserId, entitySearch);
    fetchRelations(selectedUserId, relationSearch);
  }, [selectedUserId]);

  // 刷新全部数据
  const handleRefresh = async () => {
    setLoading(true);
    const tasks: Promise<any>[] = [fetchStats()];
    if (selectedUserId) {
      tasks.push(
        fetchGraphData(selectedUserId),
        fetchEntities(selectedUserId, entitySearch),
        fetchRelations(selectedUserId, relationSearch),
      );
    }
    await Promise.all(tasks);
    setLoading(false);
  };

  // 实体搜索
  const handleEntitySearch = () => {
    if (!selectedUserId) return;
    fetchEntities(selectedUserId, entitySearch);
  };

  // 关系搜索
  const handleRelationSearch = () => {
    if (!selectedUserId) return;
    fetchRelations(selectedUserId, relationSearch);
  };

  // ============ 删除操作 ============

  const handleDeleteEntityClick = (entityName: string) => {
    setDeleteEntityName(entityName);
    setDeleteEntityDialogOpen(true);
  };

  const handleDeleteEntityConfirm = async () => {
    setDeleteEntityLoading(true);
    try {
      await mem0Api.deleteGraphEntity(deleteEntityName, selectedUserId || undefined);
      setDeleteEntityDialogOpen(false);
      setDeleteEntityName("");
      handleRefresh();
      toast({ title: "删除成功", description: `实体「${deleteEntityName}」已删除` });
    } catch (e: any) {
      toast({ title: "删除失败", description: e.message, variant: "destructive" });
    } finally {
      setDeleteEntityLoading(false);
    }
  };

  const handleDeleteRelationClick = (source: string, relation: string, target: string) => {
    setDeleteRelationInfo({ source, relation, target });
    setDeleteRelationDialogOpen(true);
  };

  const handleDeleteRelationConfirm = async () => {
    if (!deleteRelationInfo) return;
    setDeleteRelationLoading(true);
    try {
      await mem0Api.deleteGraphRelation(deleteRelationInfo.source, deleteRelationInfo.relation, deleteRelationInfo.target);
      setDeleteRelationDialogOpen(false);
      setDeleteRelationInfo(null);
      handleRefresh();
      toast({ title: "删除成功", description: `关系已删除` });
    } catch (e: any) {
      toast({ title: "删除失败", description: e.message, variant: "destructive" });
    } finally {
      setDeleteRelationLoading(false);
    }
  };

  const handleDeleteUserGraphConfirm = async () => {
    if (!selectedUserId) return;
    setDeleteUserGraphLoading(true);
    try {
      const res = await mem0Api.deleteUserGraph(selectedUserId);
      setDeleteUserGraphDialogOpen(false);
      const deletedUser = selectedUserId;
      setSelectedUserId("");
      setGraphData(null);
      setEntities([]);
      setEntitiesTotalCount(0);
      setRelations([]);
      setRelationsTotalCount(0);
      await fetchStats();
      toast({
        title: "删除成功",
        description: `已删除用户「${deletedUser}」的所有图谱数据（${res.deleted_entities} 个实体，${res.deleted_relations} 条关系）`,
      });
    } catch (e: any) {
      toast({ title: "删除失败", description: e.message, variant: "destructive" });
    } finally {
      setDeleteUserGraphLoading(false);
    }
  };

  // ============ 图谱可视化配置 ============

  const graphDataForViz = useMemo(() => {
    if (!graphData) return { nodes: [], links: [] };
    return {
      nodes: graphData.nodes.map((n, index) => ({
        ...n,
        color: getNodeColor(index),
      })),
      // 过滤掉自环线（source 和 target 相同的关系）
      links: graphData.links
        .filter((l) => l.source !== l.target)
        .map((l) => ({
          ...l,
        })),
    };
  }, [graphData]);

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
    <div className="space-y-4">
      {/* 页面标题 */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-bold tracking-tight">图谱记忆</h2>
          <p className="text-muted-foreground">知识图谱可视化与管理</p>
        </div>
        <div className="flex items-center gap-2">
          {graphHealth?.status === "connected" && (
            <Badge variant="outline" className="text-green-600 border-green-600/40 dark:text-green-400 dark:border-green-400/30">
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

      {/* 图谱可视化 */}
      <Card>
        <CardHeader className="flex flex-row items-center gap-4">
          <div>
            <CardTitle>知识图谱</CardTitle>
            <CardDescription>
              {!selectedUserId
                ? "请选择用户以查看图谱"
                : graphData
                  ? `${graphData.node_count} 个节点, ${graphData.link_count} 条关系`
                  : "加载中..."}
            </CardDescription>
          </div>
          <div className="flex items-center gap-2">
            <Popover open={userComboboxOpen} onOpenChange={setUserComboboxOpen}>
              <PopoverTrigger asChild>
                <Button
                  variant="outline"
                  role="combobox"
                  aria-expanded={userComboboxOpen}
                  className="w-[220px] justify-between font-normal"
                >
                  <Filter className="h-4 w-4 shrink-0 text-muted-foreground" />
                  {selectedUserId ? (
                    <span className="flex-1 text-left truncate">{selectedUserId}</span>
                  ) : (
                    <span className="flex-1 text-left text-muted-foreground">选择用户...</span>
                  )}
                  <ChevronsUpDown className="ml-2 h-4 w-4 shrink-0 opacity-50" />
                </Button>
              </PopoverTrigger>
              <PopoverContent className="w-[220px] p-0">
                <Command>
                  <CommandInput placeholder="搜索用户..." />
                  <CommandList>
                    <CommandEmpty>未找到匹配用户</CommandEmpty>
                    <CommandGroup>
                      {userList.map((uid) => (
                        <CommandItem
                          key={uid}
                          value={uid}
                          onSelect={(value) => {
                            setSelectedUserId(value === selectedUserId ? "" : value);
                            setUserComboboxOpen(false);
                          }}
                          className="flex items-center gap-2"
                        >
                          <Check
                            className={`h-4 w-4 shrink-0 ${selectedUserId === uid ? "opacity-100" : "opacity-0"}`}
                          />
                          <span className="truncate">{uid}</span>
                        </CommandItem>
                      ))}
                    </CommandGroup>
                  </CommandList>
                </Command>
              </PopoverContent>
            </Popover>
            {selectedUserId && (
              <>
                <Button
                  variant="outline"
                  size="icon"
                  className="h-9 w-9 shrink-0"
                  onClick={() => setSelectedUserId("")}
                  title="取消选择"
                >
                  <X className="h-4 w-4" />
                </Button>
                <Button
                  variant="outline"
                  size="icon"
                  className="h-9 w-9 shrink-0 text-destructive hover:text-destructive hover:bg-destructive/10"
                  onClick={() => setDeleteUserGraphDialogOpen(true)}
                  title="删除该用户的所有图谱数据"
                >
                  <Trash2 className="h-4 w-4" />
                </Button>
              </>
            )}
          </div>
        </CardHeader>
        <CardContent className="p-0">
          <div
            ref={graphContainerRef}
            className={`relative w-full border-t bg-background ${
              isFullscreen ? "h-screen" : "h-[500px]"
            }`}
          >
            {!selectedUserId ? (
              <div className="flex h-full flex-col items-center justify-center text-muted-foreground">
                <Users className="mb-3 h-12 w-12 opacity-50" />
                <p className="text-sm font-medium">请先选择一个用户</p>
                <p className="text-xs">在上方筛选栏中选择用户后，将加载该用户的知识图谱</p>
              </div>
            ) : graphLoading ? (
              <div className="flex h-full items-center justify-center">
                <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
              </div>
            ) : graphDataForViz.nodes.length > 0 ? (
              <>
                <ForceGraphViewer
                  ref={graphViewerRef}
                  nodes={graphDataForViz.nodes}
                  links={graphDataForViz.links}
                />
                {/* 缩放控制按钮组 */}
                <div className="absolute bottom-4 right-4 flex flex-col gap-1.5 z-10">
                  <Button
                    variant="outline"
                    size="icon"
                    className="h-8 w-8 bg-background/80 backdrop-blur-sm shadow-sm border"
                    onClick={() => graphViewerRef.current?.zoomIn()}
                    title="放大"
                  >
                    <ZoomIn className="h-4 w-4" />
                  </Button>
                  <Button
                    variant="outline"
                    size="icon"
                    className="h-8 w-8 bg-background/80 backdrop-blur-sm shadow-sm border"
                    onClick={() => graphViewerRef.current?.zoomOut()}
                    title="缩小"
                  >
                    <ZoomOut className="h-4 w-4" />
                  </Button>
                  <Button
                    variant="outline"
                    size="icon"
                    className="h-8 w-8 bg-background/80 backdrop-blur-sm shadow-sm border"
                    onClick={() => graphViewerRef.current?.zoomToFit()}
                    title="适应画布"
                  >
                    <Focus className="h-4 w-4" />
                  </Button>
                  <Button
                    variant="outline"
                    size="icon"
                    className="h-8 w-8 bg-background/80 backdrop-blur-sm shadow-sm border"
                    onClick={toggleFullscreen}
                    title={isFullscreen ? "退出全屏" : "全屏"}
                  >
                    {isFullscreen ? (
                      <Minimize className="h-4 w-4" />
                    ) : (
                      <Maximize className="h-4 w-4" />
                    )}
                  </Button>
                </div>
              </>
            ) : (
              <div className="flex h-full flex-col items-center justify-center text-muted-foreground">
                <Network className="mb-3 h-12 w-12 opacity-50" />
                <p className="text-sm">该用户暂无图谱数据</p>
                <p className="text-xs">添加记忆后，系统会自动提取实体和关系</p>
              </div>
            )}
          </div>
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
              <div className="flex items-center gap-4">
                <CardTitle className="text-sm font-semibold">实体列表</CardTitle>
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
                      <TableHead>标签</TableHead>
<TableHead className="whitespace-nowrap">关系数</TableHead>
                      <TableHead className="pl-8">用户</TableHead>
                      <TableHead className="w-[80px]">操作</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {entities.map((entity, idx) => (
                      <TableRow key={idx}>
                        <TableCell className="font-medium">{entity.name}</TableCell>
                        <TableCell>
                          <div className="flex flex-wrap gap-1">
                            {(entity.labels || []).map((label, i) => (
                              <Badge key={i} variant="outline" className="text-xs">
                                {label}
                              </Badge>
                            ))}
                          </div>
                        </TableCell>
<TableCell>
                          {entity.relation_count ?? 0}
                        </TableCell>
                        <TableCell className="pl-8">
                          {entity.user_id ? (
                            <span className="text-sm">{entity.user_id}</span>
                          ) : (
                            <span className="text-muted-foreground">-</span>
                          )}
                        </TableCell>
                        <TableCell>
                          <Button
                            variant="ghost"
                            size="icon"
                            className="h-8 w-8 text-destructive hover:text-destructive"
                            onClick={() => handleDeleteEntityClick(entity.name)}
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
              {/* 实体分页 */}
              {entitiesTotalCount > GRAPH_PAGE_SIZE && (
                <div className="flex items-center justify-end gap-2 pt-4 border-t mt-4">
                  <span className="text-sm text-muted-foreground">
                    {entitiesPage * GRAPH_PAGE_SIZE + 1}-{Math.min((entitiesPage + 1) * GRAPH_PAGE_SIZE, entitiesTotalCount)} / {entitiesTotalCount}
                  </span>
                  <Button variant="outline" size="sm" disabled={entitiesPage <= 0} onClick={() => { const p = entitiesPage - 1; setEntitiesPage(p); fetchEntities(selectedUserId || undefined, entitySearch || undefined, p * GRAPH_PAGE_SIZE); }}>
                    上一页
                  </Button>
                  <Button variant="outline" size="sm" disabled={(entitiesPage + 1) * GRAPH_PAGE_SIZE >= entitiesTotalCount} onClick={() => { const p = entitiesPage + 1; setEntitiesPage(p); fetchEntities(selectedUserId || undefined, entitySearch || undefined, p * GRAPH_PAGE_SIZE); }}>
                    下一页
                  </Button>
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
<CardTitle className="text-sm font-semibold">关系列表</CardTitle>
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
                              handleDeleteRelationClick(rel.source, rel.relation, rel.target)
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
              {/* 关系分页 */}
              {relationsTotalCount > GRAPH_PAGE_SIZE && (
                <div className="flex items-center justify-end gap-2 pt-4 border-t mt-4">
                  <span className="text-sm text-muted-foreground">
                    {relationsPage * GRAPH_PAGE_SIZE + 1}-{Math.min((relationsPage + 1) * GRAPH_PAGE_SIZE, relationsTotalCount)} / {relationsTotalCount}
                  </span>
                  <Button variant="outline" size="sm" disabled={relationsPage <= 0} onClick={() => { const p = relationsPage - 1; setRelationsPage(p); fetchRelations(selectedUserId || undefined, relationSearch || undefined, p * GRAPH_PAGE_SIZE); }}>
                    上一页
                  </Button>
                  <Button variant="outline" size="sm" disabled={(relationsPage + 1) * GRAPH_PAGE_SIZE >= relationsTotalCount} onClick={() => { const p = relationsPage + 1; setRelationsPage(p); fetchRelations(selectedUserId || undefined, relationSearch || undefined, p * GRAPH_PAGE_SIZE); }}>
                    下一页
                  </Button>
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        {/* 关系类型分布 */}
        <TabsContent value="distribution">
          <Card>
            <CardHeader>
<CardTitle className="text-sm font-semibold">关系类型分布</CardTitle>
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

      {/* 删除实体确认弹窗 */}
      <DeleteConfirmDialog
        open={deleteEntityDialogOpen}
        onOpenChange={setDeleteEntityDialogOpen}
        onConfirm={handleDeleteEntityConfirm}
        loading={deleteEntityLoading}
        title="删除实体"
        description={`确定要删除实体「${deleteEntityName}」及其所有关联关系吗？此操作不可撤销。`}
      />

      {/* 删除关系确认弹窗 */}
      <DeleteConfirmDialog
        open={deleteRelationDialogOpen}
        onOpenChange={setDeleteRelationDialogOpen}
        onConfirm={handleDeleteRelationConfirm}
        loading={deleteRelationLoading}
        title="删除关系"
        description={deleteRelationInfo ? `确定要删除关系「${deleteRelationInfo.source} → ${deleteRelationInfo.relation} → ${deleteRelationInfo.target}」吗？此操作不可撤销。` : ""}
      />

      {/* 删除用户图谱确认弹窗 */}
      <DeleteConfirmDialog
        open={deleteUserGraphDialogOpen}
        onOpenChange={setDeleteUserGraphDialogOpen}
        onConfirm={handleDeleteUserGraphConfirm}
        loading={deleteUserGraphLoading}
        title="删除用户图谱"
        description={`确定要删除用户「${selectedUserId}」的所有图谱数据（包括所有实体和关系）吗？此操作不可撤销，但不会影响该用户的记忆数据。`}
      />
    </div>
  );
}
