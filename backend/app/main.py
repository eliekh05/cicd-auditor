from __future__ import annotations

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from app.engine import Engine
from app.models.schemas import Report

app = FastAPI(
    title="CI/CD Auditor",
    description="Evidence-driven CI/CD pipeline generator. Analyzes public GitHub repos — no auth, no assumptions.",
    version="2.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

_engine = Engine()


class AnalyzeRequest(BaseModel):
    url: str = Field(..., description="Public GitHub repository URL", examples=["https://github.com/psf/requests"])


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "version": "2.0.0"}


@app.post("/api/analyze", response_model=Report)
def analyze(req: AnalyzeRequest) -> Report:
    try:
        return _engine.analyze(req.url.strip())
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(422, str(exc)) from exc
    except Exception as exc:
        raise HTTPException(500, f"Analysis failed: {exc}") from exc
