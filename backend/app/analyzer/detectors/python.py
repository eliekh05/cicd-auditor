from __future__ import annotations

import re
from pathlib import Path

from app.analyzer.helpers import find, make_evidence, rel
from app.models.schemas import Command, Confidence, Dependency, Evidence


def detect(repo: Path) -> tuple[list[Evidence], list[Dependency], list[Command]]:
    evidence: list[Evidence] = []
    deps: list[Dependency] = []
    commands: list[Command] = []

    _requirements(repo, evidence, deps, commands)
    _pyproject(repo, evidence, deps, commands)

    return evidence, deps, commands


def _requirements(repo: Path, evidence: list, deps: list, commands: list) -> None:
    for name in ("requirements.txt", "requirements-dev.txt", "requirements-test.txt"):
        for path in find(repo, {name}):
            r = rel(repo, path)
            pkg_dir = str(path.parent.relative_to(repo)) if path.parent != repo else ""

            try:
                lines = path.read_text(encoding="utf-8").splitlines()
            except OSError:
                continue

            has_deps = False
            for raw in lines:
                line = raw.strip()
                if not line or line.startswith("#") or line.startswith("-"):
                    continue
                m = re.match(r"^([\w\-_.]+)([><=!~,\s].*)?$", line.split("#")[0].strip())
                if not m:
                    continue
                pkg, ver = m.group(1), (m.group(2) or "").strip() or None
                deps.append(Dependency(name=pkg, version=ver, source=r, kind="runtime"))
                evidence.append(make_evidence(
                    r, "requirements.txt",
                    f"Python dependency '{pkg}'" + (f" {ver}" if ver else ""),
                    0.98, pkg,
                ))
                has_deps = True

            # Synthesise pip install command if the file has real deps
            if has_deps:
                install_cmd = f"pip install -r {name}"
                commands.append(Command(
                    cmd=install_cmd,
                    source=r,
                    method="requirements.txt (synthesised install)",
                    score=0.98,
                    category="install",
                    pipeline_eligible=True,
                    working_dir=pkg_dir or None,
                ))
                evidence.append(make_evidence(
                    r, "requirements.txt",
                    f"Python project requires pip install -r {name}",
                    0.98, name,
                ))


def _pyproject(repo: Path, evidence: list, deps: list, commands: list) -> None:
    for path in find(repo, {"pyproject.toml"}):
        r = rel(repo, path)
        pkg_dir = str(path.parent.relative_to(repo)) if path.parent != repo else ""
        try:
            content = path.read_text(encoding="utf-8")
        except OSError:
            continue

        evidence.append(make_evidence(
            r, "pyproject.toml",
            "Python project with pyproject.toml build system",
            0.98, "pyproject.toml",
        ))

        is_poetry = "[tool.poetry" in content
        if is_poetry:
            evidence.append(make_evidence(
                r, "pyproject.toml",
                "Poetry build system detected",
                0.95, "poetry",
                confidence=Confidence.INFERRED,
            ))
            commands.append(Command(
                cmd="poetry install",
                source=r,
                method="pyproject.toml (poetry synthesised install)",
                score=0.97,
                category="install",
                pipeline_eligible=True,
                working_dir=pkg_dir or None,
            ))
        else:
            commands.append(Command(
                cmd="pip install -e .",
                source=r,
                method="pyproject.toml (synthesised install)",
                score=0.90,
                category="install",
                pipeline_eligible=True,
                working_dir=pkg_dir or None,
            ))

        # pytest detection in pyproject
        if "[tool.pytest" in content or 'pytest' in content:
            commands.append(Command(
                cmd="pytest",
                source=r,
                method="pyproject.toml pytest config",
                score=0.95,
                category="test",
                pipeline_eligible=True,
                working_dir=pkg_dir or None,
            ))
            evidence.append(make_evidence(
                r, "pyproject.toml pytest config",
                "pytest configuration found in pyproject.toml",
                0.95, "pytest",
            ))

        # Inline script entry points (poetry.scripts)
        section = re.search(r"\[tool\.poetry\.scripts\](.*?)(?:\[|\Z)", content, re.DOTALL)
        if section:
            for line in section.group(1).splitlines():
                if "=" in line and not line.strip().startswith("#"):
                    name = line.split("=")[0].strip()
                    commands.append(Command(
                        cmd=name,
                        source=r,
                        method="pyproject.toml poetry.scripts",
                        score=0.98,
                        category="build",
                        pipeline_eligible=True,
                        working_dir=pkg_dir or None,
                    ))

        # Dependency declarations
        for m in re.finditer(r"^([\w\-]+)\s*=\s*\"[^\"]+\"", content, re.MULTILINE):
            pkg = m.group(1)
            if pkg not in ("python", "build-system", "requires"):
                deps.append(Dependency(name=pkg, version=None, source=r, kind="runtime"))
