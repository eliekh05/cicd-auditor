from __future__ import annotations

import re
from pathlib import Path

from app.analyzer.detectors.base import RepositoryCommand, evidence, find_files, is_production_path
from app.models.schemas import ConfidenceLevel, EvidenceItem


def analyze_dockerfile(repo_path: Path) -> tuple[list[EvidenceItem], list[RepositoryCommand], list[EvidenceItem]]:
    """
    Returns (all_docker_evidence, commands, production_deployment_evidence).
    Dockerfiles in test/demo paths are recorded but excluded from deployment targets.
    """
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
            "Containerization via Dockerfile detected"
            + ("" if production else " (non-production path — not a deployment target)"),
            0.98 if production else 0.75,
            "docker",
            level=ConfidenceLevel.EXPLICIT if production else ConfidenceLevel.INFERRED,
        )
        items.append(presence)
        if production:
            deployment_items.append(presence)

        for line in content.splitlines():
            line_stripped = line.strip()
            if line_stripped.upper().startswith("FROM "):
                base = line_stripped[5:].split("#")[0].strip()
                items.append(evidence(
                    rel, "Dockerfile FROM instruction",
                    f"Base image: {base}",
                    0.98, base,
                ))
            if line_stripped.upper().startswith(("CMD ", "ENTRYPOINT ")):
                items.append(evidence(
                    rel, "Dockerfile entrypoint",
                    f"Entrypoint/command: {line_stripped}",
                    0.98, line_stripped,
                ))
            if line_stripped.upper().startswith("RUN "):
                run_cmd = line_stripped[4:].strip()
                commands.append(RepositoryCommand(
                    command=run_cmd,
                    source_file=rel,
                    detection_method="Dockerfile RUN instruction",
                    confidence=0.98,
                    category="docker",
                ))
                items.append(evidence(
                    rel, "Dockerfile RUN instruction",
                    f"Build command from Dockerfile: {run_cmd}",
                    0.98, run_cmd,
                ))

    for compose in find_files(repo_path, {"docker-compose.yml", "docker-compose.yaml", "compose.yml"}):
        rel = str(compose.relative_to(repo_path))
        production = is_production_path(rel)
        item = evidence(
            rel, "docker-compose presence",
            "Docker Compose configuration detected"
            + ("" if production else " (non-production path — not a deployment target)"),
            0.98 if production else 0.75,
            "docker-compose",
            level=ConfidenceLevel.EXPLICIT if production else ConfidenceLevel.INFERRED,
        )
        items.append(item)
        if production:
            deployment_items.append(item)

    return items, commands, deployment_items


def analyze_kubernetes(repo_path: Path) -> list[EvidenceItem]:
    """Kubernetes evidence requires explicit kind: field — no path-heuristic alone."""
    items: list[EvidenceItem] = []
    seen: set[str] = set()

    for path in repo_path.rglob("*"):
        if not path.is_file() or path.suffix not in (".yaml", ".yml"):
            continue
        rel = str(path.relative_to(repo_path))
        if not is_production_path(rel):
            continue
        try:
            content = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue

        if not re.search(
            r"^kind:\s*(Deployment|Service|Ingress|StatefulSet|DaemonSet|ConfigMap)",
            content,
            re.MULTILINE,
        ):
            continue
        if rel in seen:
            continue
        seen.add(rel)
        items.append(evidence(
            rel, "Kubernetes kind field",
            "Kubernetes resource kind explicitly declared in YAML",
            0.98, "kubernetes",
        ))

    for helm in find_files(repo_path, {"Chart.yaml"}):
        rel = str(helm.relative_to(repo_path))
        if not is_production_path(rel):
            continue
        items.append(evidence(
            rel, "Helm Chart.yaml",
            "Helm chart detected",
            0.98, "helm",
        ))

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
