"""
Evidence and pipeline generation rules.

These rules override implementation behavior when conflicts arise.
"""

from __future__ import annotations

# Confidence thresholds — prevent inflation
CONFIDENCE_EXPLICIT_MIN = 0.95
CONFIDENCE_INFERRED_MIN = 0.70
CONFIDENCE_LOW_MAX = 0.69

# Paths whose deployment/container artifacts are test/demo fixtures, not production targets
NON_PRODUCTION_PATH_SEGMENTS = frozenset({
    "test", "tests", "__tests__", "spec", "demo", "demos", "examples",
    "example", "fixtures", "mock", "mocks", "sample", "samples", "docs",
})

# Hugging Face Spaces requires explicit metadata — not Gradio/Docker presence alone
HF_REQUIRED_SIGNALS = frozenset({
    "space.yaml",
    "space.yml",
    ".huggingface",
    "readme_front_matter",
})

# Commands forbidden unless found verbatim in repository files
FORBIDDEN_INVENTED_COMMANDS = frozenset({
    "docker build -t app:latest .",
    "mvn test",
    "mvn package",
    "./gradlew build",
    "./gradlew test",
    "poetry install",
    "npm test",
    "pytest",
})

# README-sourced commands are evidence only — never pipeline steps
README_COMMAND_PIPELINE_ELIGIBLE = False

# Platform boilerplate (checkout, triggers, branches) must not appear in generated pipelines
INCLUDE_PLATFORM_BOILERPLATE = False
