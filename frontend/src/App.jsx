import { useState, useEffect } from "react";
import { analyzeRepo } from "./services/api";
import Section from "./components/Section";
import EvidenceTable from "./components/EvidenceTable";
import StackDisplay from "./components/StackDisplay";
import FileTree from "./components/FileTree";
import WorkflowPanel from "./components/WorkflowPanel";
import StartingPoint from "./components/StartingPoint";

const STEPS = [
  "Cloning repository…",
  "Walking the file tree…",
  "Running detectors…",
  "Building evidence…",
  "Wrapping up…",
];

export default function App() {
  const [url, setUrl] = useState("");
  const [loading, setLoading] = useState(false);
  const [stepIdx, setStepIdx] = useState(0);
  const [error, setError] = useState(null);
  const [report, setReport] = useState(null);

  useEffect(() => {
    if (!loading) { setStepIdx(0); return; }
    const id = setInterval(
      () => setStepIdx((s) => Math.min(s + 1, STEPS.length - 1)),
      3200
    );
    return () => clearInterval(id);
  }, [loading]);

  async function submit(e) {
    e.preventDefault();
    if (!url.trim()) return;
    setLoading(true);
    setError(null);
    setReport(null);
    try {
      setReport(await analyzeRepo(url.trim()));
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="shell">
      <header className="header">
        <div className="header-inner">
          <div className="logo">
            <div className="logo-icon">▸</div>
            <div>
              <div className="logo-text">Pipeline Scout</div>
              <div className="logo-sub">checks if you need it before telling you what to do</div>
            </div>
          </div>
          {report && (
            <button
              className="btn btn-ghost"
              onClick={() => { setReport(null); setError(null); setUrl(""); }}
            >
              ← scan another
            </button>
          )}
        </div>
      </header>

      <main className="page">
        {!report && !loading && (
          <div className="hero">
            <h1>Does this repo need a pipeline?</h1>
            <p>
              Drop in a GitHub URL. If CI already exists we'll tell you straight
              and flag anything worth fixing. If it doesn't, we'll build you a
              real starting point from what we actually find in the code.
            </p>
            <form onSubmit={submit}>
              <div className="search-wrap">
                <input
                  className="url-input"
                  type="url"
                  placeholder="https://github.com/owner/repo"
                  value={url}
                  onChange={(e) => setUrl(e.target.value)}
                  required
                  disabled={loading}
                />
                <button className="btn" type="submit" disabled={!url.trim()}>
                  Scan
                </button>
              </div>
            </form>
            {error && <div className="error-bar">{error}</div>}
          </div>
        )}

        {loading && (
          <div className="loading">
            <div className="spinner" />
            <div className="loading-msg">{STEPS[stepIdx]}</div>
          </div>
        )}

        {report && <Result report={report} />}
      </main>

      <footer className="footer">
        Pipeline Scout — looks before it leaps
      </footer>
    </div>
  );
}

/* ────────────────────────────────────────────────────────────────────────── */

function Result({ report }) {
  const hasCI = report.existing_workflows?.length > 0;
  const isHF  = report.is_huggingface;

  return (
    <div style={{ paddingTop: "1.5rem" }}>

      {/* ── Verdict ── */}
      {isHF && (
        <div className="verdict is-hf">
          <span className="verdict-icon">🤗</span>
          <div>
            <div className="verdict-title">Hugging Face Space — no pipeline needed</div>
            <div className="verdict-body">
              Spaces rebuild automatically every time you push. There's nothing
              to configure here — just commit and the platform handles it.
            </div>
          </div>
        </div>
      )}

      {!isHF && hasCI && (
        <div className="verdict has-ci">
          <span className="verdict-icon">✓</span>
          <div>
            <div className="verdict-title">This repo already has CI — you're good</div>
            <div className="verdict-body">
              Found {report.existing_workflows.length} workflow file
              {report.existing_workflows.length !== 1 ? "s" : ""}.
              {report.gaps.length > 0
                ? ` We spotted ${report.gaps.length} thing${report.gaps.length !== 1 ? "s" : ""} worth looking at below.`
                : " Everything looks clean — no obvious issues."}
            </div>
          </div>
        </div>
      )}

      {!isHF && !hasCI && (
        <div className="verdict no-ci">
          <span className="verdict-icon">→</span>
          <div>
            <div className="verdict-title">No CI found — here's a starting point</div>
            <div className="verdict-body">
              We scanned {report.file_count} files and found nothing under{" "}
              <code style={{ fontFamily: "var(--mono)", fontSize: "0.82em" }}>.github/workflows/</code>,
              no <code style={{ fontFamily: "var(--mono)", fontSize: "0.82em" }}>.gitlab-ci.yml</code>,
              no <code style={{ fontFamily: "var(--mono)", fontSize: "0.82em" }}>Jenkinsfile</code>.
              What's below is built from what actually exists in the repo — not a generic template.
            </div>
          </div>
        </div>
      )}

      {/* ── Existing CI audit ── */}
      {hasCI && (
        <Section title="Your CI files" defaultOpen>
          <WorkflowPanel workflows={report.existing_workflows} />
        </Section>
      )}

      {/* ── Audit issues ── */}
      {hasCI && report.gaps.length > 0 && (
        <Section title="Things worth fixing" badge={report.gaps.length} defaultOpen>
          <div className="audit-list">
            {report.gaps.map((g, i) => (
              <div key={i} className="audit-item">
                <span className="audit-dot">▲</span>
                <span>{g}</span>
              </div>
            ))}
          </div>
        </Section>
      )}

      {hasCI && report.gaps.length === 0 && (
        <Section title="Audit">
          <div className="audit-clean">
            <span>✓</span>
            No obvious issues in the existing CI configuration.
          </div>
        </Section>
      )}

      {/* ── Generated starting point ── */}
      {!isHF && !hasCI && report.pipeline && (
        <Section title="Starting point" defaultOpen>
          <StartingPoint pipeline={report.pipeline} steps={report.steps} />
        </Section>
      )}

      {!isHF && !hasCI && !report.pipeline && (
        <Section title="Starting point">
          <div className="starting-point-intro">
            Not enough evidence to write a meaningful pipeline. We found no build
            scripts, no test commands, and no install configuration. Add a{" "}
            <code>package.json</code>, <code>requirements.txt</code>, or{" "}
            <code>Makefile</code> with real commands and scan again.
          </div>
        </Section>
      )}

      {/* ── What we found ── */}
      <Section title="What we found in the repo">
        <div className="stats-row">
          <Stat n={report.file_count} label="Files scanned" />
          <Stat n={report.dependencies.length} label="Dependencies" />
          <Stat n={report.explicit_findings.length} label="Hard evidence" color="var(--green)" />
          <Stat n={report.inferred_findings.length} label="Inferred" color="var(--amber)" />
        </div>
        <FileTree tree={report.file_tree} />
      </Section>

      {/* ── Tech stack ── */}
      <Section title="Tech stack" badge={countStack(report.stack)}>
        <StackDisplay stack={report.stack} />
      </Section>

      {/* ── Dependencies ── */}
      {report.dependencies.length > 0 && (
        <Section title="Dependencies" badge={report.dependencies.length}>
          <p className="dep-note">
            {report.dependencies.length} explicit dependencies found across all manifest files.
          </p>
          <div className="chips">
            {report.dependencies.slice(0, 80).map((d, i) => (
              <span key={i} className="chip mono-sm" title={`from ${d.source}`}>
                {d.name}
                {d.version ? `@${d.version.replace(/[\^~>=<\s]/g, "").slice(0, 10)}` : ""}
              </span>
            ))}
            {report.dependencies.length > 80 && (
              <span className="chip" style={{ color: "var(--text-3)" }}>
                +{report.dependencies.length - 80} more
              </span>
            )}
          </div>
        </Section>
      )}

      {/* ── Evidence ── */}
      <Section title="Evidence collected" badge={report.evidence.length}>
        <EvidenceTable items={report.evidence} />
      </Section>

    </div>
  );
}

function Stat({ n, label, color }) {
  return (
    <div className="stat-cell">
      <div className="stat-val" style={color ? { color } : {}}>{n}</div>
      <div className="stat-lbl">{label}</div>
    </div>
  );
}

function countStack(stack) {
  return Object.values(stack).reduce((acc, arr) => acc + (arr?.length ?? 0), 0);
}
