from __future__ import annotations

import re
from pathlib import Path

from app.analyzer.helpers import find, make_evidence, rel
from app.models.schemas import Confidence, Evidence, ExistingWorkflow

_SKIP = frozenset({".git", "node_modules", "__pycache__", ".venv", "venv", "dist", "build"})


# ──────────────────────────────────────────────────────────────────────────────
# Audit helpers
# ──────────────────────────────────────────────────────────────────────────────

def _audit_gha(content: str) -> list[str]:
    notes = []
    if "actions/checkout" not in content:
        notes.append("Missing actions/checkout step — the workspace will be empty.")
    if "cache" not in content and ("npm" in content or "pip" in content or "poetry" in content):
        notes.append("No dependency caching — consider actions/cache or setup-node/setup-python cache: option.")
    if "timeout-minutes" not in content:
        notes.append("No timeout-minutes set — runaway jobs will consume all Actions minutes.")
    if "permissions:" not in content:
        notes.append("No explicit permissions block — default token permissions may be too broad.")
    if re.search(r"uses:\s+\S+@(main|master|latest)", content):
        notes.append("Action pinned to a mutable ref (main/master/latest) — pin to a SHA for reproducibility.")
    if "on:" not in content and "\"on\":" not in content:
        notes.append("No trigger (on:) defined.")
    if not re.search(r"(npm (ci|install)|pip install|poetry install|yarn install)", content):
        notes.append("No dependency install step detected.")
    if not re.search(r"(npm (run )?test|pytest|jest|vitest|yarn test)", content):
        notes.append("No test step detected — consider adding one.")
    return notes


def _audit_gitlab(content: str) -> list[str]:
    notes = []
    if "stages:" not in content:
        notes.append("No stages: defined — pipeline stage order is implicit.")
    if "cache:" not in content:
        notes.append("No cache: directive — dependency installs will repeat every run.")
    if not re.search(r"(npm (ci|install)|pip install|poetry install)", content):
        notes.append("No dependency install step detected.")
    if not re.search(r"(npm (run )?test|pytest|jest|vitest)", content):
        notes.append("No test step detected.")
    return notes


def _audit_jenkins(content: str) -> list[str]:
    notes = []
    if "agent" not in content:
        notes.append("No agent directive — pipeline may not run.")
    if "post {" not in content:
        notes.append("No post block — build results and notifications are not handled.")
    if not re.search(r"(npm (run )?test|pytest|sh 'test)", content):
        notes.append("No test stage detected.")
    return notes


# ──────────────────────────────────────────────────────────────────────────────
# Existing CI detection
# ──────────────────────────────────────────────────────────────────────────────

def detect_existing_ci(repo: Path) -> tuple[list[Evidence], list[ExistingWorkflow]]:
    """
    Returns (evidence_list, existing_workflows).
    existing_workflows is non-empty when the repo already has CI config.
    """
    evidence: list[Evidence] = []
    workflows: list[ExistingWorkflow] = []

    # GitHub Actions — read every workflow file
    gha_dir = repo / ".github" / "workflows"
    if gha_dir.is_dir():
        for wf in sorted(gha_dir.glob("*.yml")) + sorted(gha_dir.glob("*.yaml")):
            r = rel(repo, wf)
            try:
                content = wf.read_text(encoding="utf-8", errors="replace")
            except OSError:
                content = ""
            notes = _audit_gha(content)
            workflows.append(ExistingWorkflow(
                path=r, kind="github-actions", content=content, audit_notes=notes,
            ))
            evidence.append(make_evidence(
                r, "GitHub Actions workflow",
                f"Existing workflow: {wf.name}",
                0.99, "github-actions",
            ))

    # GitLab CI
    for gitlab in find(repo, {".gitlab-ci.yml"}):
        r = rel(repo, gitlab)
        try:
            content = gitlab.read_text(encoding="utf-8", errors="replace")
        except OSError:
            content = ""
        notes = _audit_gitlab(content)
        workflows.append(ExistingWorkflow(
            path=r, kind="gitlab-ci", content=content, audit_notes=notes,
        ))
        evidence.append(make_evidence(r, "GitLab CI", "Existing .gitlab-ci.yml", 0.99, "gitlab-ci"))

    # Jenkins
    for jenkins in find(repo, {"Jenkinsfile"}):
        r = rel(repo, jenkins)
        try:
            content = jenkins.read_text(encoding="utf-8", errors="replace")
        except OSError:
            content = ""
        notes = _audit_jenkins(content)
        workflows.append(ExistingWorkflow(
            path=r, kind="jenkins", content=content, audit_notes=notes,
        ))
        evidence.append(make_evidence(r, "Jenkinsfile", "Existing Jenkinsfile", 0.99, "jenkins"))

    return evidence, workflows


def detect_readme_commands(repo: Path) -> list[Evidence]:
    evidence: list[Evidence] = []
    _starters = (
        "npm ", "yarn ", "pnpm ", "pip ", "python ", "make ",
        "docker ", "poetry ", "pytest", "gradle", "./gradlew", "mvn ",
    )
    for readme in find(repo, {"README.md", "README.MD"}):
        r = rel(repo, readme)
        try:
            content = readme.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for block in re.findall(r"```(?:bash|sh|shell)?\n(.*?)```", content, re.DOTALL):
            for line in block.splitlines():
                line = line.strip().lstrip("$ ")
                if line and any(line.startswith(s) for s in _starters):
                    evidence.append(make_evidence(
                        r, "README command",
                        f"Command in README (evidence only): {line}",
                        0.60, line,
                        confidence=Confidence.LOW,
                    ))
    return evidence


def detect_test_frameworks(evidence: list[Evidence]) -> list[Evidence]:
    keywords = {"jest", "vitest", "pytest", "cypress", "junit", "mocha", "playwright", "karma"}
    found: list[Evidence] = []
    seen: set[str] = set()
    for item in evidence:
        if item.confidence == Confidence.LOW:
            continue
        combined = f"{item.value or ''} {item.detail}".lower()
        for kw in keywords:
            if kw in combined and kw not in seen:
                seen.add(kw)
                found.append(item)
                break
    return found


# ──────────────────────────────────────────────────────────────────────────────
# Hugging Face Spaces
# ──────────────────────────────────────────────────────────────────────────────

def detect_huggingface(repo: Path) -> tuple[bool, list[Evidence], str | None]:
    evidence: list[Evidence] = []
    signals: set[str] = set()

    for readme in find(repo, {"README.md", "README.MD", "readme.md"}):
        if str(readme.relative_to(repo)).count("/") > 0:
            continue
        r = rel(repo, readme)
        try:
            content = readme.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        m = re.search(r"^---\s*\n(.*?)\n---", content, re.DOTALL | re.MULTILINE)
        if m and ("sdk:" in m.group(1).lower() or "app_file:" in m.group(1).lower()):
            signals.add("readme_front_matter")
            evidence.append(make_evidence(
                r, "Hugging Face front matter",
                "Root README has Spaces YAML front matter (sdk/app_file)",
                0.98, "huggingface-spaces",
            ))
        if re.search(r"huggingface\.co/spaces/", content, re.IGNORECASE):
            signals.add("readme_hf_url")
            evidence.append(make_evidence(
                r, "Hugging Face URL",
                "README references huggingface.co/spaces/",
                0.97, "huggingface-spaces",
            ))

    for space_yaml in find(repo, {"space.yaml", "space.yml"}):
        signals.add("space.yaml")
        evidence.append(make_evidence(
            rel(repo, space_yaml), "space.yaml",
            "Dedicated Hugging Face Space config file",
            0.99, "huggingface-spaces",
        ))

    for d in repo.rglob(".huggingface"):
        if d.is_dir():
            signals.add(".huggingface")
            evidence.append(make_evidence(
                rel(repo, d), ".huggingface directory",
                "Hugging Face config directory",
                0.98, "huggingface-spaces",
            ))

    for app_py in find(repo, {"app.py"}):
        if rel(repo, app_py).count("/") > 0:
            continue
        try:
            content = app_py.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if "import gradio" in content or "from gradio" in content:
            evidence.append(make_evidence(
                rel(repo, app_py), "Gradio import",
                "Root app.py imports Gradio — supporting signal only",
                0.70, "gradio",
                confidence=Confidence.INFERRED,
            ))

    detected = bool(signals)
    note = (
        "This is a Hugging Face Space. "
        "CI/CD is managed automatically by the Spaces runtime on every push."
        if detected else None
    )
    return detected, evidence, note
