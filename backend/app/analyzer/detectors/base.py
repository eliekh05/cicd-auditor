from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from app.models.schemas import ConfidenceLevel, EvidenceItem
from app.rules.evidence_rules import (
    CONFIDENCE_EXPLICIT_MIN,
    CONFIDENCE_INFERRED_MIN,
    CONFIDENCE_LOW_MAX,
)


def evidence(
    source_file: str,
    detection_method: str,
    reasoning: str,
    confidence: float,
    value=None,
    level: ConfidenceLevel | None = None,
) -> EvidenceItem:
    if level is None:
        if confidence >= CONFIDENCE_EXPLICIT_MIN:
            level = ConfidenceLevel.EXPLICIT
        elif confidence >= CONFIDENCE_INFERRED_MIN:
            level = ConfidenceLevel.INFERRED
        else:
            level = ConfidenceLevel.LOW
    return EvidenceItem(
        source_file=source_file,
        detection_method=detection_method,
        reasoning=reasoning,
        confidence=confidence,
        confidence_level=level,
        value=value,
    )


def find_files(repo_path: Path, names: set[str]) -> list[Path]:
    found: list[Path] = []
    for path in repo_path.rglob("*"):
        if path.is_file() and path.name in names:
            found.append(path)
    return found


def is_production_path(relative_path: str) -> bool:
    """Return False for test/demo/fixture paths — not valid deployment evidence."""
    from app.rules.evidence_rules import NON_PRODUCTION_PATH_SEGMENTS

    parts = {p.lower() for p in Path(relative_path).parts}
    return not (parts & NON_PRODUCTION_PATH_SEGMENTS)


@dataclass(frozen=True)
class RepositoryCommand:
    command: str
    source_file: str
    detection_method: str
    confidence: float
    category: str  # build | test | install | docker

    @property
    def pipeline_eligible(self) -> bool:
        from app.rules.evidence_rules import README_COMMAND_PIPELINE_ELIGIBLE

        if self.confidence < CONFIDENCE_EXPLICIT_MIN:
            return False
        if self.detection_method == "README explicit command" and not README_COMMAND_PIPELINE_ELIGIBLE:
            return False
        return True
