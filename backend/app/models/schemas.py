from __future__ import annotations
from enum import Enum
from typing import Any
from pydantic import BaseModel, Field


class Confidence(str, Enum):
    EXPLICIT = "explicit"   # Found verbatim in a config/manifest file
    INFERRED = "inferred"   # Derived from file presence or patterns
    LOW = "low"             # Weak signal, heuristic only


class Evidence(BaseModel):
    source: str
    method: str
    detail: str
    score: float = Field(ge=0.0, le=1.0)
    confidence: Confidence
    value: str | None = None


class Dependency(BaseModel):
    name: str
    version: str | None = None
    source: str
    kind: str = "runtime"  # runtime | dev | peer


class Command(BaseModel):
    cmd: str
    source: str
    method: str
    score: float
    category: str  # build | test | install | docker | dev | other
    pipeline_eligible: bool
    working_dir: str | None = None


class PipelineStep(BaseModel):
    name: str
    cmd: str | None = None
    source: str
    method: str
    detail: str
    score: float
    confidence: Confidence


class ExistingWorkflow(BaseModel):
    """A CI workflow file already present in the repository."""
    path: str           # e.g. .github/workflows/ci.yml
    kind: str           # github-actions | gitlab-ci | jenkins
    content: str
    audit_notes: list[str] = Field(default_factory=list)


class Pipeline(BaseModel):
    kind: str           # github-actions | gitlab-ci | jenkins | huggingface-spaces
    content: str
    steps: list[PipelineStep] = Field(default_factory=list)
    override_note: str | None = None
    is_generated: bool = True   # False = we are showing the existing file


class Stack(BaseModel):
    languages: list[Evidence] = Field(default_factory=list)
    frameworks: list[Evidence] = Field(default_factory=list)
    runtimes: list[Evidence] = Field(default_factory=list)
    build_tools: list[Evidence] = Field(default_factory=list)
    test_frameworks: list[Evidence] = Field(default_factory=list)
    containers: list[Evidence] = Field(default_factory=list)
    deploy_targets: list[Evidence] = Field(default_factory=list)


class ConfidenceSummary(BaseModel):
    overall: float
    build: float
    test: float
    deploy: float


class Report(BaseModel):
    repo_url: str
    file_count: int
    file_tree: dict[str, Any]
    stack: Stack
    architecture: str
    dependencies: list[Dependency]
    evidence: list[Evidence]
    existing_workflows: list[ExistingWorkflow] = Field(default_factory=list)
    pipeline: Pipeline | None        # generated only when no existing CI found
    steps: list[PipelineStep]
    explicit_findings: list[Evidence]
    inferred_findings: list[Evidence]
    gaps: list[str]
    confidence: ConfidenceSummary
    instructions: list[str]
    is_huggingface: bool = False
    hf_note: str | None = None
    deploy_note: str | None = None
