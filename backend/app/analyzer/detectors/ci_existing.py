from __future__ import annotations

import re
from pathlib import Path

from app.analyzer.detectors.base import evidence, find_files
from app.models.schemas import ConfidenceLevel, EvidenceItem


def analyze_existing_ci(repo_path: Path) -> tuple[list[EvidenceItem], str | None]:
    items: list[EvidenceItem] = []
    override: str | None = None

    gitlab_files = find_files(repo_path, {".gitlab-ci.yml"})
    if gitlab_files:
        rel = str(gitlab_files[0].relative_to(repo_path))
        items.append(evidence(
            rel, "GitLab CI config",
            "Existing GitLab CI configuration detected — GitLab CI takes priority",
            0.98, "gitlab-ci",
        ))
        override = "gitlab-ci"

    jenkins_files = find_files(repo_path, {"Jenkinsfile"})
    if jenkins_files and override is None:
        rel = str(jenkins_files[0].relative_to(repo_path))
        items.append(evidence(
            rel, "Jenkinsfile",
            "Existing Jenkins pipeline detected — Jenkins takes priority",
            0.98, "jenkins",
        ))
        override = "jenkins"

    gha_dir = repo_path / ".github" / "workflows"
    if gha_dir.is_dir():
        for wf in sorted(gha_dir.glob("*.yml")) + sorted(gha_dir.glob("*.yaml")):
            rel = str(wf.relative_to(repo_path))
            items.append(evidence(
                rel, "GitHub Actions workflow",
                f"Existing GitHub Actions workflow: {wf.name}",
                0.98, "github-actions",
            ))

    return items, override


def analyze_readme_commands(repo_path: Path) -> tuple[list[EvidenceItem], list]:
    """
    README commands are recorded as low-confidence evidence only.
    They are NOT added to pipeline-eligible command lists.
    """
    items: list[EvidenceItem] = []

    for readme in find_files(repo_path, {"README.md", "README.MD"}):
        rel = str(readme.relative_to(repo_path))
        try:
            content = readme.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue

        code_blocks = re.findall(r"```(?:bash|sh|shell)?\n(.*?)```", content, re.DOTALL)
        for block in code_blocks:
            for line in block.splitlines():
                line = line.strip()
                if line.startswith("$"):
                    line = line[1:].strip()
                if not line:
                    continue
                if any(line.startswith(cmd) for cmd in (
                    "npm ", "yarn ", "pip ", "python ", "make ", "docker ",
                    "poetry ", "pytest", "gradle", "./gradlew", "mvn ",
                )):
                    items.append(evidence(
                        rel, "README explicit command",
                        f"Command found in README (evidence only, not pipeline-eligible): {line}",
                        0.65, line,
                        level=ConfidenceLevel.LOW,
                    ))

    return items, []


def detect_tests(evidence_items: list[EvidenceItem]) -> list[EvidenceItem]:
    test_keywords = {"jest", "vitest", "pytest", "cypress", "junit", "mocha", "playwright"}
    test_items: list[EvidenceItem] = []
    seen: set[str] = set()

    for item in evidence_items:
        if item.confidence_level == ConfidenceLevel.LOW:
            continue
        val = str(item.value).lower() if item.value else ""
        reasoning_lower = item.reasoning.lower()
        for kw in test_keywords:
            if kw in val or kw in reasoning_lower:
                if kw not in seen:
                    seen.add(kw)
                    test_items.append(item)
                break

    return test_items
