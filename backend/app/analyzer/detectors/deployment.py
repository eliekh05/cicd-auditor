from __future__ import annotations

from pathlib import Path

from app.analyzer.helpers import find, make_evidence, rel
from app.models.schemas import Command, Confidence, Evidence
from app.rules import is_production

_SKIP = frozenset({".git", "node_modules", "__pycache__", ".venv", "venv", "dist", "build"})
_COMPOSE_NAMES = frozenset({
    "compose.yml", "compose.yaml",
    "docker-compose.yml", "docker-compose.yaml",
})


def detect_docker(repo: Path) -> tuple[list[Evidence], list[Command], list[Evidence]]:
    """Returns (all_evidence, commands, production_evidence)."""
    evidence: list[Evidence] = []
    commands: list[Command] = []
    production: list[Evidence] = []

    # Dockerfile
    for df in find(repo, {"Dockerfile", "dockerfile"}):
        r = rel(repo, df)
        prod = is_production(r)
        e = make_evidence(
            r, "Dockerfile",
            "Container image definition" + ("" if prod else " (non-production path)"),
            0.98 if prod else 0.75, "docker",
            confidence=Confidence.EXPLICIT if prod else Confidence.INFERRED,
        )
        evidence.append(e)
        if prod:
            production.append(e)

        try:
            content = df.read_text(encoding="utf-8")
        except OSError:
            continue
        for line in content.splitlines():
            stripped = line.strip()
            if not stripped.startswith("RUN "):
                continue
            cmd_part = stripped[4:].strip()
            if any(kw in cmd_part for kw in ("pip install", "npm install", "yarn install")):
                continue
            commands.append(Command(
                cmd=cmd_part, source=r, method="Dockerfile RUN",
                score=0.85, category="docker", pipeline_eligible=False,
            ))

    # Docker Compose
    for path in repo.rglob("*"):
        if not path.is_file() or path.name not in _COMPOSE_NAMES:
            continue
        if _SKIP & set(path.relative_to(repo).parts):
            continue
        r = rel(repo, path)
        if not is_production(r):
            continue
        e = make_evidence(
            r, "Docker Compose",
            "Multi-container orchestration manifest",
            0.99, "docker-compose",
        )
        evidence.append(e)
        production.append(e)
        commands.append(Command(
            cmd=f"docker compose -f {path.name} build",
            source=r, method="Docker Compose",
            score=0.98, category="build", pipeline_eligible=True,
        ))

    return evidence, commands, production


def detect_kubernetes(repo: Path) -> list[Evidence]:
    evidence: list[Evidence] = []
    seen: set[str] = set()

    for path in repo.rglob("*"):
        if not path.is_file() or path.suffix not in {".yml", ".yaml"}:
            continue
        if _SKIP & set(path.relative_to(repo).parts):
            continue
        r = rel(repo, path)
        if not is_production(r) or r in seen:
            continue
        try:
            raw = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if "apiVersion:" in raw and "kind:" in raw:
            evidence.append(make_evidence(r, "Kubernetes manifest", "K8s resource manifest", 0.98, "kubernetes"))
            seen.add(r)

    # Helm
    for helm in find(repo, {"Chart.yaml"}):
        r = rel(repo, helm)
        if is_production(r):
            evidence.append(make_evidence(r, "Helm chart", "Helm Chart.yaml detected", 0.98, "helm"))

    # SPA build configs treated as static hosting targets
    for spa in find(repo, {"vite.config.js", "vite.config.ts", "next.config.js", "nuxt.config.js"}):
        r = rel(repo, spa)
        if is_production(r):
            evidence.append(make_evidence(
                r, "SPA build config",
                f"Static hosting target via {spa.name}",
                0.95, "static-hosting",
            ))

    return evidence


def detect_env(repo: Path) -> list[Evidence]:
    evidence: list[Evidence] = []
    for path in find(repo, {".env.example", ".env.sample", "env.example"}):
        r = rel(repo, path)
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except OSError:
            continue
        for raw in lines:
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            var = line.split("=")[0].strip()
            evidence.append(make_evidence(
                r, ".env.example",
                f"Environment variable: {var}",
                0.75, var,
                confidence=Confidence.INFERRED,
            ))
    return evidence
