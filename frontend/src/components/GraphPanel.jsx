import { useMemo, useCallback, useState, useEffect } from "react";
import {
  ReactFlow,
  Background,
  Controls,
  MiniMap,
  useNodesState,
  useEdgesState,
  MarkerType,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import CustomNode from "./CustomNode";

// Color map for node types
const LABEL_COLORS = {
  Customer: {
    bg: "#3b82f6",
    border: "#60a5fa",
    text: "#dbeafe",
    glow: "rgba(59,130,246,0.35)",
  },
  SalesOrder: {
    bg: "#8b5cf6",
    border: "#a78bfa",
    text: "#ede9fe",
    glow: "rgba(139,92,246,0.35)",
  },
  SalesOrderItem: {
    bg: "#a78bfa",
    border: "#c4b5fd",
    text: "#ede9fe",
    glow: "rgba(167,139,250,0.3)",
  },
  Delivery: {
    bg: "#f59e0b",
    border: "#fbbf24",
    text: "#451a03",
    glow: "rgba(245,158,11,0.35)",
  },
  BillingDocument: {
    bg: "#10b981",
    border: "#34d399",
    text: "#d1fae5",
    glow: "rgba(16,185,129,0.35)",
  },
  Payment: {
    bg: "#06b6d4",
    border: "#22d3ee",
    text: "#cffafe",
    glow: "rgba(6,182,212,0.35)",
  },
  Product: {
    bg: "#f43f5e",
    border: "#fb7185",
    text: "#ffe4e6",
    glow: "rgba(244,63,94,0.35)",
  },
  Plant: {
    bg: "#84cc16",
    border: "#a3e635",
    text: "#1a2e05",
    glow: "rgba(132,204,22,0.35)",
  },
  Address: {
    bg: "#6366f1",
    border: "#818cf8",
    text: "#e0e7ff",
    glow: "rgba(99,102,241,0.35)",
  },
};

const EDGE_COLORS = {
  PLACED: "#3b82f6",
  CONTAINS: "#8b5cf6",
  IS_MATERIAL: "#f43f5e",
  HAS_DELIVERY: "#f59e0b",
  SHIPPED_FROM: "#84cc16",
  HAS_INVOICE: "#10b981",
  SETTLED_BY: "#06b6d4",
  HAS_ADDRESS: "#6366f1",
};

const nodeTypes = { custom: CustomNode };

// Simple force-directed layout
function forceLayout(graphData, width = 3000, height = 2400) {
  const nodes = graphData.nodes;
  const edges = graphData.edges;
  if (nodes.length === 0) return [];

  // Group nodes by label for initial placement
  const labelOrder = [
    "Customer",
    "Address",
    "SalesOrder",
    "SalesOrderItem",
    "Product",
    "Delivery",
    "Plant",
    "BillingDocument",
    "Payment",
  ];

  // Place nodes in a radial layout by type
  const positions = {};
  const nodesByLabel = {};
  nodes.forEach((n) => {
    const label = n.label || "Unknown";
    if (!nodesByLabel[label]) nodesByLabel[label] = [];
    nodesByLabel[label].push(n);
  });

  const cx = width / 2;
  const cy = height / 2;

  // Place each type group in a sector of the circle
  const usedLabels = labelOrder.filter(
    (l) => (nodesByLabel[l] || []).length > 0,
  );
  const angleStep = (2 * Math.PI) / usedLabels.length;
  const baseRadius = Math.min(width, height) * 0.35;

  usedLabels.forEach((label, groupIdx) => {
    const items = nodesByLabel[label] || [];
    const angle = groupIdx * angleStep - Math.PI / 2;
    const groupCx = cx + baseRadius * Math.cos(angle);
    const groupCy = cy + baseRadius * Math.sin(angle);

    // Spread nodes within the group in a sub-circle
    const subRadius = Math.max(40, Math.min(items.length * 12, 280));
    items.forEach((n, i) => {
      const subAngle = (2 * Math.PI * i) / items.length;
      positions[n.node_id] = {
        x:
          groupCx + subRadius * Math.cos(subAngle) + (Math.random() - 0.5) * 20,
        y:
          groupCy + subRadius * Math.sin(subAngle) + (Math.random() - 0.5) * 20,
      };
    });
  });

  // Build adjacency for force simulation
  const nodeIdSet = new Set(nodes.map((n) => n.node_id));
  const adjEdges = edges.filter(
    (e) => nodeIdSet.has(e.source) && nodeIdSet.has(e.target),
  );

  // Simple force iterations
  const springLength = 200;
  const repulsion = 8000;
  const springK = 0.02;
  const damping = 0.85;
  const iterations = 80;

  const vel = {};
  nodes.forEach((n) => (vel[n.node_id] = { x: 0, y: 0 }));

  for (let iter = 0; iter < iterations; iter++) {
    const forces = {};
    nodes.forEach((n) => (forces[n.node_id] = { x: 0, y: 0 }));

    // Repulsion between all nodes
    for (let i = 0; i < nodes.length; i++) {
      for (let j = i + 1; j < nodes.length; j++) {
        const a = nodes[i].node_id;
        const b = nodes[j].node_id;
        const dx = positions[a].x - positions[b].x;
        const dy = positions[a].y - positions[b].y;
        const dist = Math.sqrt(dx * dx + dy * dy) || 1;
        const force = repulsion / (dist * dist);
        const fx = (dx / dist) * force;
        const fy = (dy / dist) * force;
        forces[a].x += fx;
        forces[a].y += fy;
        forces[b].x -= fx;
        forces[b].y -= fy;
      }
    }

    // Spring attraction along edges
    adjEdges.forEach((e) => {
      const dx = positions[e.target].x - positions[e.source].x;
      const dy = positions[e.target].y - positions[e.source].y;
      const dist = Math.sqrt(dx * dx + dy * dy) || 1;
      const force = springK * (dist - springLength);
      const fx = (dx / dist) * force;
      const fy = (dy / dist) * force;
      forces[e.source].x += fx;
      forces[e.source].y += fy;
      forces[e.target].x -= fx;
      forces[e.target].y -= fy;
    });

    // Gravity toward center
    nodes.forEach((n) => {
      const id = n.node_id;
      forces[id].x += (cx - positions[id].x) * 0.001;
      forces[id].y += (cy - positions[id].y) * 0.001;
    });

    // Apply forces with damping
    const cooldown = 1 - iter / iterations;
    nodes.forEach((n) => {
      const id = n.node_id;
      vel[id].x = (vel[id].x + forces[id].x) * damping * cooldown;
      vel[id].y = (vel[id].y + forces[id].y) * damping * cooldown;
      positions[id].x += vel[id].x;
      positions[id].y += vel[id].y;
    });
  }

  return positions;
}

function buildFlowElements(
  graphData,
  highlightedNodes,
  activeFilters,
  hoveredNode,
) {
  const positions = forceLayout(graphData);

  const highlightSet =
    highlightedNodes instanceof Set
      ? highlightedNodes
      : new Set(highlightedNodes);

  // Build neighbor sets for hover dimming
  const hoverNeighbors = new Set();
  if (hoveredNode) {
    hoverNeighbors.add(hoveredNode);
    graphData.edges.forEach((e) => {
      if (e.source === hoveredNode) hoverNeighbors.add(e.target);
      if (e.target === hoveredNode) hoverNeighbors.add(e.source);
    });
  }

  const flowNodes = [];
  graphData.nodes.forEach((n) => {
    const label = n.label || "Unknown";
    if (activeFilters.size > 0 && !activeFilters.has(label)) return;

    const colors = LABEL_COLORS[label] || {
      bg: "#64748b",
      border: "#475569",
      text: "#e2e8f0",
      glow: "rgba(100,116,139,0.3)",
    };
    const isHighlighted = highlightSet.has(n.node_id);
    const isDimmed = hoveredNode && !hoverNeighbors.has(n.node_id);

    flowNodes.push({
      id: n.node_id,
      type: "custom",
      position: positions[n.node_id] || { x: 0, y: 0 },
      data: {
        label: n.label,
        displayName:
          n.name ||
          n.description ||
          n.plantName ||
          n.id ||
          n.node_id.split(":")[1],
        id: n.id,
        colors,
        isHighlighted,
        isDimmed,
        fullData: n,
      },
    });
  });

  const flowEdges = graphData.edges
    .filter((e) => {
      if (activeFilters.size === 0) return true;
      const srcLabel = graphData.nodes.find(
        (n) => n.node_id === e.source,
      )?.label;
      const tgtLabel = graphData.nodes.find(
        (n) => n.node_id === e.target,
      )?.label;
      return activeFilters.has(srcLabel) && activeFilters.has(tgtLabel);
    })
    .map((e, i) => {
      const edgeColor = EDGE_COLORS[e.type] || "#475569";
      const isHoverEdge =
        hoveredNode && (e.source === hoveredNode || e.target === hoveredNode);
      const isHighEdge =
        highlightSet.size > 0 &&
        highlightSet.has(e.source) &&
        highlightSet.has(e.target);
      const isDimmedEdge = hoveredNode && !isHoverEdge;

      return {
        id: `e-${i}`,
        source: e.source,
        target: e.target,
        label: e.type?.replace(/_/g, " "),
        type: "default",
        animated: isHighEdge || isHoverEdge,
        style: {
          stroke: isHoverEdge ? "#fbbf24" : edgeColor,
          strokeWidth: isHighEdge ? 2.5 : isHoverEdge ? 2 : 1,
          opacity: isDimmedEdge ? 0.08 : isHighEdge ? 1 : 0.45,
          transition: "all 0.3s ease",
        },
        markerEnd: {
          type: MarkerType.ArrowClosed,
          width: 12,
          height: 12,
          color: isHoverEdge ? "#fbbf24" : edgeColor,
        },
        labelStyle: {
          fill: isHoverEdge ? "#fbbf24" : "#94a3b8",
          fontSize: isHoverEdge ? 9 : 7,
          fontWeight: isHoverEdge ? 700 : 500,
          opacity: isDimmedEdge ? 0 : 1,
        },
        labelBgStyle: {
          fill: "#0f172a",
          fillOpacity: isDimmedEdge ? 0 : 0.85,
        },
        labelBgPadding: [4, 2],
      };
    });

  return { flowNodes, flowEdges };
}

// Legend component
function Legend({ activeFilters, onToggle }) {
  const labels = Object.entries(LABEL_COLORS);
  return (
    <div className="absolute bottom-4 left-4 z-20 bg-slate-900/90 backdrop-blur-md border border-slate-700 rounded-xl p-3 shadow-2xl">
      <div className="text-[10px] uppercase tracking-wider text-slate-500 font-bold mb-2">
        Entity Types
      </div>
      <div className="flex flex-wrap gap-1.5 max-w-[240px]">
        {labels.map(([label, colors]) => {
          const isActive = activeFilters.size === 0 || activeFilters.has(label);
          return (
            <button
              key={label}
              type="button"
              onClick={() => onToggle(label)}
              className={`flex items-center gap-1.5 px-2 py-1 rounded-md text-[10px] font-medium transition-all duration-200 border ${
                isActive
                  ? "border-transparent opacity-100"
                  : "border-slate-700 opacity-30 grayscale"
              }`}
              style={{
                backgroundColor: isActive ? colors.bg + "22" : "transparent",
                color: isActive ? colors.border : "#64748b",
              }}
            >
              <span
                className="w-2.5 h-2.5 rounded-full flex-shrink-0"
                style={{ backgroundColor: colors.bg }}
              />
              {label}
            </button>
          );
        })}
      </div>
      {activeFilters.size > 0 && (
        <button
          type="button"
          onClick={() => onToggle(null)}
          className="text-[9px] text-blue-400 hover:text-blue-300 mt-2 transition"
        >
          Reset filters
        </button>
      )}
    </div>
  );
}

export default function GraphPanel({
  graphData,
  highlightedNodes,
  onNodeClick,
}) {
  const [activeFilters, setActiveFilters] = useState(new Set());
  const [hoveredNode, setHoveredNode] = useState(null);

  const handleToggle = useCallback((label) => {
    if (label === null) {
      setActiveFilters(new Set());
      return;
    }
    setActiveFilters((prev) => {
      const next = new Set(prev);
      if (next.has(label)) next.delete(label);
      else next.add(label);
      return next;
    });
  }, []);

  const { flowNodes, flowEdges } = useMemo(
    () =>
      buildFlowElements(
        graphData,
        highlightedNodes,
        activeFilters,
        hoveredNode,
      ),
    [graphData, highlightedNodes, activeFilters, hoveredNode],
  );

  const [nodes, setNodes, onNodesChange] = useNodesState(flowNodes);
  const [edges, setEdges, onEdgesChange] = useEdgesState(flowEdges);

  useEffect(() => {
    setNodes(flowNodes);
    setEdges(flowEdges);
  }, [flowNodes, flowEdges, setNodes, setEdges]);

  const handleNodeClick = useCallback(
    (event, node) => {
      if (node.data?.fullData) onNodeClick(node.data.fullData);
    },
    [onNodeClick],
  );

  const handleNodeMouseEnter = useCallback((event, node) => {
    setHoveredNode(node.id);
  }, []);

  const handleNodeMouseLeave = useCallback(() => {
    setHoveredNode(null);
  }, []);

  return (
    <div className="w-full h-full relative">
      <ReactFlow
        nodes={nodes}
        edges={edges}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        onNodeClick={handleNodeClick}
        onNodeMouseEnter={handleNodeMouseEnter}
        onNodeMouseLeave={handleNodeMouseLeave}
        nodeTypes={nodeTypes}
        fitView
        fitViewOptions={{ padding: 0.15, maxZoom: 1.2 }}
        minZoom={0.02}
        maxZoom={3}
        defaultEdgeOptions={{ type: "default" }}
        proOptions={{ hideAttribution: true }}
      >
        <Background color="#1e293b" gap={40} size={1} variant="dots" />
        <Controls
          className="!bg-slate-800/90 !border-slate-600 !shadow-xl !rounded-lg !backdrop-blur"
          showInteractive={false}
        />
        <MiniMap
          nodeColor={(node) => {
            const colors = LABEL_COLORS[node.data?.label];
            return colors ? colors.bg : "#64748b";
          }}
          className="!bg-slate-900/80 !border-slate-700 !rounded-lg !backdrop-blur"
          maskColor="rgba(15, 23, 42, 0.8)"
          pannable
          zoomable
        />
      </ReactFlow>
      <Legend activeFilters={activeFilters} onToggle={handleToggle} />
    </div>
  );
}
