export default function EvidenceTable({ items }) {
  if (!items.length) return <p className="muted">No evidence collected.</p>;

  return (
    <div className="table-wrap">
      <table className="evidence-table">
        <thead>
          <tr>
            <th>Source File</th>
            <th>Detection Method</th>
            <th>Reasoning</th>
            <th>Confidence</th>
            <th>Level</th>
          </tr>
        </thead>
        <tbody>
          {items.map((item, i) => (
            <tr key={i}>
              <td className="mono">{item.source_file}</td>
              <td>{item.detection_method}</td>
              <td>{item.reasoning}</td>
              <td>{Math.round(item.confidence * 100)}%</td>
              <td>
                <span className={`badge badge-${item.confidence_level}`}>
                  {item.confidence_level}
                </span>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
