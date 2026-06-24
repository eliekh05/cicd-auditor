from __future__ import annotations

from pathlib import Path
from app.analyzer.detectors.base import RepositoryCommand
from app.models.schemas import ConfidenceLevel, GeneratedPipeline, PipelineStep
from app.rules.evidence_rules import CONFIDENCE_EXPLICIT_MIN, INCLUDE_PLATFORM_BOILERPLATE


def _step(cmd: RepositoryCommand, step_name: str) -> PipelineStep:
    level = (
        ConfidenceLevel.EXPLICIT
        if cmd.confidence >= CONFIDENCE_EXPLICIT_MIN
        else ConfidenceLevel.INFERRED
    )
    return PipelineStep(
        name=step_name,
        command=cmd.command,
        source_file=cmd.source_file,
        detection_method=cmd.detection_method,
        reasoning=f"Command '{cmd.command}' from {cmd.source_file} via {cmd.detection_method}",
        confidence=cmd.confidence,
        confidence_level=level,
    )


def _pick_commands(commands: list[RepositoryCommand], category: str) -> list[RepositoryCommand]:
    eligible = [
        c for c in commands
        if c.category == category and c.pipeline_eligible
    ]
    
    # Prioritization logic for test targets
    if category == "test":
        eligible.sort(key=lambda c: (
            0 if c.command in {"make test", "make ci", "make coverage", "npm run test", "npm test"} else 1,
            0 if "test" in c.command.lower() else 1,
            c.command,
        ))
    # Prioritization logic for build/install targets
    elif category in {"build", "install"}:
        eligible.sort(key=lambda c: (
            0 if "build" in c.command.lower() or "compile" in c.command.lower() else 1,
            c.command,
        ))
    return eligible


def generate_github_actions(
    build_cmds: list[RepositoryCommand],
    test_cmds: list[RepositoryCommand],
    docker_cmds: list[RepositoryCommand],
    env_vars: list[str],
) -> tuple[str, list[PipelineStep]]:
    lines = []
    steps = []

    if INCLUDE_PLATFORM_BOILERPLATE:
        lines.extend([
            "name: CI Pipeline",
            "on:",
            "  push:",
            "    branches: [ main, master ]",
            "  pull_request:",
            "    branches: [ main, master ]",
            "jobs:",
            "  build-and-test:",
            "    runs-on: ubuntu-latest",
            "    steps:",
            "      - name: Checkout repository",
            "        uses: actions/checkout@v4",
        ])
    else:
        lines.extend([
            "# Steps below are derived solely from repository evidence.",
            "# Platform boilerplate (checkout, triggers, runners) intentionally omitted.",
            "name: CI Pipeline (evidence-derived steps only)",
            "",
            "jobs:",
            "  evidence-derived:",
            "    steps:",
        ])

    indent = "      " if INCLUDE_PLATFORM_BOILERPLATE else "      "

    # 1. Execute Build Commands (e.g. npm run build, docker compose build)
    # If Docker Compose configuration exists, prioritize it for unified architecture deployments
    if docker_cmds:
        # Deduplicate compose items
        seen_docker = set()
        for cmd in docker_cmds:
            if "build" in cmd.command and cmd.command not in seen_docker:
                seen_docker.add(cmd.command)
                steps.append(_step(cmd, "Build"))
                lines.append(f"{indent}- name: Build")
                lines.append(f"{indent}  run: {cmd.command}")
    elif build_cmds:
        seen_build = set()
        for cmd in build_cmds:
            if cmd.command not in seen_build:
                seen_build.add(cmd.command)
                steps.append(_step(cmd, "Build"))
                lines.append(f"{indent}- name: Build")
                lines.append(f"{indent}  run: {cmd.command}")
                break # Extract primary production artifact generation command

    # 2. Execute Framework Unit/Integration Tests
    if test_cmds:
        seen_test = set()
        for cmd in test_cmds:
            if cmd.command not in seen_test:
                seen_test.add(cmd.command)
                steps.append(_step(cmd, "Test"))
                lines.append(f"{indent}- name: Test")
                lines.append(f"{indent}  run: {cmd.command}")
                break # Isolate to primary text execution harness

    # 3. Handle Discovered Environment Context Vectors Safely
    if env_vars:
        lines.append(f"{indent}- name: Environment placeholders")
        lines.append(f"{indent}  env:")
        # Deduplicate keys cleanly
        for var in sorted(list(set(env_vars))):
            lines.append(f"{indent}    {var}: ${{{{ secrets.{var} }}}}")

    return "\n".join(lines), steps


def generate_gitlab_ci(
    build_cmds: list[RepositoryCommand], test_cmds: list[RepositoryCommand]
) -> tuple[str, list[PipelineStep]]:
    lines = ["stages:", "  - build", "  - test", ""]
    steps = []

    if build_cmds:
        cmd = build_cmds[0]
        steps.append(_step(cmd, "Build Stage"))
        lines.extend([
            "build-job:",
            "  stage: build",
            f"  script:",
            f"    - {cmd.command}",
            "",
        ])

    if test_cmds:
        cmd = test_cmds[0]
        steps.append(_step(cmd, "Test Stage"))
        lines.extend([
            "test-job:",
            "  stage: test",
            f"  script:",
            f"    - {cmd.command}",
            "",
        ])

    return "\n".join(lines), steps


def generate_jenkinsfile(
    build_cmds: list[RepositoryCommand], test_cmds: list[RepositoryCommand]
) -> tuple[str, list[PipelineStep]]:
    lines = ["pipeline {", "    agent any", "    stages {"]
    steps = []

    if build_cmds:
        cmd = build_cmds[0]
        steps.append(_step(cmd, "Build Stage"))
        lines.extend([
            "        stage('Build') {",
            "            steps {",
            f"                sh '{cmd.command}'",
            "            }",
            "        }",
        ])

    if test_cmds:
        cmd = test_cmds[0]
        steps.append(_step(cmd, "Test Stage"))
        lines.extend([
            "        stage('Test') {",
            "            steps {",
            f"                sh '{cmd.command}'",
            "            }",
            "        }",
        ])

    lines.extend(["    }", "}"])
    return "\n".join(lines), steps


def generate_pipeline(
    repo_path: Path,
    commands: list[RepositoryCommand],
    evidence_items: list,
    ci_override: str | None = None,
    hf_detected: bool = False,
    has_production_deployment: bool = False,
    is_native_artifact: bool = False,
) -> tuple[GeneratedPipeline | None, list[PipelineStep]]:
    
    # 1. Isolate commands across categories using exact priority routines
    build_commands = _pick_commands(commands, "build")
    test_commands = _pick_commands(commands, "test")
    docker_commands = _pick_commands(commands, "docker")

    # 2. Extract variable environment markers safely from primitives or dictionaries
    env_vars = []
    for e in evidence_items:
        if e.detection_method == ".env.example variable" and e.value:
            val = e.value
            if isinstance(val, dict):
                val = val.get("dependency") or val.get("runtime") or str(val)
            env_vars.append(str(val))

    # 3. Route to dedicated multi-tier ecosystem generation models
    if hf_detected:
        content = (
            "# Hugging Face Spaces direct deployment configuration managed via Space infrastructure.\n"
            "# Continuous synchronization executes automatically on repository head push updates."
        )
        steps = [PipelineStep(
            name="Hugging Face Spaces Deployment",
            command="git push huggingface main",
            source_file="README.md",
            detection_method="Hugging Face Space metadata signature",
            reasoning="Direct git integration matching Space runtime metrics configuration patterns.",
            confidence=0.99,
            confidence_level=ConfidenceLevel.EXPLICIT
        )]
        return GeneratedPipeline(
            pipeline_type="huggingface-spaces",
            content=content,
            steps=steps,
            override_reason="Explicit Hugging Face Spaces metadata — GitHub Actions deployment skipped",
        ), steps

    # Fallback to empty context boundaries safely if no matching files are found
    if not build_commands and not test_commands and not docker_commands and not env_vars:
        return None, []

    if ci_override == "gitlab-ci":
        content, steps = generate_gitlab_ci(build_commands, test_commands)
        if not content.strip():
            return None, []
        return GeneratedPipeline(
            pipeline_type="gitlab-ci",
            content=content,
            steps=steps,
            override_reason="Existing .gitlab-ci.yml detected",
        ), steps

    if ci_override == "jenkins":
        content, steps = generate_jenkinsfile(build_commands, test_commands)
        if not content.strip():
            return None, []
        return GeneratedPipeline(
            pipeline_type="jenkins",
            content=content,
            steps=steps,
            override_reason="Existing Jenkinsfile detected",
        ), steps

    # Default directly to comprehensive GitHub Actions compilation mapping
    content, steps = generate_github_actions(build_commands, test_commands, docker_commands, env_vars)
    if not content.strip():
        return None, []

    if not has_production_deployment:
        content += "\n# No deployment stage — no deployment target detected from repository evidence."

    return GeneratedPipeline(pipeline_type="github-actions", content=content, steps=steps), steps
