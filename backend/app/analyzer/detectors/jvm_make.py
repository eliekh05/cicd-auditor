from __future__ import annotations

import re
from pathlib import Path

from app.analyzer.helpers import find, make_evidence, rel
from app.models.schemas import Command, Dependency, Evidence

_TEST_TARGETS = frozenset({"test", "tests", "ci", "coverage", "check"})
_BUILD_TARGETS = frozenset({"build", "compile", "package", "dist", "publish", "release"})
_INSTALL_TARGETS = frozenset({"init", "setup", "install", "bootstrap", "deps"})


def _make_category(target: str) -> str:
    t = target.lower()
    if t in _TEST_TARGETS or t.startswith("test"):
        return "test"
    if t in _BUILD_TARGETS or "build" in t:
        return "build"
    if t in _INSTALL_TARGETS:
        return "install"
    return "build"


def detect(repo: Path) -> tuple[list[Evidence], list[Dependency], list[Command]]:
    evidence: list[Evidence] = []
    deps: list[Dependency] = []
    commands: list[Command] = []

    # Maven
    for pom in find(repo, {"pom.xml"}):
        r = rel(repo, pom)
        evidence.append(make_evidence(r, "pom.xml", "Maven project detected", 0.98, "Maven"))
        try:
            content = pom.read_text(encoding="utf-8", errors="replace")
        except OSError:
            content = ""
        if "junit" in content.lower():
            evidence.append(make_evidence(r, "pom.xml", "JUnit test dependency found", 0.95, "JUnit"))
        # Extract <artifactId> dependencies (top-level only)
        for m in re.finditer(r"<artifactId>([^<]+)</artifactId>", content):
            name = m.group(1).strip()
            deps.append(Dependency(name=name, version=None, source=r, kind="runtime"))

    # Gradle
    for gradle in find(repo, {"build.gradle", "build.gradle.kts"}):
        r = rel(repo, gradle)
        evidence.append(make_evidence(r, "Gradle", "Gradle project detected", 0.98, "Gradle"))

    # Makefile
    for mk in find(repo, {"Makefile", "makefile", "GNUmakefile"}):
        r = rel(repo, mk)
        try:
            content = mk.read_text(encoding="utf-8")
        except OSError:
            continue
        for line in content.splitlines():
            m = re.match(r"^([a-zA-Z0-9_-]+)\s*:", line)
            if not m or line.startswith("\t") or line.startswith("."):
                continue
            target = m.group(1)
            if target == ".PHONY":
                continue
            cat = _make_category(target)
            commands.append(Command(
                cmd=f"make {target}", source=r,
                method="Makefile target",
                score=0.98, category=cat,
                pipeline_eligible=True,
            ))
            evidence.append(make_evidence(
                r, "Makefile target",
                f"Target '{target}' declared",
                0.98, target,
            ))

    return evidence, deps, commands
