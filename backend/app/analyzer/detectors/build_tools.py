from __future__ import annotations

import json
import re
from pathlib import Path

from app.analyzer.detectors.base import RepositoryCommand, evidence, find_files
from app.models.schemas import ConfidenceLevel, DependencyNode, EvidenceItem

_TEST_SCRIPT_NAMES = frozenset({"test", "tests", "test:run", "test:unit", "test:ci", "coverage", "ci"})
_BUILD_SCRIPT_NAMES = frozenset({"build", "compile", "package", "dist", "prepare"})


def _script_category(name: str, command: str) -> str:
    name_lower = name.lower()
    if name_lower in _TEST_SCRIPT_NAMES or name_lower.startswith("test"):
        return "test"
    if name_lower in _BUILD_SCRIPT_NAMES or "build" in name_lower:
        return "build"
    if "install" in name_lower or name_lower in {"init", "setup"}:
        return "install"
    if any(kw in command.lower() for kw in ("pytest", "jest", "vitest", "cypress", "mocha")):
        return "test"
    return "build"


def _make_target_category(target: str) -> str:
    target_lower = target.lower()
    if target_lower in {"test", "tests", "ci", "coverage", "test-readme"} or target_lower.startswith("test"):
        return "test"
    if target_lower in {"build", "compile", "package", "dist", "publish"}:
        return "build"
    if target_lower in {"init", "setup", "install"}:
        return "install"
    return "build"


def analyze_package_json(repo_path: Path) -> tuple[list[EvidenceItem], list[DependencyNode], list[RepositoryCommand]]:
    items: list[EvidenceItem] = []
    deps: list[DependencyNode] = []
    commands: list[RepositoryCommand] = []

    for pkg_path in find_files(repo_path, {"package.json"}):
        rel = str(pkg_path.relative_to(repo_path))
        try:
            data = json.loads(pkg_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue

        if "scripts" in data and isinstance(data["scripts"], dict):
            for name, cmd in data["scripts"].items():
                npm_cmd = f"npm run {name}"
                category = _script_category(name, cmd)
                commands.append(RepositoryCommand(
                    command=npm_cmd,
                    source_file=rel,
                    detection_method="package.json scripts",
                    confidence=0.98,
                    category=category,
                ))
                items.append(evidence(
                    rel, "package.json scripts",
                    f"Script '{name}' defined: {cmd}",
                    0.98, {"script": name, "command": cmd},
                ))

        for dep_type in ("dependencies", "devDependencies", "peerDependencies"):
            section = data.get(dep_type, {})
            if isinstance(section, dict):
                for name, version in section.items():
                    deps.append(DependencyNode(
                        name=name, version=str(version),
                        source_file=rel, confidence_level=ConfidenceLevel.EXPLICIT,
                    ))
                    items.append(evidence(
                        rel, f"package.json {dep_type}",
                        f"Dependency '{name}' at version '{version}'",
                        0.98, {"dependency": name, "version": version},
                    ))

        engines = data.get("engines", {})
        if isinstance(engines, dict):
            for runtime, version in engines.items():
                items.append(evidence(
                    rel, "package.json engines",
                    f"Runtime '{runtime}' requires '{version}'",
                    0.98, {"runtime": runtime, "version": version},
                ))

        all_deps = {**data.get("dependencies", {}), **data.get("devDependencies", {})}
        for dep_name in all_deps:
            items.append(evidence(
                rel, "package.json dependency",
                f"Dependency '{dep_name}' declared",
                0.98, dep_name,
            ))

    return items, deps, commands


def analyze_requirements(repo_path: Path) -> tuple[list[EvidenceItem], list[DependencyNode]]:
    items: list[EvidenceItem] = []
    deps: list[DependencyNode] = []

    for req_name in ("requirements.txt", "requirements-dev.txt", "requirements-test.txt"):
        for req_path in find_files(repo_path, {req_name}):
            rel = str(req_path.relative_to(repo_path))
            try:
                lines = req_path.read_text(encoding="utf-8").splitlines()
            except OSError:
                continue

            for line in lines:
                line = line.strip()
                if not line or line.startswith("#") or line.startswith("-"):
                    continue
                match = re.match(r"^([a-zA-Z0-9_\-.]+)([><=!~].*)?$", line.split("#")[0].strip())
                if match:
                    name, version = match.group(1), match.group(2) or None
                    deps.append(DependencyNode(
                        name=name, version=version,
                        source_file=rel, confidence_level=ConfidenceLevel.EXPLICIT,
                    ))
                    items.append(evidence(
                        rel, "requirements.txt parsing",
                        f"Python dependency '{name}'" + (f" version '{version}'" if version else ""),
                        0.98, {"dependency": name, "version": version},
                    ))

    return items, deps


def analyze_pyproject(repo_path: Path) -> tuple[list[EvidenceItem], list[DependencyNode], list[RepositoryCommand]]:
    items: list[EvidenceItem] = []
    deps: list[DependencyNode] = []
    commands: list[RepositoryCommand] = []

    for pyproject in find_files(repo_path, {"pyproject.toml"}):
        rel = str(pyproject.relative_to(repo_path))
        try:
            content = pyproject.read_text(encoding="utf-8")
        except OSError:
            continue

        items.append(evidence(
            rel, "pyproject.toml presence",
            "Python project uses pyproject.toml build system",
            0.98, "pyproject.toml",
        ))

        if "[tool.poetry" in content:
            items.append(evidence(
                rel, "pyproject.toml build system",
                "Poetry configuration section detected",
                0.95, "poetry",
                level=ConfidenceLevel.INFERRED,
            ))

        dep_pattern = re.compile(r'^[\w\-]+\s*=\s*"[^"]+"', re.MULTILINE)
        for match in dep_pattern.finditer(content):
            line = match.group(0)
            name = line.split("=")[0].strip()
            if name not in ("python", "build-system"):
                deps.append(DependencyNode(
                    name=name, version=None,
                    source_file=rel, confidence_level=ConfidenceLevel.EXPLICIT,
                ))

        script_section = re.search(r"\[tool\.poetry\.scripts\](.*?)(?:\[|\Z)", content, re.DOTALL)
        if script_section:
            for line in script_section.group(1).splitlines():
                if "=" in line and not line.strip().startswith("#"):
                    script_name = line.split("=")[0].strip()
                    commands.append(RepositoryCommand(
                        command=script_name,
                        source_file=rel,
                        detection_method="pyproject.toml poetry.scripts",
                        confidence=0.98,
                        category="build",
                    ))

    return items, deps, commands


def analyze_maven_gradle(repo_path: Path) -> tuple[list[EvidenceItem], list[DependencyNode], list[RepositoryCommand]]:
    """Detect Maven/Gradle presence only — do not invent mvn/gradlew commands."""
    items: list[EvidenceItem] = []
    deps: list[DependencyNode] = []
    commands: list[RepositoryCommand] = []

    for pom in find_files(repo_path, {"pom.xml"}):
        rel = str(pom.relative_to(repo_path))
        items.append(evidence(rel, "pom.xml presence", "Maven project detected", 0.98, "Maven"))
        content = pom.read_text(encoding="utf-8", errors="replace")
        if "junit" in content.lower():
            items.append(evidence(
                rel, "pom.xml test dependency",
                "JUnit dependency reference found in pom.xml",
                0.95, "JUnit",
                level=ConfidenceLevel.INFERRED,
            ))

    for gradle in find_files(repo_path, {"build.gradle", "build.gradle.kts"}):
        rel = str(gradle.relative_to(repo_path))
        items.append(evidence(rel, "Gradle build file", "Gradle project detected", 0.98, "Gradle"))

    return items, deps, commands


def analyze_makefile(repo_path: Path) -> tuple[list[EvidenceItem], list[RepositoryCommand]]:
    items: list[EvidenceItem] = []
    commands: list[RepositoryCommand] = []

    for makefile in find_files(repo_path, {"Makefile", "makefile", "GNUmakefile"}):
        rel = str(makefile.relative_to(repo_path))
        try:
            content = makefile.read_text(encoding="utf-8")
        except OSError:
            continue

        for line in content.splitlines():
            match = re.match(r"^([a-zA-Z0-9_-]+)\s*:", line)
            if match and not line.startswith("\t") and not line.startswith("."):
                target = match.group(1)
                if target == ".PHONY":
                    continue
                category = _make_target_category(target)
                commands.append(RepositoryCommand(
                    command=f"make {target}",
                    source_file=rel,
                    detection_method="Makefile target",
                    confidence=0.98,
                    category=category,
                ))
                items.append(evidence(
                    rel, "Makefile target",
                    f"Make target '{target}' found",
                    0.98, target,
                ))

    return items, commands
