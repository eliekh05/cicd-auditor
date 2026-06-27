export default function ConfidenceBar({ value, showPct = true }) {
  const pct = Math.round(value * 100);
  const color =
    value >= 0.9 ? "var(--green)" : value >= 0.65 ? "var(--amber)" : "var(--red)";

  return (
    <span className="conf-row" style={{ flex: 1, minWidth: 0 }}>
      <span className="conf-bar-wrap">
        <span className="conf-bar-fill" style={{ width: `${pct}%`, background: color }} />
      </span>
      {showPct && <span className="conf-pct">{pct}%</span>}
    </span>
  );
}
