# Frontier AI Radar — Backend

FastAPI application plus multi-agent pipeline: fetcher, extractor, summarizer, SOTA detection, entity normalization, dedup, analytics, PDF, email.

## Quick start

```bash
python -m venv .venv
.venv\Scripts\activate   # Windows
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Run from the `backend` directory so `config/radar.yaml` and `data/` resolve.

## Layout

- **app/main.py** — FastAPI app, CORS, lifespan (init_db + schema migrations, scheduler).
- **app/config/settings.py** — Pydantic settings from env.
- **app/db/** — Async SQLite/Postgres, models: Source, PipelineConfig, ScheduledJob, Snapshot, Extraction, Finding, Run, Digest, RunLog, EmailRecipient.
- **app/db/database.py** — Engine, session, auto-migration (ALTER TABLE for new columns), UTCDateTime TypeDecorator.
- **app/schemas/** — Pydantic request/response (FindingCreate, RunOut, SourceOut, PipelineConfigOut, etc.).
- **app/services/** — FetcherService, ExtractorService, ChangeDetector, SummarizerService, DedupService, PDFGenerator, EmailService, AnalyticsService.
- **app/utils/** — sota_detection.py (SOTA claim detection), entity_normalizer.py (canonical name mapping), agent_detector.py (auto-detect agent from URL).
- **app/agents/** — BaseAgent, CompetitorAgent, ModelProviderAgent, ResearchAgent, HFBenchmarksAgent, DigestAgent.
- **app/orchestration/run_manager.py** — Runs agents in parallel, SOTA detection + entity normalization on findings, persists results, runs DigestAgent.
- **app/orchestration/scheduler.py** — APScheduler for scheduled pipeline runs with timezone support.
- **app/api/routes/** — REST: runs, sources, findings, digests, config, analytics, scheduler, pipeline-configs, meta.

## Config

- **config/radar.yaml** — `global` (run_time, timezone, rate limits, email_recipients) and `agents` (competitors, model_providers, research, hf_benchmarks). Each agent reads its slice.
- **.env** — DATABASE_URL, OPENAI_API_KEY, SMTP_*, MAILGUN_*, CORS_ORIGINS, etc.

## Data flow (daily run)

1. Scheduler or POST /api/runs/ triggers RunManager.start_run().
2. Run record created (status=running).
3. Sources merged from pipeline config into agent config.
4. Agents 1–4 run in parallel (Competitor, ModelProvider, Research, HF).
5. Findings deduplicated, impact-scored, SOTA-detected, entities normalized, persisted with run_id.
6. DigestAgent: loads findings, clusters, generates PDF (includes SOTA Watch section), optionally sends email.
7. Run status set to success/partial; digest record created.

## Key modules

### SOTA Detection (`app/utils/sota_detection.py`)
- `detect_sota_claim(text)` → `{"is_sota": bool, "confidence": float}`
- 18 regex patterns with weighted scoring (0.70–1.00)
- Persisted as `Finding.is_sota` and `Finding.sota_confidence`

### Entity Normalization (`app/utils/entity_normalizer.py`)
- `normalize_entity(name)` → canonical string
- 30+ mappings (OpenAI, Anthropic, DeepMind, etc.)
- Applied before storing `Finding.entities`

### Analytics Service (`app/services/analytics_service.py`)
- `get_sota_findings(db, limit)` → SOTA findings list
- `get_entity_heatmap(db, days)` → `{entities, topics, matrix}`
- Topics: models, research, benchmarks, pricing, safety, tooling

## Dependencies

See `requirements.txt`. Key: FastAPI, SQLAlchemy 2, httpx, beautifulsoup4, trafilatura, feedparser, reportlab, openai, apscheduler, pyyaml. Optional: playwright for JS-rendered pages.
