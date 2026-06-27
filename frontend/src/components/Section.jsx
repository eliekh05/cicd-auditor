import { useState } from "react";

export default function Section({ title, badge, defaultOpen = false, children }) {
  const [open, setOpen] = useState(defaultOpen);
  return (
    <div className="card">
      <div className="card-head" onClick={() => setOpen((o) => !o)}>
        <span className="card-title">
          {title}
          {badge != null && <span className="card-badge">{badge}</span>}
        </span>
        <span className={`chevron ${open ? "open" : ""}`}>▶</span>
      </div>
      {open && <div className="card-body">{children}</div>}
    </div>
  );
}
