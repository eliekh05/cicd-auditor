from __future__ import annotations

from app.models.schemas import Command, Confidence, Pipeline, PipelineStep
from app.rules import EXPLICIT_MIN, INCLUDE_BOILERPLATE


# ── Helpers ───────────────────────────────────────────────────────────────────

def _step(cmd: Command, name: str) -> PipelineStep:
    c = Confidence.EXPLICIT if cmd.score >= EXPLICIT_MIN else Confidence.INFERRED
    return PipelineStep(
        name=name, cmd=cmd.cmd, source=cmd.source, method=cmd.method,
        detail=f"'{cmd.cmd}' extracted from {cmd.source} via {cmd.method}",
        score=cmd.score, confidence=c,
    )


def _pick(commands: list[Command], category: str) -> list[Command]:
    """Return pipeline-eligible commands for a category, best-candidate first."""
    eligible = [c for c in commands if c.category == category and c.pipeline_eligible]
    if not eligible:
        return []

    if category == "build":
        # Rank: prefer explicit 'build' over 'compile' over others; never 'dev'/'preview'
        def build_rank(c: Command) -> tuple:
            cmd = c.cmd.lower()
            if "build" in cmd and "dev" not in cmd and "preview" not in cmd:
                return (0, cmd)
            if "compile" in cmd or "bundle" in cmd:
                return (1, cmd)
            return (2, cmd)
        eligible.sort(key=build_rank)

    elif category == "test":
        def test_rank(c: Command) -> tuple:
            cmd = c.cmd.lower()
            if "pytest" in cmd or "jest" in cmd or "vitest" in cmd:
                return (0, cmd)
            if "test" in cmd:
                return (1, cmd)
            return (2, cmd)
        eligible.sort(key=test_rank)

    elif category == "install":
        # pip install / npm ci / poetry install — keep all, we emit one per working_dir
        pass

    return eligible


def _gha_step_block(
    indent: str,
    name: str,
    cmd: str,
    working_dir: str | None = None,
    env: dict[str, str] | None = None,
) -> list[str]:
    """Build lines for a single GitHub Actions step."""
    lines = [f"{indent}- name: {name}", f"{indent}  run: {cmd}"]
    if working_dir:
        lines.append(f"{indent}  working-directory: {working_dir}")
    if env:
        lines.append(f"{indent}  env:")
        for k, v in sorted(env.items()):
            lines.append(f"{indent}    {k}: {v}")
    return lines


def _gha(
    install: list[Command],
    build: list[Command],
    test: list[Command],
    docker: list[Command],
    env_vars: list[str],
) -> tuple[str, list[PipelineStep]]:
    steps: list[PipelineStep] = []
    lines: list[str] = []
    indent = "      "

    if INCLUDE_BOILERPLATE:
        lines += [
            "name: CI",
            "",
            "on:",
            "  push:",
            "    branches: [main, master]",
            "  pull_request:",
            "    branches: [main, master]",
            "",
            "jobs:",
            "  ci:",
            "    runs-on: ubuntu-latest",
            "",
            "    steps:",
            f"{indent}- uses: actions/checkout@v4",
        ]

    # ── Install (deduplicated by working_dir) ─────────────────────────────────
    seen_dirs: set[str | None] = set()
    for cmd in install:
        wd = cmd.working_dir
        if wd in seen_dirs:
            continue
        seen_dirs.add(wd)
        label = f"Install dependencies{' (' + wd + ')' if wd else ''}"
        steps.append(_step(cmd, label))
        lines += _gha_step_block(indent, label, cmd.cmd, wd)

    # ── Build ────────────────────────────────────────────────────────────────
    src = docker if docker else build
    seen_cmds: set[str] = set()
    for cmd in src:
        if cmd.cmd in seen_cmds:
            continue
        seen_cmds.add(cmd.cmd)
        label = f"Build{' (' + cmd.working_dir + ')' if cmd.working_dir else ''}"
        steps.append(_step(cmd, label))
        lines += _gha_step_block(indent, label, cmd.cmd, cmd.working_dir)
        break  # one build step

    # ── Test ─────────────────────────────────────────────────────────────────
    seen_t: set[str] = set()
    for cmd in test:
        if cmd.cmd in seen_t:
            continue
        seen_t.add(cmd.cmd)
        label = f"Test{' (' + cmd.working_dir + ')' if cmd.working_dir else ''}"
        steps.append(_step(cmd, label))
        lines += _gha_step_block(indent, label, cmd.cmd, cmd.working_dir)
        break  # one test step

    # ── Secrets env block ────────────────────────────────────────────────────
    if env_vars:
        unique = sorted(set(env_vars))
        lines += [f"{indent}- name: Check secrets"]
        lines += [f"{indent}  env:"]
        for var in unique:
            lines += [f"{indent}    {var}: ${{{{ secrets.{var} }}}}"]
        lines += [f"{indent}  run: echo 'Secrets injected'"]

    return "\n".join(lines), steps


def _gitlab(
    install: list[Command],
    build: list[Command],
    test: list[Command],
) -> tuple[str, list[PipelineStep]]:
    steps: list[PipelineStep] = []
    stage_list = ["install"] if install else []
    stage_list += ["build"] if build else []
    stage_list += ["test"] if test else []
    lines = ["stages:"] + [f"  - {s}" for s in stage_list] + [""]

    if install:
        steps.append(_step(install[0], "Install"))
        lines += ["install:", "  stage: install", "  script:"]
        for cmd in install[:3]:
            lines += [f"    - {cmd.cmd}"]
        lines += [""]
    if build:
        steps.append(_step(build[0], "Build"))
        lines += ["build:", "  stage: build", "  script:", f"    - {build[0].cmd}", ""]
    if test:
        steps.append(_step(test[0], "Test"))
        lines += ["test:", "  stage: test", "  script:", f"    - {test[0].cmd}", ""]
    return "\n".join(lines), steps


def _jenkins(
    install: list[Command],
    build: list[Command],
    test: list[Command],
) -> tuple[str, list[PipelineStep]]:
    steps: list[PipelineStep] = []
    lines = ["pipeline {", "    agent any", "    stages {"]

    if install:
        steps.append(_step(install[0], "Install"))
        lines += [
            "        stage('Install') {", "            steps {",
            f"                sh '{install[0].cmd}'", "            }", "        }",
        ]
    if build:
        steps.append(_step(build[0], "Build"))
        lines += [
            "        stage('Build') {", "            steps {",
            f"                sh '{build[0].cmd}'", "            }", "        }",
        ]
    if test:
        steps.append(_step(test[0], "Test"))
        lines += [
            "        stage('Test') {", "            steps {",
            f"                sh '{test[0].cmd}'", "            }", "        }",
        ]
    lines += ["    }", "}"]
    return "\n".join(lines), steps


# ── Public API ────────────────────────────────────────────────────────────────

def generate(
    commands: list[Command],
    evidence: list,
    *,
    ci_override: str | None = None,
    is_huggingface: bool = False,
    has_deploy: bool = False,
) -> tuple[Pipeline | None, list[PipelineStep]]:

    install_cmds = _pick(commands, "install")
    build_cmds   = _pick(commands, "build")
    test_cmds    = _pick(commands, "test")
    docker_cmds  = _pick(commands, "docker")

    env_vars = [
        str(e.value) for e in evidence
        if e.method == ".env.example" and e.value
    ]

    # ── Hugging Face Spaces ───────────────────────────────────────────────────
    if is_huggingface:
        hf_step = PipelineStep(
            name="Hugging Face Spaces deploy", cmd="git push huggingface main",
            source="README.md", method="Hugging Face Spaces metadata",
            detail="Push to Spaces — CI/CD runs automatically on head.",
            score=0.99, confidence=Confidence.EXPLICIT,
        )
        return Pipeline(
            kind="huggingface-spaces",
            content=(
                "# Hugging Face Spaces — no custom CI/CD needed.\n"
                "# The Space rebuilds automatically on every push to this repository."
            ),
            steps=[hf_step],
            override_note="Hugging Face Spaces runtime handles deployment",
        ), [hf_step]

    # ── Nothing useful found ─────────────────────────────────────────────────
    if not any([install_cmds, build_cmds, test_cmds, docker_cmds, env_vars]):
        return None, []

    # ── GitLab CI ─────────────────────────────────────────────────────────────
    if ci_override == "gitlab-ci":
        content, steps = _gitlab(install_cmds, build_cmds, test_cmds)
        return Pipeline(kind="gitlab-ci", content=content, steps=steps,
                        override_note="Existing .gitlab-ci.yml detected"), steps

    # ── Jenkins ───────────────────────────────────────────────────────────────
    if ci_override == "jenkins":
        content, steps = _jenkins(install_cmds, build_cmds, test_cmds)
        return Pipeline(kind="jenkins", content=content, steps=steps,
                        override_note="Existing Jenkinsfile detected"), steps

    # ── GitHub Actions (default) ──────────────────────────────────────────────
    content, steps = _gha(install_cmds, build_cmds, test_cmds, docker_cmds, env_vars)
    if not content.strip():
        return None, []

    if not has_deploy:
        content += "\n\n      # Note: no deployment stage — no deployment target detected."

    return Pipeline(kind="github-actions", content=content, steps=steps), steps
