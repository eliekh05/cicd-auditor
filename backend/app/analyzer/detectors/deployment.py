from __future__ import annotations

import re
from pathlib import Path

from app.analyzer.detectors.base import RepositoryCommand, evidence, find_files, is_production_path
from app.models.schemas import ConfidenceLevel, EvidenceItem


def analyze_dockerfile(repo_path: Path) -> tuple[list[EvidenceItem], list[RepositoryCommand], list[EvidenceItem]]:
    """Parses single and multi-nested Dockerfiles and extracts Docker Compose configuration matrices."""
    items: list[EvidenceItem] = []
    commands: list[RepositoryCommand] = []
    deployment_items: list[EvidenceItem] = []

    for dockerfile in find_files(repo_path, {"Dockerfile", "dockerfile"}):
        rel = str(dockerfile.relative_to(repo_path))
        production = is_production_path(rel)
        try:
            content = dockerfile.read_text(encoding="utf-8")
        except OSError:
            continue

        presence = evidence(
            rel, "Dockerfile presence",
            "Containerization via Dockerfile detected" + ("" if production else " (non-production path)"),
            0.98 if production else 0.75,
            "docker",
            level=ConfidenceLevel.EXPLICIT if production else ConfidenceLevel.INFERRED,
        )
        items.append(presence)
        if production:
            deployment_items.append(presence)

        for line in content.splitlines():
            line_stripped = line.strip()
            if line_stripped.startswith("RUN "):
                cmd_part = line_stripped[4:].strip()
                if any(kw in cmd_part for kw in ("pip install", "npm install", "yarn install", "bun install")):
                    continue
                commands.append(RepositoryCommand(
                    command=cmd_part,
                    source_file=rel,
                    detection_method="Dockerfile RUN command",
                    confidence=0.85,
                    category="docker",
                ))

    # Catch Docker Compose Files
    for path in repo_path.rglob("*"):
        if path.is_file() and path.name in {"compose.yml", "compose.yaml", "docker-compose.yml", "docker-compose.yaml"}:
            rel_comp = str(path.relative_to(repo_path))
            if not is_production_path(rel_comp):
                continue
            comp_evidence = evidence(
                rel_comp, "Docker Compose configuration",
                "Multi-container target configuration detected via compose manifest specifications.",
                0.99,
                "docker-compose",
                level=ConfidenceLevel.EXPLICIT
            )
            items.append(comp_evidence)
            deployment_items.append(comp_evidence)
            commands.append(RepositoryCommand(
                command=f"docker compose -f {path.name} build",
                source_file=rel_comp,
                detection_method="Docker Compose configuration target",
                confidence=0.98,
                category="build"
            ))

    return items, commands, deployment_items


def analyze_kubernetes(repo_path: Path) -> list[EvidenceItem]:
    """Identifies deployment infrastructures by tracking explicit file configurations and front-end build matrices."""
    items: list[EvidenceItem] = []
    seen: set[str] = set()

    # 1. Search for traditional cloud cluster files
    for yml_path in repo_path.rglob("*"):
        if not yml_path.is_file() or yml_path.suffix not in {".yml", ".yaml"}:
            continue
        rel = str(yml_path.relative_to(repo_path))
        if not is_production_path(rel) or rel in seen:
            continue
        try:
            raw = yml_path.read_text(encoding="utf-8", errors="replace")
            if "apiVersion:" in raw and "kind:" in raw:
                items.append(evidence(
                    rel, "Kubernetes manifest configuration",
                    "Orchestration resource mapping verified via internal API structure specifications.",
                    0.98, "kubernetes"
                ))
                seen.add(rel)
        except OSError:
            continue

    # 2. SPA FRONTEND TARGET CHECK: Prevents SPA frameworks like pkgui from logging empty deployment records
    for spa_config in find_files(repo_path, {"vite.config.js", "vite.config.ts", "next.config.js", "nuxt.config.js"}):
        rel_spa = str(spa_config.relative_to(repo_path))
        if not is_production_path(rel_spa):
            continue
        spa_evidence = evidence(
            rel_spa, "Single Page Application Build Engine",
            f"Production static hosting deployment target identified via {spa_config.name} compilation metrics.",
            0.95,
            "static-web-hosting",
            level=ConfidenceLevel.EXPLICIT
        )
        items.append(spa_evidence)

    for helm in find_files(repo_path, {"Chart.yaml"}):
        rel = str(helm.relative_to(repo_path))
        if not is_production_path(rel):
            continue
        items.append(evidence(rel, "Helm Chart.yaml", "Helm chart detected", 0.98, "helm"))

    return items


def analyze_env_example(repo_path: Path) -> list[EvidenceItem]:
    items: list[EvidenceItem] = []
    for env_file in find_files(repo_path, {".env.example", ".env.sample", "env.example"}):
        rel = str(env_file.relative_to(repo_path))
        try:
            lines = env_file.read_text(encoding="utf-8").splitlines()
        except OSError:
            continue
        for line in lines:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                var_name = line.split("=")[0].strip()
                items.append(evidence(
                    rel, ".env.example variable",
                    f"Environment variable name listed in example file: {var_name}",
                    0.75, var_name,
                    level=ConfidenceLevel.INFERRED,
                ))
    return items
