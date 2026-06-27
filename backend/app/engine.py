from __future__ import annotations

from pathlib import Path

from app.analyzer.detectors.ci_hf import (
    detect_existing_ci,
    detect_huggingface,
    detect_readme_commands,
    detect_test_frameworks,
)
from app.analyzer.detectors.deployment import detect_docker, detect_env, detect_kubernetes
from app.analyzer.detectors.jvm_make import detect as detect_jvm
from app.analyzer.detectors.node import detect as detect_node
from app.analyzer.detectors.python import detect as detect_python
from app.generator import generate
from app.models.schemas import (
    Confidence,
    ConfidenceSummary,
    Dependency,
    Evidence,
    ExistingWorkflow,
    Report,
    Stack,
)
from app.scanner import Scanner

_EXT_LANGS: dict[str, str] = {
    ".py": "Python", ".js": "JavaScript", ".ts": "TypeScript",
    ".tsx": "TypeScript (React)", ".jsx": "JavaScript (React)",
    ".java": "Java", ".go": "Go", ".rs": "Rust", ".rb": "Ruby",
    ".cs": "C#", ".cpp": "C++", ".c": "C", ".swift": "Swift",
    ".kt": "Kotlin", ".scala": "Scala", ".php": "PHP",
}


class Engine:
    def __init__(self) -> None:
        self.scanner = Scanner()

    def analyze(self, url: str) -> Report:
        path = self.scanner.clone(url)
        try:
            return self._run(url, path)
        finally:
            self.scanner.cleanup(path)

    # ------------------------------------------------------------------

    def _run(self, url: str, repo: Path) -> Report:
        all_ev: list[Evidence] = []
        all_deps: list[Dependency] = []
        all_cmds = []

        # ── Detectors ──────────────────────────────────────────────────
        for ev, deps, cmds in (
            detect_node(repo),
            detect_python(repo),
            detect_jvm(repo),
        ):
            all_ev.extend(ev)
            all_deps.extend(deps)
            all_cmds.extend(cmds)

        docker_ev, docker_cmds, docker_deploy = detect_docker(repo)
        all_ev.extend(docker_ev)
        all_cmds.extend(docker_cmds)

        k8s_ev = detect_kubernetes(repo)
        all_ev.extend(k8s_ev)

        env_ev = detect_env(repo)
        all_ev.extend(env_ev)

        # Existing CI — read files + audit them
        ci_ev, existing_workflows = detect_existing_ci(repo)
        all_ev.extend(ci_ev)

        all_ev.extend(detect_readme_commands(repo))

        hf_detected, hf_ev, hf_note = detect_huggingface(repo)
        all_ev.extend(hf_ev)

        lang_ev = self._detect_languages(repo)
        all_ev.extend(lang_ev)

        # ── Derived data ───────────────────────────────────────────────
        test_frameworks = detect_test_frameworks(all_ev)
        has_deploy = bool(docker_deploy or k8s_ev)

        # ── Pipeline decision ──────────────────────────────────────────
        # If the repo already has CI workflows, don't generate — audit instead.
        if existing_workflows:
            pipeline = None
            steps = []
        else:
            pipeline, steps = generate(
                all_cmds, all_ev,
                is_huggingface=hf_detected,
                has_deploy=has_deploy,
            )

        # ── Report ─────────────────────────────────────────────────────
        file_count = sum(1 for _ in self.scanner.iter_files(repo))
        explicit = [e for e in all_ev if e.confidence == Confidence.EXPLICIT]
        inferred = [e for e in all_ev if e.confidence != Confidence.EXPLICIT]

        return Report(
            repo_url=url,
            file_count=file_count,
            file_tree=self.scanner.file_tree(repo),
            stack=self._build_stack(all_ev, lang_ev, docker_deploy, k8s_ev, hf_ev, test_frameworks),
            architecture=self._architecture(all_ev, file_count, all_deps, has_deploy),
            dependencies=all_deps,
            evidence=all_ev,
            existing_workflows=existing_workflows,
            pipeline=pipeline,
            steps=steps,
            explicit_findings=explicit,
            inferred_findings=inferred,
            gaps=self._gaps(all_cmds, test_frameworks, has_deploy, all_ev, existing_workflows),
            confidence=self._confidence(all_ev, steps, has_deploy),
            instructions=self._instructions(url, pipeline, existing_workflows, hf_detected, hf_note, has_deploy),
            is_huggingface=hf_detected,
            hf_note=hf_note,
            deploy_note=None if has_deploy else "No deployment target detected.",
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _detect_languages(self, repo: Path) -> list[Evidence]:
        from app.analyzer.helpers import make_evidence
        counts: dict[str, int] = {}
        for p in self.scanner.iter_files(repo):
            lang = _EXT_LANGS.get(p.suffix.lower())
            if lang:
                counts[lang] = counts.get(lang, 0) + 1
        result = []
        for lang, n in sorted(counts.items(), key=lambda x: -x[1]):
            result.append(make_evidence(
                "repository scan", "file extension analysis",
                f"'{lang}' inferred from {n} file(s)",
                min(0.75, 0.55 + n * 0.002), lang,
                confidence=Confidence.INFERRED,
            ))
        return result

    def _build_stack(
        self,
        all_ev: list[Evidence],
        lang_ev: list[Evidence],
        docker: list[Evidence],
        k8s: list[Evidence],
        hf: list[Evidence],
        tests: list[Evidence],
    ) -> Stack:
        def by_method(*methods: str) -> list[Evidence]:
            return [e for e in all_ev if e.method in methods and e.confidence != Confidence.LOW]

        def keyword_match(*keywords: str) -> list[Evidence]:
            kws = set(keywords)
            results = []
            for e in all_ev:
                if e.confidence == Confidence.LOW:
                    continue
                text = f"{e.value or ''} {e.detail} {e.method}".lower()
                if any(k in text for k in kws):
                    results.append(e)
            return results

        return Stack(
            languages=lang_ev,
            frameworks=keyword_match("dependency", "framework", "package.json dependencies"),
            runtimes=keyword_match("engines", "runtime", "package.json engines"),
            build_tools=by_method(
                "Makefile target", "package.json scripts",
                "pyproject.toml", "pom.xml", "Gradle",
            ),
            test_frameworks=tests,
            containers=docker,
            deploy_targets=k8s + [e for e in hf if e.confidence == Confidence.EXPLICIT],
        )

    def _gaps(self, cmds, tests, has_deploy, evidence, existing_workflows) -> list[str]:
        gaps = []

        # If existing CI present, audit its gaps instead
        if existing_workflows:
            for wf in existing_workflows:
                for note in wf.audit_notes:
                    gaps.append(f"[{wf.path}] {note}")
            return gaps

        eligible = [c for c in cmds if c.pipeline_eligible and c.category not in ("dev", "other")]
        if not eligible:
            gaps.append("No pipeline-eligible build or test commands found at explicit confidence (≥0.95).")
        if not tests:
            gaps.append("No test framework detected in dependencies or configuration.")
        if not has_deploy:
            gaps.append("No production deployment target found (Dockerfile, Kubernetes, Hugging Face Spaces).")
        if not any(e.method == "package.json engines" for e in evidence):
            gaps.append("No runtime version constraints (e.g. package.json engines field).")
        return gaps

    def _confidence(self, evidence, steps, has_deploy) -> ConfidenceSummary:
        explicit_scores = [e.score for e in evidence if e.confidence == Confidence.EXPLICIT]
        step_scores = [s.score for s in steps]
        test_scores = [s.score for s in steps if "test" in s.name.lower()]
        return ConfidenceSummary(
            overall=round(sum(explicit_scores) / max(len(explicit_scores), 1), 2),
            build=round(max(step_scores, default=0.0), 2),
            test=round(max(test_scores, default=0.0), 2),
            deploy=0.98 if has_deploy else 0.0,
        )

    def _architecture(self, evidence, file_count, deps, has_deploy) -> str:
        langs = sorted(
            {e.value for e in evidence if e.method == "file extension analysis" and e.value},
            key=lambda l: -next((e.score for e in evidence if e.value == l), 0),
        )[:4]
        parts = [f"Repository: {file_count} scannable files."]
        if langs:
            parts.append(f"Languages detected: {', '.join(langs)}.")
        parts.append(f"Dependencies: {len(deps)} explicit entries.")
        if has_deploy:
            parts.append("Production deployment configuration present.")
        return " ".join(parts)

    def _instructions(self, url, pipeline, existing_workflows, hf, hf_note, has_deploy) -> list[str]:
        out = [f"git clone {url}"]

        if hf and hf_note:
            out.append(hf_note)
            return out

        if existing_workflows:
            kinds = sorted({w.kind for w in existing_workflows})
            out.append(
                f"This repo already has CI ({', '.join(kinds)}). "
                "Review the audit notes in the gaps section for suggested improvements."
            )
            total_notes = sum(len(w.audit_notes) for w in existing_workflows)
            if total_notes == 0:
                out.append("No issues found in existing CI configuration.")
            else:
                out.append(f"{total_notes} improvement suggestion(s) found — see Gaps section.")
            return out

        if pipeline:
            out.append(f"No CI found. A {pipeline.kind} pipeline has been generated from the repository's build configuration.")
            out.append("Copy the pipeline YAML into your repository's CI config file.")
        else:
            out.append("No CI found and insufficient evidence to generate one. Add a build script or Dockerfile and re-analyze.")

        if not has_deploy:
            out.append("No deployment target detected — deploy step omitted from generated pipeline.")
        return out
