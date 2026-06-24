from __future__ import annotations

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from app.analyzer.engine import RepositoryAnalyzer
from app.models.schemas import AnalysisReport

app = FastAPI(
    title="Repository CI/CD Auditor",
    description=(
        "Evidence-driven CI/CD pipeline generator and repository analyzer. "
        "Analyzes public GitHub repositories without authentication or external APIs."
    ),
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

analyzer = RepositoryAnalyzer()


class AnalyzeRequest(BaseModel):
    repository_url: str = Field(
        ...,
        description="Public GitHub repository URL",
        examples=["https://github.com/psf/requests"],
    )


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "service": "repo-cicd-auditor"}


@app.post("/api/analyze", response_model=AnalysisReport)
def analyze_repository(request: AnalyzeRequest) -> AnalysisReport:
    try:
        return analyzer.analyze(request.repository_url)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Analysis failed: {exc}") from exc
