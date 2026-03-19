"use client";

import Graph from "graphology";
import Sigma from "sigma";
import { useEffect, useRef, useState } from "react";

const NODE_COLORS = {
  User: "#378ADD",
  Group: "#1D9E75",
  Device: "#BA7517",
  Service: "#534AB7",
  Resource: "#888780",
  Agent: "#D85A30",
  AIAgent: "#D4537E"
};

type GraphPayload = {
  nodes: Array<
    Record<string, unknown> & {
      id: string;
      type: keyof typeof NODE_COLORS;
      displayName?: string;
    }
  >;
  edges: Array<{ source: string; target: string; type: string }>;
};

type IdentityGraphProps = {
  highlightId?: string | null;
  onNodeSelect?: (nodeId: string) => void;
};

export function IdentityGraph({ highlightId, onNodeSelect }: IdentityGraphProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const sigmaRef = useRef<Sigma | null>(null);
  const graphRef = useRef<Graph | null>(null);
  const [stats, setStats] = useState({ nodes: 0, edges: 0 });

  useEffect(() => {
    let cancelled = false;

    async function run() {
      if (!containerRef.current) {
        return;
      }

      const graph = new Graph();
      graphRef.current = graph;
      const sigma = new Sigma(graph, containerRef.current, {
        defaultNodeColor: "#888780",
        defaultEdgeColor: "#33506f",
        hideEdgesOnMove: true,
        hideLabelsOnMove: true,
        labelFont: "IBM Plex Mono"
      });
      sigmaRef.current = sigma;
      sigma.on("clickNode", ({ node }) => {
        onNodeSelect?.(node);
      });

      const response = await fetch("/api/graph/overview", { cache: "no-store" });
      const data: GraphPayload = await response.json();

      data.nodes.forEach((node, index) => {
        graph.addNode(node.id, {
          label: node.displayName || node.id,
          size: 8,
          x: Math.cos(index) * 10,
          y: Math.sin(index) * 10,
          color: NODE_COLORS[node.type] || "#888780",
          type: node.type
        });
      });

      data.edges.forEach((edge, index) => {
        graph.addEdgeWithKey(`${edge.source}-${edge.target}-${index}`, edge.source, edge.target, {
          size: 1,
          color: edge.type === "attack_path" ? "#DC2626" : "#33506f"
        });
      });

      if (!cancelled) {
        setStats({ nodes: graph.order, edges: graph.size });
      }
    }

    run().catch(() => undefined);

    return () => {
      cancelled = true;
      sigmaRef.current?.kill();
      sigmaRef.current = null;
      graphRef.current = null;
    };
  }, [onNodeSelect]);

  useEffect(() => {
    const graph = graphRef.current;
    if (!graph) {
      return;
    }

    graph.forEachNode((node) => {
      const nodeType = graph.getNodeAttribute(node, "type") as keyof typeof NODE_COLORS;
      graph.setNodeAttribute(node, "size", node === highlightId ? 14 : 8);
      graph.setNodeAttribute(
        node,
        "color",
        node === highlightId ? "#F97316" : NODE_COLORS[nodeType] || "#888780"
      );
    });
    sigmaRef.current?.refresh();
  }, [highlightId]);

  return (
    <div className="relative h-[24rem] overflow-hidden rounded-2xl border bg-panel/80 shadow-panel">
      <div ref={containerRef} className="h-full w-full" />
      <div className="absolute right-4 top-4 rounded-lg border bg-background/90 px-3 py-2 font-mono text-xs text-muted">
        {stats.nodes.toLocaleString()} nodes | {stats.edges.toLocaleString()} edges
      </div>
      <div className="absolute bottom-4 left-4 rounded-lg border bg-background/90 p-3 text-xs font-mono text-muted">
        {Object.entries(NODE_COLORS).map(([label, color]) => (
          <div key={label} className="flex items-center gap-2">
            <span className="h-3 w-3 rounded-full" style={{ backgroundColor: color }} />
            <span>{label}</span>
          </div>
        ))}
      </div>
    </div>
  );
}
