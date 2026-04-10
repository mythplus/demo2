"use client";

import React, { useRef, useEffect, useState, useCallback, useImperativeHandle, forwardRef } from "react";
import ForceGraph2D from "react-force-graph-2d";
import { Loader2 } from "lucide-react";

export interface GraphNode {
  id: string;
  name: string;
  user_id?: string;
  color?: string;
  val?: number;
  x?: number;
  y?: number;
}

export interface GraphLink {
  source: string;
  target: string;
  relation: string;
  color?: string;
}

export interface ForceGraphViewerProps {
  nodes: GraphNode[];
  links: GraphLink[];
  onNodeClick?: (node: GraphNode) => void;
  forwardedRef?: React.Ref<ForceGraphViewerHandle>;
}

/** 暴露给父组件的控制方法 */
export interface ForceGraphViewerHandle {
  zoomIn: () => void;
  zoomOut: () => void;
  zoomToFit: () => void;
  centerGraph: () => void;
}

const ForceGraphViewer = forwardRef<ForceGraphViewerHandle, ForceGraphViewerProps>(
  ({ nodes, links, onNodeClick, forwardedRef }, ref) => {
  const graphRef = useRef<any>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const [dimensions, setDimensions] = useState({ width: 800, height: 500 });
  const [mounted, setMounted] = useState(false);
  const [isDark, setIsDark] = useState(false);

  // 优先使用 forwardedRef（通过 dynamic 包装传入），否则使用 forwardRef 的 ref
  const effectiveRef = forwardedRef || ref;

  // 暴露缩放控制方法给父组件
  useImperativeHandle(effectiveRef, () => ({
    zoomIn: () => {
      if (graphRef.current) {
        const currentZoom = graphRef.current.zoom();
        graphRef.current.zoom(currentZoom * 1.5, 300);
      }
    },
    zoomOut: () => {
      if (graphRef.current) {
        const currentZoom = graphRef.current.zoom();
        graphRef.current.zoom(currentZoom / 1.5, 300);
      }
    },
    zoomToFit: () => {
      if (graphRef.current) {
        graphRef.current.zoomToFit(400, 40);
      }
    },
    centerGraph: () => {
      if (graphRef.current) {
        graphRef.current.centerAt(0, 0, 300);
        graphRef.current.zoomToFit(400, 40);
      }
    },
  }));

  // 检测深色模式
  useEffect(() => {
    const checkDark = () => {
      setIsDark(document.documentElement.classList.contains("dark"));
    };
    checkDark();

    // 监听 class 变化以响应主题切换
    const observer = new MutationObserver(() => checkDark());
    observer.observe(document.documentElement, {
      attributes: true,
      attributeFilter: ["class"],
    });
    return () => observer.disconnect();
  }, []);

  // 确保只在客户端渲染
  useEffect(() => {
    setMounted(true);
  }, []);

  // 监听容器尺寸变化
  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;

    const observer = new ResizeObserver((entries) => {
      for (const entry of entries) {
        setDimensions({
          width: entry.contentRect.width,
          height: entry.contentRect.height,
        });
      }
    });
    observer.observe(container);
    setDimensions({
      width: container.clientWidth,
      height: container.clientHeight,
    });

    return () => observer.disconnect();
  }, [mounted]);

  // 根据主题动态计算颜色
  const labelColor = isDark ? "rgba(255,255,255,0.9)" : "rgba(0,0,0,0.8)";
  const linkDefaultColor = isDark ? "rgba(140,160,200,0.6)" : "rgba(156,163,175,0.4)";
  const nodeStrokeColor = isDark ? "rgba(255,255,255,0.6)" : "rgba(255,255,255,0.8)";
  const linkLabelColor = isDark ? "rgba(200,210,230,0.85)" : "rgba(80,80,80,0.7)";
  const bgColor = isDark ? "#0a0f1a" : "#ffffff";

  // Canvas 自定义绘制节点
  const paintNode = useCallback((node: any, ctx: CanvasRenderingContext2D, globalScale: number) => {
    const label = node.name;
    const fontSize = Math.max(12 / globalScale, 2);
    ctx.font = `${fontSize}px Sans-Serif`;
    const nodeR = Math.max(Math.sqrt(node.val || 1) * 4, 4);

    // 绘制节点圆
    ctx.beginPath();
    ctx.arc(node.x, node.y, nodeR, 0, 2 * Math.PI, false);
    ctx.fillStyle = node.color || "#94a3b8";
    ctx.fill();
    ctx.strokeStyle = nodeStrokeColor;
    ctx.lineWidth = 1.5 / globalScale;
    ctx.stroke();

    // 绘制标签
    if (globalScale > 0.6) {
      ctx.textAlign = "center";
      ctx.textBaseline = "middle";
      ctx.fillStyle = labelColor;
      ctx.fillText(label, node.x, node.y + nodeR + fontSize);
    }
  }, [labelColor, nodeStrokeColor]);

  // Canvas 自定义绘制连线标签
  const paintLinkLabel = useCallback((link: any, ctx: CanvasRenderingContext2D, globalScale: number) => {
    if (globalScale < 1.2) return; // 缩放较小时不显示关系标签
    const relation = link.relation;
    if (!relation) return;

    const start = link.source;
    const end = link.target;
    if (typeof start !== "object" || typeof end !== "object") return;

    const midX = (start.x + end.x) / 2;
    const midY = (start.y + end.y) / 2;
    const fontSize = Math.max(10 / globalScale, 1.5);

    ctx.font = `${fontSize}px Sans-Serif`;
    ctx.textAlign = "center";
    ctx.textBaseline = "middle";

    // 绘制标签背景
    const textWidth = ctx.measureText(relation).width;
    const padding = 2 / globalScale;
    ctx.fillStyle = isDark ? "rgba(15,23,42,0.85)" : "rgba(255,255,255,0.85)";
    ctx.fillRect(
      midX - textWidth / 2 - padding,
      midY - fontSize / 2 - padding,
      textWidth + padding * 2,
      fontSize + padding * 2
    );

    ctx.fillStyle = linkLabelColor;
    ctx.fillText(relation, midX, midY);
  }, [isDark, linkLabelColor]);

  if (!mounted) {
    return (
      <div className="flex h-full items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
      </div>
    );
  }

  return (
    <div ref={containerRef} className="h-full w-full">
      <ForceGraph2D
        ref={graphRef}
        graphData={{ nodes, links }}
        backgroundColor={bgColor}
        nodeLabel={(node: any) =>
          `${node.name}${node.user_id ? ` (${node.user_id})` : ""}`
        }
        nodeColor={(node: any) => node.color || "#94a3b8"}
        nodeRelSize={6}
        nodeVal={(node: any) => Math.max(node.val || 1, 1)}
        linkLabel={(link: any) => link.relation}
        linkColor={(link: any) => link.color || linkDefaultColor}
        linkDirectionalArrowLength={4}
        linkDirectionalArrowRelPos={1}
        linkDirectionalArrowColor={(link: any) => link.color || (isDark ? "rgba(160,180,220,0.8)" : "rgba(120,130,140,0.6)")}
        linkWidth={1.5}
        linkCurvature={0.1}
        nodeCanvasObject={paintNode}
        linkCanvasObjectMode={() => "after"}
        linkCanvasObject={paintLinkLabel}
        onNodeClick={(node: any) => {
          if (onNodeClick) onNodeClick(node);
          if (graphRef.current) {
            graphRef.current.centerAt(node.x, node.y, 500);
            graphRef.current.zoom(3, 500);
          }
        }}
        cooldownTicks={100}
        warmupTicks={50}
        width={dimensions.width || 800}
        height={dimensions.height || 500}
      />
    </div>
  );
  }
);

ForceGraphViewer.displayName = "ForceGraphViewer";

export default ForceGraphViewer;
