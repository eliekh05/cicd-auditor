from __future__ import annotations

import re
from pathlib import Path

from app.analyzer.detectors.base import evidence, find_files
from app.models.schemas import ConfidenceLevel, EvidenceItem


def detect_huggingface_space(repo_path: Path) -> tuple[bool, list[EvidenceItem], str | None]:
    """
    Hugging Face Spaces detection requires explicit metadata signals.
    Gradio app.py or Dockerfile references alone are insufficient.
    """
    items: list[EvidenceItem] = []
    explicit_signals: set[str] = set()

    readme_paths = find_files(repo_path, {"README.md", "README.MD", "readme.md"})
    for readme in readme_paths:
        if str(readme.relative_to(repo_path)).count("/") > 0:
            continue
        rel = str(readme.relative_to(repo_path))
        try:
            content = readme.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue

        yaml_block = re.search(r"^---\s*\n(.*?)\n---", content, re.DOTALL | re.MULTILINE)
        if yaml_block:
            block = yaml_block.group(1).lower()
            if "sdk:" in block or "app_file:" in block:
                explicit_signals.add("readme_front_matter")
                items.append(evidence(
                    rel, "Hugging Face Spaces YAML front matter",
                    "Root README contains Spaces YAML front matter with sdk/app_file",
                    0.98, yaml_block.group(0),
                ))

        if re.search(r"huggingface\.co/spaces/", content, re.IGNORECASE):
            explicit_signals.add("readme_hf_url")
            items.append(evidence(
                rel, "Hugging Face Spaces URL reference",
                "Root README references huggingface.co/spaces/",
                0.98, "huggingface-spaces",
            ))

    for space_yaml in find_files(repo_path, {"space.yaml", "space.yml"}):
        rel = str(space_yaml.relative_to(repo_path))
        explicit_signals.add("space.yaml")
        items.append(evidence(
            rel, "space.yaml",
            "Dedicated Hugging Face Space configuration file detected",
            0.98, "huggingface-spaces",
        ))

    hf_config_dirs = [d for d in repo_path.rglob(".huggingface") if d.is_dir()]
    if hf_config_dirs:
        explicit_signals.add(".huggingface")
        for d in hf_config_dirs:
            rel = str(d.relative_to(repo_path))
            items.append(evidence(
                rel, ".huggingface directory",
                "Hugging Face configuration directory detected",
                0.98, "huggingface-spaces",
            ))

    for app_py in find_files(repo_path, {"app.py"}):
        rel = str(app_py.relative_to(repo_path))
        if rel.count("/") > 0:
            continue
        try:
            content = app_py.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if "import gradio" in content or "from gradio" in content:
            items.append(evidence(
                rel, "Gradio app.py",
                "Root app.py imports Gradio — supporting signal only, not sufficient alone",
                0.70, "gradio",
                level=ConfidenceLevel.INFERRED,
            ))

    detected = bool(explicit_signals)
    message = None
    if detected:
        message = (
            "This repository is a Hugging Face Space. "
            "CI/CD is managed by Hugging Face Spaces runtime."
        )

    return detected, items, message


def extract_spaces_config(repo_path: Path) -> str | None:
    """Return only verbatim Spaces config from repository — no placeholders."""
    for space_yaml in find_files(repo_path, {"space.yaml", "space.yml"}):
        try:
            return space_yaml.read_text(encoding="utf-8")
        except OSError:
            continue

    readme_paths = find_files(repo_path, {"README.md"})
    for readme in readme_paths:
        if str(readme.relative_to(repo_path)).count("/") > 0:
            continue
        try:
            content = readme.read_text(encoding="utf-8")
            yaml_match = re.search(r"^---\s*\n(.*?)\n---", content, re.DOTALL)
            if yaml_match and ("sdk:" in yaml_match.group(1).lower() or "app_file:" in yaml_match.group(1).lower()):
                return yaml_match.group(0)
        except OSError:
            continue

    return None
