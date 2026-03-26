import { useState, useCallback, useEffect } from "react";
import GraphPanel from "./components/GraphPanel";
import ChatPanel from "./components/ChatPanel";
import NodeDrawer from "./components/NodeDrawer";

const API_URL = import.meta.env.VITE_API_URL || "http://localhost:8002";

function App() {
  const [graphData, setGraphData] = useState({ nodes: [], edges: [] });
  const [highlightedNodes, setHighlightedNodes] = useState(new Set());
  const [selectedNode, setSelectedNode] = useState(null);
  const [loading, setLoading] = useState(true);

  // Fetch graph data on mount
  useEffect(() => {
    fetch(`${API_URL}/graph`)
      .then((r) => r.json())
      .then((data) => {
        setGraphData(data);
        setLoading(false);
      })
      .catch((err) => {
        console.error("Failed to load graph:", err);
        setLoading(false);
      });
  }, []);

  const handleNodeClick = useCallback((nodeData) => {
    setSelectedNode(nodeData);
  }, []);

  const handleHighlight = useCallback((nodeIds) => {
    setHighlightedNodes(new Set(nodeIds));
    // Clear highlights after 10 seconds
    if (nodeIds.length > 0) {
      setTimeout(() => setHighlightedNodes(new Set()), 10000);
    }
  }, []);

  return (
    <div className="flex h-screen w-screen bg-slate-900">
      {/* Left Panel — Graph Visualization */}
      <div className="w-1/2 h-full border-r border-slate-700/50 relative">
        <div className="absolute top-0 left-0 right-0 z-10 bg-slate-900/80 backdrop-blur-md px-4 py-2.5 border-b border-slate-700/50">
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-sm font-bold text-blue-400 tracking-wide flex items-center gap-2">
                <span className="w-2 h-2 rounded-full bg-blue-400 animate-pulse" />
                GRAPH DATA EXPLORER
              </h1>
              <p className="text-[11px] text-slate-500 mt-0.5">
                {loading
                  ? "Loading graph..."
                  : `${graphData.nodes.length} nodes · ${graphData.edges.length} edges · SAP Order-to-Cash`}
              </p>
            </div>
            <div className="text-[10px] text-slate-600 font-mono">
              {!loading && "Interactive"}
            </div>
          </div>
        </div>
        {!loading && (
          <GraphPanel
            graphData={graphData}
            highlightedNodes={highlightedNodes}
            onNodeClick={handleNodeClick}
          />
        )}
      </div>

      {/* Right Panel — Chat Interface */}
      <div className="w-1/2 h-full flex flex-col">
        <ChatPanel apiUrl={API_URL} onHighlight={handleHighlight} />
      </div>

      {/* Node Inspector Drawer */}
      {selectedNode && (
        <NodeDrawer node={selectedNode} onClose={() => setSelectedNode(null)} />
      )}
    </div>
  );
}

export default App;
