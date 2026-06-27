# CI/CD Auditor v2

Evidence-driven CI/CD pipeline generator. Clones any public GitHub repository,
scans every file, and produces a justified pipeline — no AI, no guesses, only
what the repository actually contains.

## Architecture

```
browser → Cloudflare Pages (frontend)
              ↓  /api/*
        Cloudflare Worker  ← rate-limit + KV cache + security headers
              ↓
        FastAPI backend  (Railway / Render / Fly / VPS)
              ↓
        GitHub (git clone)
```

## Local development

```bash
bash start.sh
# Backend  → http://localhost:8000
# Frontend → http://localhost:5173
```

## Deploy to Cloudflare

### 1. Backend (FastAPI)

Deploy to any Python-capable host (Railway, Render, Fly.io, or a VPS):

```bash
cd backend
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Note your backend URL, e.g. `https://cicd-auditor-api.railway.app`.

### 2. Cloudflare Worker

```bash
cd worker
npm install
wrangler kv:namespace create CACHE        # note the ID
wrangler kv:namespace create RATE_LIMIT   # note the ID
```

Edit `wrangler.toml` and fill in the two KV namespace IDs, then:

```bash
wrangler secret put BACKEND_URL
# enter: https://your-backend-host.example.com

wrangler deploy
```

Your Worker URL will be `https://cicd-auditor.<account>.workers.dev`.

### 3. Cloudflare Pages (frontend)

```bash
cd frontend
# In Pages dashboard:
#   Build command:   npm run build
#   Build output:   dist
#   Root directory: frontend
#
# Add environment variable:
#   VITE_API_BASE = https://cicd-auditor.<account>.workers.dev
```

Or via CLI:
```bash
npm run build
wrangler pages deploy dist --project-name cicd-auditor
```

### Custom domain

1. Add your domain to Cloudflare.
2. In Pages → Custom domains → add `yourdomain.com`.
3. In the Worker, add a route: `api.yourdomain.com/*`.
4. Update `VITE_API_BASE` to `https://api.yourdomain.com`.

## Stack

| Layer | Technology |
|---|---|
| Frontend | React 18 + Vite |
| Backend | FastAPI + Pydantic v2 |
| Worker | Cloudflare Workers (JS) |
| Cache | Cloudflare KV |
| Rate limiting | Cloudflare KV (sliding window) |
| Hosting | Cloudflare Pages + Workers |

## What the auditor detects

- **Node.js** — `package.json` scripts, dependencies, engines
- **Python** — `requirements.txt`, `pyproject.toml`, Poetry
- **JVM** — `pom.xml` (Maven), `build.gradle` (Gradle)
- **Make** — `Makefile` targets
- **Docker** — `Dockerfile`, `docker-compose.yml`
- **Kubernetes** — manifest YAMLs, `Chart.yaml` (Helm)
- **Hugging Face Spaces** — README front matter, `space.yaml`
- **Existing CI** — `.gitlab-ci.yml`, `Jenkinsfile`, GitHub Actions workflows
- **Languages** — inferred from file extensions
