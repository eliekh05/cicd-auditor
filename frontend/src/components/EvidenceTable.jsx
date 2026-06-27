import { useState, useMemo } from "react";

const LEVELS = ["all", "explicit", "inferred", "low"];

function Bar({ score }) {
  const pct = Math.round(score * 100);
  const color =
    score >= 0.9 ? "var(--green)" : score >= 0.65 ? "var(--amber)" : "var(--red)";
  return (
    <span className="conf-row">
      <span className="conf-bar-wrap">
        <span className="conf-bar-fill" style={{ width: `${pct}%`, background: color }} />
      </span>
      <span className="conf-pct">{pct}%</span>
    </span>
  );
}

export default function EvidenceTable({ items }) {
  const [filter, setFilter] = useState("all");
  const [q, setQ] = useState("");

  const rows = useMemo(() => {
    let r = items;
    if (filter !== "all") r = r.filter((x) => x.confidence === filter);
    if (q.trim()) {
      const s = q.toLowerCase();
      r = r.filter((x) =>
        [x.source, x.method, x.detail, x.value].some((f) => f?.toLowerCase().includes(s))
      );
    }
    return r;
  }, [items, filter, q]);

  if (!items.length) return (
    <p style={{ color: "var(--text-3)", fontSize: "0.85rem" }}>No evidence recorded.</p>
  );

  return (
    <div>
      <div className="filter-row">
        {LEVELS.map((l) => (
          <button
            key={l}
            className={`filter-chip ${filter === l ? "active" : ""}`}
            onClick={() => setFilter(l)}
          >
            {l}
          </button>
        ))}
        <input
          className="search-input"
          placeholder="search…"
          value={q}
          onChange={(e) => setQ(e.target.value)}
        />
        <span className="row-count">{rows.length}</span>
      </div>

      <div className="table-scroll">
        <table className="ev-table">
          <thead>
            <tr>
              <th>Source</th>
              <th>Method</th>
              <th>Detail</th>
              <th>Score</th>
              <th>Level</th>
            </tr>
          </thead>
          <tbody>
            {rows.slice(0, 200).map((item, i) => (
              <tr key={i}>
                <td className="mono-sm">{item.source}</td>
                <td style={{ fontSize: "0.8rem" }}>{item.method}</td>
                <td style={{ fontSize: "0.8rem", color: "var(--text-2)" }}>{item.detail}</td>
                <td><Bar score={item.score} /></td>
                <td><span className={`badge badge-${item.confidence}`}>{item.confidence}</span></td>
              </tr>
            ))}
          </tbody>
        </table>
        {rows.length > 200 && (
          <p style={{ fontSize: "0.75rem", color: "var(--text-3)", padding: "0.5rem 0.75rem" }}>
            Showing 200 of {rows.length}
          </p>
        )}
      </div>
    </div>
  );
}
