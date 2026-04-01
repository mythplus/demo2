"use client";

import React, { useRef, useEffect, useState } from "react";
import dynamic from "next/dynamic";
import { Loader2 } from "lucide-react";

// 动态导入 ForceGraph2D（完全禁用 SSR，避免 window is not defined）
const ForceGraph2D = dynamic(
  () => import("react-force-graph-2d").then((mod) => mod.default || mod),
  { ssr: false }
);

interface GraphNode {
  id: string;
  name: string;
  user_id?: string;
  color?: string;
  val?: number;
  x?: number;
  y?: number;
}

interface GraphLink {
  source: string;
  target: string;
  relation: string;
  color?: string;
}

interface ForceGraphViewerProps {
  nodes: GraphNode[];
  links: GraphLink[];
  onNodeClick?: (node: GraphNode) => void;
}

export default function ForceGraphViewer({ nodes, links, onNodeClick }: ForceGraphViewerProps) {
  const graphRef = useRef<any>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const [dimensions, setDimensions] = useState({ width: 800, height: 500 });
  const [mounted, setMounted] = useState(false);

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
        nodeLabel={(node: any) =>
          `${node.name}${node.user_id ? ` (${node.user_id})` : ""}`
        }
        nodeColor={(node: any) => node.color || "#94a3b8"}
        nodeRelSize={6}
        nodeVal={(node: any) => Math.max(node.val || 1, 1)}
        linkLabel={(link: any) => link.relation}
        linkColor={(link: any) => link.color || "rgba(156, 163, 175, 0.4)"}
        linkDirectionalArrowLength={4}
        linkDirectionalArrowRelPos={1}
        linkWidth={1.5}
        linkCurvature={0.1}
        nodeCanvasObject={(node: any, ctx: CanvasRenderingContext2D, globalScale: number) => {
          const label = node.name;
          const fontSize = Math.max(12 / globalScale, 2);
          ctx.font = `${fontSize}px Sans-Serif`;
          const nodeR = Math.max(Math.sqrt(node.val || 1) * 4, 4);

          // 绘制节点圆
          ctx.beginPath();
          ctx.arc(node.x, node.y, nodeR, 0, 2 * Math.PI, false);
          ctx.fillStyle = node.color || "#94a3b8";
          ctx.fill();
          ctx.strokeStyle = "rgba(255,255,255,0.8)";
          ctx.lineWidth = 1.5 / globalScale;
          ctx.stroke();

          // 绘制标签
          if (globalScale > 0.6) {
            ctx.textAlign = "center";
            ctx.textBaseline = "middle";
            ctx.fillStyle = "rgba(0,0,0,0.8)";
            ctx.fillText(label, node.x, node.y + nodeR + fontSize);
          }
        }}
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
