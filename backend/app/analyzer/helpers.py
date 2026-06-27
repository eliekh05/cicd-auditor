from __future__ import annotations

from pathlib import Path

from app.models.schemas import Confidence, Evidence
from app.rules import EXPLICIT_MIN, INFERRED_MIN, is_production


def make_evidence(
    source: str,
    method: str,
    detail: str,
    score: float,
    value: str | None = None,
    *,
    confidence: Confidence | None = None,
) -> Evidence:
    if confidence is None:
        if score >= EXPLICIT_MIN:
            confidence = Confidence.EXPLICIT
        elif score >= INFERRED_MIN:
            confidence = Confidence.INFERRED
        else:
            confidence = Confidence.LOW

    return Evidence(
        source=source,
        method=method,
        detail=detail,
        score=score,
        confidence=confidence,
        value=value,
    )


def find(repo: Path, names: set[str]) -> list[Path]:
    """Locate files by name anywhere under repo, skipping hidden and vendor dirs."""
    skip = frozenset({".git", "node_modules", "__pycache__", ".venv", "venv", "dist", "build"})
    results: list[Path] = []
    for p in repo.rglob("*"):
        if not p.is_file():
            continue
        if skip & set(p.relative_to(repo).parts):
            continue
        if p.name in names:
            results.append(p)
    return results


def rel(repo: Path, path: Path) -> str:
    return str(path.relative_to(repo))
