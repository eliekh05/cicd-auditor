# Repository CI/CD Auditor

An evidence-driven system that analyzes public GitHub repositories and generates production-grade CI/CD pipelines based strictly on repository evidence.

## Principles

- **Accuracy over completeness** — never invent infrastructure or commands
- **Evidence over assumptions** — every output is traceable to a source file
- **No external APIs** — no OpenAI, Anthropic, or paid services required
- **No authentication** — works with public GitHub URLs only

## Architecture

```
repo-cicd-auditor/
├── backend/          # FastAPI Python API
│   └── app/
│       ├── analyzer/ # Repository scanning & detection
│       ├── generator/# CI/CD pipeline generation
│       └── models/   # Pydantic schemas
└── frontend/         # React + Vite UI
```

## Quick Start

### Backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

Open http://localhost:5173 and enter a public GitHub repository URL.

## API

```
POST /api/analyze
Content-Type: application/json

{ "repository_url": "https://github.com/owner/repo" }
```

Returns a full analysis report with all 11 required output sections.

## Detection Capabilities

- **Build tools**: package.json, pyproject.toml, requirements.txt, Makefile, Maven, Gradle
- **Containerization**: Dockerfile, docker-compose
- **Deployment**: Kubernetes manifests, Helm charts, Hugging Face Spaces
- **CI overrides**: GitLab CI, Jenkinsfile, Hugging Face Spaces
- **Test frameworks**: Detected from dependencies only (jest, pytest, vitest, etc.)

## Hugging Face Spaces

When Spaces metadata is detected (README front matter, app.py + Gradio, .huggingface/, space.yaml), the system:

1. Outputs: "This repository is a Hugging Face Space. CI/CD is managed by Hugging Face Spaces runtime."
2. Generates Spaces-compatible configuration
3. Does NOT generate GitHub Actions deployment

## License

MIT
