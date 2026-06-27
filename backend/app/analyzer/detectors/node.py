from __future__ import annotations

import json
from pathlib import Path

from app.analyzer.helpers import find, make_evidence, rel
from app.models.schemas import Command, Dependency, Evidence

_TEST_NAMES = frozenset({
    "test", "tests", "test:run", "test:unit", "test:integration",
    "test:ci", "test:all", "coverage", "ci", "check",
})
_BUILD_NAMES = frozenset({
    "build", "compile", "package", "dist", "bundle", "prepare",
    "build:prod", "build:production",
})
_INSTALL_NAMES = frozenset({"init", "setup", "install", "bootstrap", "deps"})
# These are dev-server / preview scripts — never pipeline steps
_DEV_ONLY = frozenset({
    "dev", "start", "serve", "watch", "preview", "storybook",
    "eject", "analyze", "postinstall",
})

_TEST_TOOLS = frozenset({"jest", "vitest", "cypress", "mocha", "playwright", "karma", "jasmine"})


def _script_category(name: str, cmd: str) -> tuple[str, bool]:
    """Return (category, pipeline_eligible)."""
    n = name.lower()

    if n in _DEV_ONLY or n.startswith("dev:") or n.startswith("start:"):
        return "dev", False  # never put in pipeline

    if n in _TEST_NAMES or n.startswith("test"):
        return "test", True
    if n in _BUILD_NAMES or "build" in n:
        return "build", True
    if n in _INSTALL_NAMES:
        return "install", True

    # Check the command itself
    cmd_lower = cmd.lower()
    if any(t in cmd_lower for t in _TEST_TOOLS | {"pytest", "coverage"}):
        return "test", True
    if "build" in cmd_lower or "compile" in cmd_lower or "webpack" in cmd_lower:
        return "build", True

    return "other", False  # unknown scripts are not pipeline-eligible


def detect(repo: Path) -> tuple[list[Evidence], list[Dependency], list[Command]]:
    evidence: list[Evidence] = []
    deps: list[Dependency] = []
    commands: list[Command] = []

    for pkg in find(repo, {"package.json"}):
        r = rel(repo, pkg)
        # Derive working directory relative to repo root (for monorepos)
        pkg_dir = str(pkg.parent.relative_to(repo)) if pkg.parent != repo else ""

        try:
            data = json.loads(pkg.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue

        has_package_manager = "workspaces" in data  # monorepo root
        pm = "npm"
        if (pkg.parent / "yarn.lock").exists():
            pm = "yarn"
        elif (pkg.parent / "pnpm-lock.yaml").exists():
            pm = "pnpm"

        # Synthesise install command for this package
        install_cmd = f"{pm} install" if pm != "npm" else "npm ci"
        commands.append(Command(
            cmd=install_cmd,
            source=r,
            method="package.json (synthesised install)",
            score=0.98,
            category="install",
            pipeline_eligible=True,
            working_dir=pkg_dir or None,
        ))

        # Scripts
        for name, cmd in (data.get("scripts") or {}).items():
            cat, eligible = _script_category(name, str(cmd))
            if cat == "other":
                continue
            npm_cmd = f"{pm} run {name}" if pm != "npm" else f"npm run {name}"
            commands.append(Command(
                cmd=npm_cmd,
                source=r,
                method="package.json scripts",
                score=0.98,
                category=cat,
                pipeline_eligible=eligible,
                working_dir=pkg_dir or None,
            ))
            evidence.append(make_evidence(
                r, "package.json scripts",
                f"Script '{name}': {cmd}",
                0.98, name,
            ))

        # Dependencies
        for section in ("dependencies", "devDependencies", "peerDependencies"):
            for name, version in (data.get(section) or {}).items():
                kind = "runtime" if section == "dependencies" else "dev"
                deps.append(Dependency(name=name, version=str(version), source=r, kind=kind))
                evidence.append(make_evidence(
                    r, f"package.json {section}",
                    f"Dependency '{name}' @ {version}",
                    0.98, name,
                ))

        # Engines
        for runtime, version in (data.get("engines") or {}).items():
            evidence.append(make_evidence(
                r, "package.json engines",
                f"Runtime constraint: {runtime} {version}",
                0.98, runtime,
            ))

    return evidence, deps, commands
