export default function NodeDrawer({ node, onClose }) {
  const entries = Object.entries(node).filter(
    ([key, value]) => value && String(value) !== "nan" && key !== "node_id",
  );

  return (
    <div className="fixed right-0 top-0 h-full w-80 bg-slate-800 border-l border-slate-600 shadow-2xl z-50 flex flex-col">
      <div className="flex items-center justify-between px-4 py-3 border-b border-slate-700">
        <div>
          <span className="text-xs font-bold uppercase tracking-wider text-blue-400">
            {node.label}
          </span>
          <h3 className="text-sm font-medium text-white mt-0.5">
            {node.name || node.description || node.plantName || node.id}
          </h3>
        </div>
        <button
          onClick={onClose}
          className="text-slate-400 hover:text-white text-lg w-8 h-8 flex items-center justify-center rounded hover:bg-slate-700"
        >
          ✕
        </button>
      </div>

      <div className="flex-1 overflow-y-auto p-4 space-y-2">
        {entries.map(([key, value]) => (
          <div key={key} className="flex flex-col">
            <span className="text-[10px] uppercase tracking-wider text-slate-500 font-medium">
              {key}
            </span>
            <span className="text-sm text-slate-200 break-all">
              {String(value)}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}
