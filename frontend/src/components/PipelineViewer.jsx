import { useState } from "react";

export default function PipelineViewer({ pipeline }) {
  const [copied, setCopied] = useState(false);

  function copy() {
    navigator.clipboard.writeText(pipeline.content).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    });
  }

  const kindLabels = {
    "github-actions": "GitHub Actions",
    "gitlab-ci": "GitLab CI",
    jenkins: "Jenkins",
    "huggingface-spaces": "Hugging Face Spaces",
  };

  return (
    <div>
      <div className="pipeline-meta">
        <span className="pipeline-kind">{kindLabels[pipeline.kind] ?? pipeline.kind}</span>
        {pipeline.override_note && (
          <span className="pipeline-override">↳ {pipeline.override_note}</span>
        )}
        <button className={`copy-btn ${copied ? "copied" : ""}`} onClick={copy}>
          {copied ? "✓ Copied" : "Copy"}
        </button>
      </div>
      <pre className="pipeline-code"><code>{pipeline.content}</code></pre>
    </div>
  );
}
