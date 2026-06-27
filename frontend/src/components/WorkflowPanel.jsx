import { useState } from "react";

const KIND_LABELS = {
  "github-actions": "GitHub Actions",
  "gitlab-ci":      "GitLab CI",
  "jenkins":        "Jenkinsfile",
};

export default function WorkflowPanel({ workflows }) {
  const [active, setActive] = useState(0);
  const [copied, setCopied] = useState(false);

  if (!workflows?.length) return null;
  const wf = workflows[active];

  function copy() {
    navigator.clipboard.writeText(wf.content).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 1800);
    });
  }

  return (
    <div>
      {workflows.length > 1 && (
        <div className="workflow-tabs">
          {workflows.map((w, i) => (
            <button
              key={i}
              className={`wf-tab ${i === active ? "active" : ""}`}
              onClick={() => { setActive(i); setCopied(false); }}
            >
              {w.path}
            </button>
          ))}
        </div>
      )}

      <div className="copy-row">
        <span className="copy-row-label">
          {KIND_LABELS[wf.kind] ?? wf.kind} · {wf.path}
        </span>
        <button className={`copy-btn ${copied ? "copied" : ""}`} onClick={copy}>
          {copied ? "✓ copied" : "copy"}
        </button>
      </div>

      <pre className="code-block"><code>{wf.content || "(empty file)"}</code></pre>

      {wf.audit_notes?.length > 0 && (
        <div className="audit-list" style={{ marginTop: "1rem" }}>
          {wf.audit_notes.map((note, i) => (
            <div key={i} className="audit-item">
              <span className="audit-dot">▲</span>
              <span>{note}</span>
            </div>
          ))}
        </div>
      )}

      {wf.audit_notes?.length === 0 && (
        <div className="audit-clean" style={{ marginTop: "0.75rem" }}>
          <span>✓</span> Looks clean — no obvious issues spotted.
        </div>
      )}
    </div>
  );
}
