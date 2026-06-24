from __future__ import annotations

from pathlib import Path

from app.analyzer.detectors.base import RepositoryCommand, evidence
from app.analyzer.detectors.build_tools import (
    analyze_makefile,
    analyze_maven_gradle,
    analyze_package_json,
    analyze_pyproject,
    analyze_requirements,
)
from app.analyzer.detectors.ci_existing import analyze_existing_ci, analyze_readme_commands, detect_tests
from app.analyzer.detectors.deployment import analyze_dockerfile, analyze_env_example, analyze_kubernetes
from app.analyzer.detectors.huggingface import detect_huggingface_space
from app.analyzer.scanner import RepositoryScanner
from app.generator.pipeline import generate_pipeline
from app.models.schemas import (
    AnalysisReport,
    ConfidenceLevel,
    DependencyGraphSummary,
    TechnologyStack,
)
from app.rules.evidence_rules import CONFIDENCE_EXPLICIT_MIN


class RepositoryAnalyzer:
    def __init__(self, scanner: RepositoryScanner | None = None) -> None:
        self.scanner = scanner or RepositoryScanner()

    def analyze(self, repo_url: str) -> AnalysisReport:
        repo_path = self.scanner.clone(repo_url)
        try:
            return self._analyze_path(repo_url, repo_path)
        finally:
            self.scanner.cleanup(repo_path)

    def _analyze_path(self, repo_url: str, repo_path: Path) -> AnalysisReport:
        all_evidence: list = []
        all_commands: list[RepositoryCommand] = []
        all_deps = []

        file_tree = self.scanner.build_file_tree(repo_path)
        file_count = sum(1 for _ in self.scanner.iter_files(repo_path))

        pkg_items, pkg_deps, pkg_cmds = analyze_package_json(repo_path)
        all_evidence.extend(pkg_items)
        all_deps.extend(pkg_deps)
        all_commands.extend(pkg_cmds)

        req_items, req_deps = analyze_requirements(repo_path)
        all_evidence.extend(req_items)
        all_deps.extend(req_deps)

        py_items, py_deps, py_cmds = analyze_pyproject(repo_path)
        all_evidence.extend(py_items)
        all_deps.extend(py_deps)
        all_commands.extend(py_cmds)

        mv_items, mv_deps, mv_cmds = analyze_maven_gradle(repo_path)
        all_evidence.extend(mv_items)
        all_deps.extend(mv_deps)
        all_commands.extend(mv_cmds)

        mk_items, mk_cmds = analyze_makefile(repo_path)
        all_evidence.extend(mk_items)
        all_commands.extend(mk_cmds)

        docker_items, docker_cmds, docker_deploy = analyze_dockerfile(repo_path)
        all_evidence.extend(docker_items)
        all_commands.extend(docker_cmds)

        k8s_items = analyze_kubernetes(repo_path)
        all_evidence.extend(k8s_items)

        env_items = analyze_env_example(repo_path)
        all_evidence.extend(env_items)

        ci_items, ci_override = analyze_existing_ci(repo_path)
        all_evidence.extend(ci_items)

        readme_items, _ = analyze_readme_commands(repo_path)
        all_evidence.extend(readme_items)

        hf_detected, hf_items, hf_message = detect_huggingface_space(repo_path)
        all_evidence.extend(hf_items)

        languages = self._detect_languages(repo_path)
        all_evidence.extend(languages)

        production_deployment = docker_deploy + k8s_items + (
            [e for e in hf_items if e.confidence >= CONFIDENCE_EXPLICIT_MIN and e.confidence_level == ConfidenceLevel.EXPLICIT]
            if hf_detected else []
        )
        has_production_deployment = bool(production_deployment)

        tech_stack = self._build_tech_stack(all_evidence, docker_deploy, k8s_items, hf_items if hf_detected else [])
        test_items = detect_tests(all_evidence)

        dep_graph = DependencyGraphSummary(
            nodes=all_deps,
            edges=[{"from": n.source_file, "to": n.name} for n in all_deps],
        )

        deployment_message = None
        if not has_production_deployment:
            deployment_message = "No deployment target detected from repository evidence."

        pipeline, steps = generate_pipeline(
            repo_path=repo_path,
            commands=all_commands,
            evidence_items=all_evidence,
            ci_override=ci_override,
            hf_detected=hf_detected,
            has_production_deployment=has_production_deployment,
        )

        explicit = [e for e in all_evidence if e.confidence_level == ConfidenceLevel.EXPLICIT]
        inferred = [e for e in all_evidence if e.confidence_level == ConfidenceLevel.INFERRED]
        low = [e for e in all_evidence if e.confidence_level == ConfidenceLevel.LOW]

        missing = self._identify_missing(all_evidence, all_commands, test_items, has_production_deployment)

        confidence = self._compute_confidence(all_evidence, steps, has_production_deployment)

        execution_instructions = self._execution_instructions(
            repo_url, pipeline, hf_detected, hf_message, deployment_message
        )

        architecture = self._architecture_summary(tech_stack, file_count, dep_graph)

        return AnalysisReport(
            repository_url=repo_url,
            repository_analysis={
                "file_count": file_count,
                "file_tree": file_tree,
                "root_path": str(repo_path.name),
            },
            technology_stack=tech_stack,
            architecture_summary=architecture,
            dependency_graph=dep_graph,
            evidence_table=all_evidence,
            generated_pipeline=pipeline,
            step_justifications=steps,
            explicit_findings=explicit,
            inferred_findings=inferred + low,
            missing_information=missing,
            confidence_assessment=confidence,
            execution_instructions=execution_instructions,
            huggingface_space_detected=hf_detected,
            huggingface_message=hf_message,
            deployment_message=deployment_message,
        )

    def _detect_languages(self, repo_path: Path) -> list:
        items = []
        ext_map = {
            ".py": "Python", ".js": "JavaScript", ".ts": "TypeScript",
            ".tsx": "TypeScript/React", ".jsx": "JavaScript/React",
            ".java": "Java", ".go": "Go", ".rs": "Rust", ".rb": "Ruby",
            ".cs": "C#", ".cpp": "C++", ".c": "C", ".swift": "Swift",
            ".kt": "Kotlin", ".scala": "Scala", ".php": "PHP",
        }
        found: dict[str, int] = {}
        for path in self.scanner.iter_files(repo_path):
            ext = path.suffix.lower()
            if ext in ext_map:
                lang = ext_map[ext]
                found[lang] = found.get(lang, 0) + 1

        for lang, count in sorted(found.items(), key=lambda x: -x[1]):
            items.append(evidence(
                "repository scan", "file extension analysis",
                f"Language '{lang}' inferred from {count} file extension(s) — not confirmed by imports",
                min(0.75, 0.55 + count * 0.002), lang,
                level=ConfidenceLevel.INFERRED,
            ))
        return items

    def _build_tech_stack(self, evidence_items, docker, k8s, hf) -> TechnologyStack:
        def explicit_only(keywords: set[str]) -> list:
            return [
                e for e in evidence_items
                if e.confidence_level == ConfidenceLevel.EXPLICIT
                and any(kw in str(e.value).lower() or kw in e.reasoning.lower() for kw in keywords)
            ]

        return TechnologyStack(
            languages=[e for e in evidence_items if e.detection_method == "file extension analysis"],
            frameworks=explicit_only({"dependency", "framework"}),
            runtimes=explicit_only({"engines", "runtime"}),
            build_tools=explicit_only({"makefile", "package.json scripts", "pyproject.toml", "pom.xml", "gradle"}),
            test_frameworks=[e for e in evidence_items if "test" in e.detection_method.lower() or "pytest" in str(e.value).lower()],
            containerization=docker,
            deployment_targets=k8s + hf,
        )

    def _identify_missing(
        self,
        evidence: list,
        commands: list[RepositoryCommand],
        tests: list,
        has_deploy: bool,
    ) -> list[str]:
        missing = []
        pipeline_eligible = [c for c in commands if c.pipeline_eligible]
        if not pipeline_eligible:
            missing.append("No pipeline-eligible build/test commands at explicit confidence (>=0.95).")
        if not tests:
            missing.append("No test framework detected from dependencies or configuration.")
        if not has_deploy:
            missing.append("No production deployment target (Dockerfile, K8s, Hugging Face Spaces) detected.")
        if not any("engines" in e.detection_method for e in evidence):
            missing.append("Runtime version constraints not found in package.json engines or similar.")
        return missing

    def _compute_confidence(self, evidence: list, steps: list, has_deploy: bool) -> dict[str, float]:
        explicit_evidence = [e.confidence for e in evidence if e.confidence_level == ConfidenceLevel.EXPLICIT]
        step_conf = [s.confidence for s in steps] if steps else []

        return {
            "overall": round(sum(explicit_evidence) / max(len(explicit_evidence), 1), 2) if explicit_evidence else 0.0,
            "build": round(max(step_conf), 2) if step_conf else 0.0,
            "test": round(
                max((s.confidence for s in steps if s.name == "Test"), default=0.0), 2
            ),
            "deploy": 0.98 if has_deploy else 0.0,
        }

    def _architecture_summary(self, stack: TechnologyStack, file_count: int, deps: DependencyGraphSummary) -> str:
        langs = {str(e.value) for e in stack.languages[:3]}
        parts = [f"Repository contains {file_count} scannable files."]
        if langs:
            parts.append(f"Languages inferred from extensions: {', '.join(langs)}.")
        parts.append(f"Dependency graph contains {len(deps.nodes)} explicit dependencies.")
        if stack.containerization:
            parts.append("Production containerization evidence present.")
        if stack.deployment_targets:
            parts.append("Production deployment configuration evidence present.")
        return " ".join(parts)

    def _execution_instructions(self, url, pipeline, hf, hf_msg, deploy_msg) -> list[str]:
        instructions = [
            f"1. Clone the repository: git clone {url}",
            "2. Review evidence table and step justifications.",
        ]
        if hf and hf_msg:
            instructions.append(f"3. {hf_msg}")
        elif pipeline and pipeline.content:
            instructions.append(f"3. Review evidence-derived {pipeline.pipeline_type} steps.")
        if deploy_msg:
            instructions.append(f"Note: {deploy_msg}")
        return instructions
