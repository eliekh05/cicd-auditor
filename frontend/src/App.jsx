import { useState } from "react";
import { analyzeRepository } from "./services/api";
import ReportSection from "./components/ReportSection";
import EvidenceTable from "./components/EvidenceTable";
import PipelineViewer from "./components/PipelineViewer";
import ConfidenceBar from "./components/ConfidenceBar";

export default function App() {
  const [url, setUrl] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [report, setReport] = useState(null);

  async function handleAnalyze(e) {
    e.preventDefault();
    setLoading(true);
    setError(null);
    setReport(null);
    try {
      const result = await analyzeRepository(url.trim());
      setReport(result);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="app">
      <header className="header">
        <div className="header-inner">
          <div className="logo">
            <span className="logo-icon">◈</span>
            <div>
              <h1>Repository CI/CD Auditor</h1>
              <p className="tagline">Evidence-driven pipeline generation — no assumptions, no API keys</p>
            </div>
          </div>
        </div>
      </header>

      <main className="main">
        <section className="input-section card">
          <form onSubmit={handleAnalyze}>
            <label htmlFor="repo-url">Public GitHub Repository URL</label>
            <div className="input-row">
              <input
                id="repo-url"
                type="url"
                placeholder="https://github.com/owner/repository"
                value={url}
                onChange={(e) => setUrl(e.target.value)}
                required
                disabled={loading}
              />
              <button type="submit" disabled={loading || !url.trim()}>
                {loading ? "Analyzing…" : "Analyze Repository"}
              </button>
            </div>
          </form>
          {error && <div className="error-banner">{error}</div>}
        </section>

        {loading && (
          <div className="loading card">
            <div className="spinner" />
            <p>Cloning repository and scanning all files…</p>
          </div>
        )}

        {report && (
          <div className="report">
            {report.huggingface_space_detected && (
              <div className="alert alert-hf">
                <strong>Hugging Face Space Detected</strong>
                <p>{report.huggingface_message}</p>
              </div>
            )}

            {report.deployment_message && !report.huggingface_space_detected && (
              <div className="alert alert-info">
                <p>{report.deployment_message}</p>
              </div>
            )}

            <ReportSection title="1. Repository Analysis Report">
              <div className="stats-grid">
                <div className="stat">
                  <span className="stat-value">{report.repository_analysis.file_count}</span>
                  <span className="stat-label">Files Scanned</span>
                </div>
                <div className="stat">
                  <span className="stat-value">{report.repository_analysis.root_path}</span>
                  <span className="stat-label">Repository</span>
                </div>
                <div className="stat">
                  <span className="stat-value">{report.evidence_table.length}</span>
                  <span className="stat-label">Evidence Items</span>
                </div>
              </div>
              <details className="file-tree-details">
                <summary>File Tree</summary>
                <pre className="file-tree">{JSON.stringify(report.repository_analysis.file_tree, null, 2)}</pre>
              </details>
            </ReportSection>

            <ReportSection title="2. Technology Stack Detection">
              <StackCategory label="Languages" items={report.technology_stack.languages} />
              <StackCategory label="Frameworks" items={report.technology_stack.frameworks} />
              <StackCategory label="Runtimes" items={report.technology_stack.runtimes} />
              <StackCategory label="Build Tools" items={report.technology_stack.build_tools} />
              <StackCategory label="Test Frameworks" items={report.technology_stack.test_frameworks} />
              <StackCategory label="Containerization" items={report.technology_stack.containerization} />
              <StackCategory label="Deployment Targets" items={report.technology_stack.deployment_targets} />
            </ReportSection>

            <ReportSection title="3. Architecture Summary">
              <p className="summary-text">{report.architecture_summary}</p>
            </ReportSection>

            <ReportSection title="4. Dependency Graph Summary">
              <p>{report.dependency_graph.nodes.length} explicit dependencies detected</p>
              {report.dependency_graph.nodes.length > 0 && (
                <div className="dep-list">
                  {report.dependency_graph.nodes.slice(0, 50).map((dep, i) => (
                    <span key={i} className="dep-chip" title={dep.source_file}>
                      {dep.name}{dep.version ? `@${dep.version}` : ""}
                    </span>
                  ))}
                  {report.dependency_graph.nodes.length > 50 && (
                    <span className="dep-chip muted">+{report.dependency_graph.nodes.length - 50} more</span>
                  )}
                </div>
              )}
            </ReportSection>

            <ReportSection title="5. Repository Evidence Table">
              <EvidenceTable items={report.evidence_table} />
            </ReportSection>

            <ReportSection title="6. Generated CI/CD Pipeline">
              {report.generated_pipeline ? (
                <PipelineViewer pipeline={report.generated_pipeline} />
              ) : (
                <p className="muted">No pipeline generated — insufficient build/test evidence.</p>
              )}
            </ReportSection>

            <ReportSection title="7. Step-by-Step Justification">
              {report.step_justifications.length > 0 ? (
                <div className="justification-list">
                  {report.step_justifications.map((step, i) => (
                    <div key={i} className="justification-item">
                      <div className="justification-header">
                        <strong>{step.name}</strong>
                        <ConfidenceBar value={step.confidence} />
                      </div>
                      {step.command && <code>{step.command}</code>}
                      <p className="justification-meta">
                        Source: <span>{step.source_file}</span> · Method: {step.detection_method}
                      </p>
                      <p>{step.reasoning}</p>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="muted">No pipeline steps generated.</p>
              )}
            </ReportSection>

            <ReportSection title="8. Explicit vs Inferred Findings">
              <div className="findings-split">
                <div>
                  <h4>Explicit ({report.explicit_findings.length})</h4>
                  <FindingsList items={report.explicit_findings.slice(0, 20)} />
                </div>
                <div>
                  <h4>Inferred ({report.inferred_findings.length})</h4>
                  <FindingsList items={report.inferred_findings.slice(0, 20)} />
                </div>
              </div>
            </ReportSection>

            <ReportSection title="9. Missing Information">
              {report.missing_information.length > 0 ? (
                <ul className="missing-list">
                  {report.missing_information.map((item, i) => (
                    <li key={i}>{item}</li>
                  ))}
                </ul>
              ) : (
                <p className="success-text">No critical gaps identified from available evidence.</p>
              )}
            </ReportSection>

            <ReportSection title="10. Confidence Assessment">
              <div className="confidence-grid">
                {Object.entries(report.confidence_assessment).map(([key, val]) => (
                  <div key={key} className="confidence-item">
                    <span className="confidence-label">{key}</span>
                    <ConfidenceBar value={val} />
                    <span className="confidence-pct">{Math.round(val * 100)}%</span>
                  </div>
                ))}
              </div>
            </ReportSection>

            <ReportSection title="11. Execution Instructions">
              <ol className="instructions-list">
                {report.execution_instructions.map((step, i) => (
                  <li key={i}>{step}</li>
                ))}
              </ol>
            </ReportSection>
          </div>
        )}
      </main>

      <footer className="footer">
        <p>Repository-aware CI/CD auditor — accuracy over assumptions</p>
      </footer>
    </div>
  );
}

function StackCategory({ label, items }) {
  if (!items || items.length === 0) return null;
  return (
    <div className="stack-category">
      <h4>{label}</h4>
      <div className="stack-items">
        {items.map((item, i) => (
          <span key={i} className="stack-chip" title={`${item.source_file} (${Math.round(item.confidence * 100)}%)`}>
            {String(item.value ?? item.reasoning.slice(0, 40))}
          </span>
        ))}
      </div>
    </div>
  );
}

function FindingsList({ items }) {
  if (!items.length) return <p className="muted">None</p>;
  return (
    <ul className="findings-list">
      {items.map((item, i) => (
        <li key={i}>
          <span className="finding-source">{item.source_file}</span>
          {item.reasoning}
        </li>
      ))}
    </ul>
  );
}
