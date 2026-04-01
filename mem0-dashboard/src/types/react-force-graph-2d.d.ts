declare module "react-force-graph-2d" {
  import { Component } from "react";

  interface ForceGraph2DProps {
    graphData?: { nodes: any[]; links: any[] };
    nodeLabel?: string | ((node: any) => string);
    nodeColor?: string | ((node: any) => string);
    nodeRelSize?: number;
    nodeVal?: string | number | ((node: any) => number);
    nodeCanvasObject?: (node: any, ctx: CanvasRenderingContext2D, globalScale: number) => void;
    linkLabel?: string | ((link: any) => string);
    linkColor?: string | ((link: any) => string);
    linkWidth?: number | ((link: any) => number);
    linkDirectionalArrowLength?: number;
    linkDirectionalArrowRelPos?: number;
    linkCurvature?: number;
    onNodeClick?: (node: any, event: MouseEvent) => void;
    onLinkClick?: (link: any, event: MouseEvent) => void;
    cooldownTicks?: number;
    warmupTicks?: number;
    width?: number;
    height?: number;
    backgroundColor?: string;
    ref?: any;
    [key: string]: any;
  }

  const ForceGraph2D: React.ForwardRefExoticComponent<ForceGraph2DProps & React.RefAttributes<any>>;
  export default ForceGraph2D;
}
