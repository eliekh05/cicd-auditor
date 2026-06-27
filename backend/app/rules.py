"""
Thresholds and rules governing evidence classification and pipeline generation.
Centralising these prevents confidence inflation across detectors.
"""
from __future__ import annotations
from pathlib import Path

# A finding must reach this score to be EXPLICIT
EXPLICIT_MIN: float = 0.95
# Below this → LOW
INFERRED_MIN: float = 0.70

# Path segments that indicate test/demo fixtures — not production deployment evidence
NON_PRODUCTION: frozenset[str] = frozenset({
    "test", "tests", "__tests__", "spec", "specs", "demo", "demos",
    "examples", "example", "fixtures", "fixture", "mock", "mocks",
    "sample", "samples", "docs", "doc",
})

# Signals required for a Hugging Face Space to be confirmed
HF_SIGNALS: frozenset[str] = frozenset({
    "space.yaml", "space.yml", ".huggingface", "readme_front_matter",
})

# README-extracted commands are evidence only; never pipeline steps
README_COMMANDS_ELIGIBLE: bool = False

# Include full GitHub Actions boilerplate (checkout, on:, jobs:, runs-on:)
INCLUDE_BOILERPLATE: bool = True


def is_production(relative: str) -> bool:
    """Return False when the path lives inside a test/demo directory tree."""
    parts = {p.lower() for p in Path(relative).parts}
    return not (parts & NON_PRODUCTION)
