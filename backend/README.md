# Frontier AI Radar — Backend

FastAPI application plus multi-agent pipeline: fetcher, extractor, summarizer, dedup, PDF, email.

## Quick start

```bash
python -m venv .venv
.venv\Scripts\activate   # Windows
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Run from the `backend` directory so `config/radar.yaml` and `storage/` resolve.

## Layout

- **app/main.py** — FastAPI app, CORS, lifespan (init_db, scheduler).
- **app/config/settings.py** — Pydantic settings from env.
- **app/db/** — Async SQLite/Postgres, models: Source, Snapshot, Extraction, Finding, Run, Digest.
- **app/schemas/** — Pydantic request/response (FindingCreate, RunOut, SourceOut, etc.).
- **app/services/** — FetcherService, ExtractorService, ChangeDetector, SummarizerService, DedupService, PDFGenerator, EmailService.
- **app/agents/** — BaseAgent, CompetitorAgent, ModelProviderAgent, ResearchAgent, HFBenchmarksAgent, DigestAgent.
- **app/orchestration/run_manager.py** — Runs agents in parallel, persists findings, runs DigestAgent.
- **app/orchestration/scheduler.py** — APScheduler daily run.
- **app/api/routes/** — REST: runs, sources, findings, digests, config.

## Config

- **config/radar.yaml** — `global` (run_time, timezone, rate limits, email_recipients) and `agents` (competitors, model_providers, research, hf_benchmarks). Each agent reads its slice.
- **.env** — DATABASE_URL, OPENAI_API_KEY, SMTP_*, CORS_ORIGINS, etc.

## Data flow (daily run)

1. Scheduler or POST /api/runs/ triggers RunManager.start_run().
2. Run record created (status=running).
3. Agents 1–4 run in parallel (Competitor, ModelProvider, Research, HF).
4. Findings deduplicated, impact-scored, persisted with run_id.
5. DigestAgent: loads findings, clusters, generates PDF, optionally sends email.
6. Run status set to success/partial; digest record created.

## Dependencies

See `requirements.txt`. Key: FastAPI, SQLAlchemy 2, httpx, beautifulsoup4, trafilatura, feedparser, reportlab, openai, apscheduler, pyyaml. Optional: playwright for JS-rendered pages.
