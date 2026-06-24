from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class ConfidenceLevel(str, Enum):
    EXPLICIT = "explicit"
    INFERRED = "inferred"
    LOW = "low"


class EvidenceItem(BaseModel):
    source_file: str
    detection_method: str
    reasoning: str
    confidence: float = Field(ge=0.0, le=1.0)
    confidence_level: ConfidenceLevel
    value: Any = None


class TechnologyStack(BaseModel):
    languages: list[EvidenceItem] = Field(default_factory=list)
    frameworks: list[EvidenceItem] = Field(default_factory=list)
    runtimes: list[EvidenceItem] = Field(default_factory=list)
    build_tools: list[EvidenceItem] = Field(default_factory=list)
    test_frameworks: list[EvidenceItem] = Field(default_factory=list)
    containerization: list[EvidenceItem] = Field(default_factory=list)
    deployment_targets: list[EvidenceItem] = Field(default_factory=list)


class DependencyNode(BaseModel):
    name: str
    version: str | None = None
    source_file: str
    confidence_level: ConfidenceLevel
    dependency_type: str = "explicit"


class DependencyGraphSummary(BaseModel):
    nodes: list[DependencyNode] = Field(default_factory=list)
    edges: list[dict[str, str]] = Field(default_factory=list)


class PipelineStep(BaseModel):
    name: str
    command: str | None = None
    source_file: str
    detection_method: str
    reasoning: str
    confidence: float
    confidence_level: ConfidenceLevel


class GeneratedPipeline(BaseModel):
    pipeline_type: str
    content: str
    steps: list[PipelineStep] = Field(default_factory=list)
    override_reason: str | None = None


class AnalysisReport(BaseModel):
    repository_url: str
    repository_analysis: dict[str, Any]
    technology_stack: TechnologyStack
    architecture_summary: str
    dependency_graph: DependencyGraphSummary
    evidence_table: list[EvidenceItem]
    generated_pipeline: GeneratedPipeline | None
    step_justifications: list[PipelineStep]
    explicit_findings: list[EvidenceItem]
    inferred_findings: list[EvidenceItem]
    missing_information: list[str]
    confidence_assessment: dict[str, float]
    execution_instructions: list[str]
    huggingface_space_detected: bool = False
    huggingface_message: str | None = None
    deployment_message: str | None = None
