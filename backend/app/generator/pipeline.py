from __future__ import annotations

from pathlib import Path

from app.analyzer.detectors.base import RepositoryCommand
from app.analyzer.detectors.huggingface import extract_spaces_config
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
    if category == "test":
        eligible.sort(key=lambda c: (
            0 if c.command in {"make test", "make ci", "make coverage"} else 1,
            0 if c.command.startswith("npm run test") else 1,
            c.command,
        ))
    elif category in {"build", "install"}:
        eligible.sort(key=lambda c: (
            0 if c.category == "build" else 1,
            0 if "build" in c.command.lower() else 1,
            c.command,
        ))
    return eligible


def _format_steps_yaml(commands: list[RepositoryCommand], step_names: list[str]) -> tuple[list[str], list[PipelineStep]]:
    yaml_lines: list[str] = []
    steps: list[PipelineStep] = []
    for cmd, name in zip(commands, step_names):
        yaml_lines.append(f"      - name: {name}")
        yaml_lines.append(f"        run: {cmd.command}")
        steps.append(_step(cmd, name))
    return yaml_lines, steps


def generate_github_actions(
    build_commands: list[RepositoryCommand],
    test_commands: list[RepositoryCommand],
    docker_commands: list[RepositoryCommand],
    env_vars: list[str],
) -> tuple[str, list[PipelineStep]]:
    steps: list[PipelineStep] = []
    yaml_steps: list[str] = []

    if build_commands:
        lines, build_steps = _format_steps_yaml(build_commands[:1], ["Build"])
        yaml_steps.extend(lines)
        steps.extend(build_steps)

    if test_commands:
        lines, test_steps = _format_steps_yaml(test_commands[:1], ["Test"])
        yaml_steps.extend(lines)
        steps.extend(test_steps)

    if docker_commands:
        lines, docker_steps = _format_steps_yaml(docker_commands[:1], ["Docker RUN"])
        yaml_steps.extend(lines)
        steps.extend(docker_steps)

    if env_vars:
        yaml_steps.append("      - name: Environment placeholders")
        yaml_steps.append("        env:")
        for var in env_vars[:10]:
            yaml_steps.append(f"          {var}: ${{{{ secrets.{var} }}}}")

    if not yaml_steps:
        return "", steps

    header = [
        "# Steps below are derived solely from repository evidence.",
        "# Platform boilerplate (checkout, triggers, runners) intentionally omitted.",
        "name: CI Pipeline (evidence-derived steps only)",
        "",
        "jobs:",
        "  evidence-derived:",
        "    steps:",
    ]
    if not INCLUDE_PLATFORM_BOILERPLATE:
        pass

    content = "\n".join([*header, *yaml_steps])
    return content, steps


def generate_gitlab_ci(
    build_commands: list[RepositoryCommand],
    test_commands: list[RepositoryCommand],
) -> tuple[str, list[PipelineStep]]:
    steps: list[PipelineStep] = []
    lines = ["# Evidence-derived steps only", "stages:", "  - build", "  - test", ""]

    if build_commands:
        cmd = build_commands[0]
        lines.extend(["build:", "  stage: build", "  script:", f"    - {cmd.command}", ""])
        steps.append(_step(cmd, "Build"))

    if test_commands:
        cmd = test_commands[0]
        lines.extend(["test:", "  stage: test", "  script:", f"    - {cmd.command}", ""])
        steps.append(_step(cmd, "Test"))

    return "\n".join(lines), steps


def generate_jenkinsfile(
    build_commands: list[RepositoryCommand],
    test_commands: list[RepositoryCommand],
) -> tuple[str, list[PipelineStep]]:
    steps: list[PipelineStep] = []
    lines = ["// Evidence-derived steps only", "pipeline {", "    agent any", "", "    stages {"]

    if build_commands:
        cmd = build_commands[0]
        lines.extend([
            "        stage('Build') {", "            steps {",
            f"                sh '{cmd.command}'", "            }", "        }",
        ])
        steps.append(_step(cmd, "Build"))

    if test_commands:
        cmd = test_commands[0]
        lines.extend([
            "        stage('Test') {", "            steps {",
            f"                sh '{cmd.command}'", "            }", "        }",
        ])
        steps.append(_step(cmd, "Test"))

    lines.extend(["    }", "}"])
    return "\n".join(lines), steps


def generate_pipeline(
    repo_path: Path,
    commands: list[RepositoryCommand],
    evidence_items: list,
    ci_override: str | None,
    hf_detected: bool,
    has_production_deployment: bool,
) -> tuple[GeneratedPipeline | None, list[PipelineStep]]:
    build_commands = _pick_commands(commands, "build") + _pick_commands(commands, "install")
    test_commands = _pick_commands(commands, "test")
    docker_commands = [c for c in commands if c.category == "docker" and c.pipeline_eligible]

    env_vars = [
        str(e.value) for e in evidence_items
        if e.detection_method == ".env.example variable" and e.value
    ]

    if hf_detected:
        config = extract_spaces_config(repo_path)
        content = config if config else "Required but not provided — no verbatim Spaces config found in repository."
        steps = [PipelineStep(
            name="Hugging Face Spaces",
            command=None,
            source_file="space.yaml or README.md",
            detection_method="explicit Spaces metadata",
            reasoning="Explicit Hugging Face Spaces metadata detected — CI/CD managed by HF runtime",
            confidence=0.98,
            confidence_level=ConfidenceLevel.EXPLICIT,
        )]
        return GeneratedPipeline(
            pipeline_type="huggingface-spaces",
            content=content,
            steps=steps,
            override_reason="Explicit Hugging Face Spaces metadata — GitHub Actions deployment skipped",
        ), steps

    if not build_commands and not test_commands and not docker_commands:
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

    content, steps = generate_github_actions(build_commands, test_commands, docker_commands, env_vars)
    if not content.strip():
        return None, []

    if not has_production_deployment:
        content += "\n# No deployment stage — no deployment target detected from repository evidence."

    return GeneratedPipeline(pipeline_type="github-actions", content=content, steps=steps), steps
