import { useState } from "react";

const KIND_LABELS = {
  "github-actions":    "GitHub Actions",
  "gitlab-ci":         "GitLab CI",
  "jenkins":           "Jenkins",
  "huggingface-spaces":"Hugging Face Spaces",
};

const KIND_PATHS = {
  "github-actions":    ".github/workflows/ci.yml",
  "gitlab-ci":         ".gitlab-ci.yml",
  "jenkins":           "Jenkinsfile",
};

export default function StartingPoint({ pipeline, steps }) {
  const [tab, setTab] = useState("yaml");
  const [copied, setCopied] = useState(false);

  const content = pipeline?.content ?? "";
  const kind    = pipeline?.kind ?? "github-actions";
  const destPath = KIND_PATHS[kind] ?? "ci.yml";

  function copy() {
    navigator.clipboard.writeText(content).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 1800);
    });
  }

  return (
    <div>
      <div className="starting-point-intro">
        This is <strong>not a generic template</strong> — every command here was
        pulled from a real file in the repository. Commands we couldn't find evidence
        for aren't included. If something looks missing it probably means the repo
        doesn't declare it yet.
        <br /><br />
        Save this as <code style={{ fontFamily: "var(--mono)", fontSize: "0.9em" }}>{destPath}</code> and
        push. That's all it takes to get started.
      </div>

      <div className="workflow-tabs" style={{ marginBottom: "0.75rem" }}>
        <button
          className={`wf-tab ${tab === "yaml" ? "active" : ""}`}
          onClick={() => setTab("yaml")}
        >
          {KIND_LABELS[kind] ?? kind}
        </button>
        {steps?.length > 0 && (
          <button
            className={`wf-tab ${tab === "why" ? "active" : ""}`}
            onClick={() => setTab("why")}
          >
            why these steps
          </button>
        )}
      </div>

      {tab === "yaml" && (
        <>
          <div className="copy-row">
            <span className="copy-row-label">save as {destPath}</span>
            <button className={`copy-btn ${copied ? "copied" : ""}`} onClick={copy}>
              {copied ? "✓ copied" : "copy"}
            </button>
          </div>
          <pre className="code-block"><code>{content}</code></pre>
        </>
      )}

      {tab === "why" && steps?.length > 0 && (
        <div className="steps-list">
          {steps.map((step, i) => (
            <div key={i} className="step-card">
              <div className="step-header">
                <span className="step-name">{step.name}</span>
                <ConfBadge confidence={step.confidence} score={step.score} />
              </div>
              {step.cmd && <div className="step-cmd">$ {step.cmd}</div>}
              <div className="step-why">{step.detail}</div>
              <div className="step-src">{step.source} · {step.method}</div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function ConfBadge({ confidence, score }) {
  const pct = Math.round(score * 100);
  const color =
    confidence === "explicit" ? "var(--green)" :
    confidence === "inferred" ? "var(--amber)" : "var(--text-3)";
  return (
    <span style={{ fontSize: "0.75rem", color, marginLeft: "auto" }}>
      {confidence} · {pct}%
    </span>
  );
}
