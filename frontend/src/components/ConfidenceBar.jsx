export default function ConfidenceBar({ value }) {
  const pct = Math.round(value * 100);
  let color = "var(--color-low)";
  if (value >= 0.9) color = "var(--color-high)";
  else if (value >= 0.6) color = "var(--color-mid)";

  return (
    <div className="confidence-bar" title={`${pct}%`}>
      <div className="confidence-fill" style={{ width: `${pct}%`, background: color }} />
    </div>
  );
}
