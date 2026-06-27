import { useState } from "react";

const SKIP = new Set([".git", "node_modules", "__pycache__", ".venv"]);

function Node({ node, depth = 0 }) {
  const [open, setOpen] = useState(depth < 1);
  const pad = depth * 12;

  if (node.type === "file") {
    return (
      <div style={{ paddingLeft: pad + 14, fontSize: "0.76rem", color: "var(--text-3)", lineHeight: 1.85 }}>
        <span style={{ opacity: 0.4, marginRight: 6 }}>·</span>
        {node.name}
      </div>
    );
  }

  if (SKIP.has(node.name)) return null;

  return (
    <div>
      <div
        onClick={() => setOpen((o) => !o)}
        style={{
          paddingLeft: pad, fontSize: "0.78rem", color: "var(--text-2)",
          lineHeight: 1.85, cursor: "pointer", display: "flex", gap: 5, alignItems: "center",
        }}
      >
        <span style={{ fontSize: "0.65rem", opacity: 0.5, width: 9 }}>{open ? "▾" : "▸"}</span>
        {node.name}/
      </div>
      {open && node.children?.map((c, i) => <Node key={i} node={c} depth={depth + 1} />)}
    </div>
  );
}

export default function FileTree({ tree }) {
  const [show, setShow] = useState(false);
  return (
    <div>
      <button className="tree-toggle" onClick={() => setShow((s) => !s)}>
        {show ? "hide" : "show"} file tree
      </button>
      {show && (
        <div className="file-tree">
          <Node node={tree} />
        </div>
      )}
    </div>
  );
}
