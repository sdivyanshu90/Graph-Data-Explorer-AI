import { memo } from "react";
import { Handle, Position } from "@xyflow/react";

function CustomNode({ data }) {
  const { colors, displayName, label, id, isHighlighted, isDimmed } = data;

  return (
    <div
      className={`graph-node rounded-xl border shadow-lg cursor-pointer transition-all duration-300
        ${isHighlighted ? "node-highlighted scale-125 z-50" : ""}
        ${isDimmed ? "opacity-15 scale-95 blur-[0.5px]" : "hover:scale-110 hover:z-40"}
      `}
      style={{
        backgroundColor: colors.bg + "dd",
        borderColor: isHighlighted ? "#fbbf24" : colors.border,
        borderWidth: isHighlighted ? 3 : 2,
        minWidth: "130px",
        maxWidth: "190px",
        padding: "8px 12px",
        boxShadow: isHighlighted
          ? `0 0 20px ${colors.glow}, 0 0 40px ${colors.glow}, inset 0 1px 0 rgba(255,255,255,0.15)`
          : `0 4px 12px rgba(0,0,0,0.3), inset 0 1px 0 rgba(255,255,255,0.1)`,
        backdropFilter: "blur(8px)",
      }}
    >
      <Handle
        type="target"
        position={Position.Left}
        className="!w-2.5 !h-2.5 !rounded-full !border-2 !border-slate-300/50"
        style={{ backgroundColor: colors.border }}
      />

      <div className="flex items-center gap-1.5 mb-1">
        <span
          className="w-2 h-2 rounded-full flex-shrink-0"
          style={{
            backgroundColor: colors.border,
            boxShadow: `0 0 6px ${colors.glow}`,
          }}
        />
        <span
          className="text-[8px] font-bold uppercase tracking-widest"
          style={{ color: colors.text, opacity: 0.7 }}
        >
          {label}
        </span>
      </div>
      <div
        className="text-[11px] font-semibold truncate leading-tight"
        style={{ color: colors.text }}
        title={displayName}
      >
        {displayName}
      </div>
      {id && (
        <div
          className="text-[8px] mt-1 font-mono"
          style={{ color: colors.text, opacity: 0.45 }}
        >
          {id}
        </div>
      )}

      <Handle
        type="source"
        position={Position.Right}
        className="!w-2.5 !h-2.5 !rounded-full !border-2 !border-slate-300/50"
        style={{ backgroundColor: colors.border }}
      />
    </div>
  );
}

export default memo(CustomNode);
