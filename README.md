# Frontier AI Radar

**Daily Multi-Agent Intelligence System** — Crawls configurable sources, summarizes and ranks updates, detects SOTA claims, normalizes entities, compiles a polished PDF digest, and can email it to a configurable distribution list.

## Product overview

- **Competitor releases** — Product/blog/changelog updates
- **Foundation model providers** — Model launches, API/pricing, eval claims
- **Research publications** — arXiv, curated URLs (LLMs, multimodal, agents, eval)
- **Hugging Face benchmarks** — Leaderboards and SOTA trends
- **SOTA detection** — Automatic state-of-the-art claim identification with confidence scoring
- **Entity normalization** — Canonical mapping of 30+ AI companies for consistent analytics
- **Analytics** — SOTA Watch, Entity Heatmap (entity vs topic), Diff Viewer (day-over-day)
- **Daily PDF digest** — Executive summary + sections + SOTA Watch + citations
- **Email delivery** — Optional SMTP/Mailgun with PDF attachment
- **Scheduler** — Configurable scheduled jobs (daily, hourly, interval) with timezone support
- **Web UI** — Dashboard, pipeline management, run history, findings explorer, analytics, digest archive

## Repository structure

```
Hackathon/
├── backend/                 # Python FastAPI + agents
│   ├── app/
│   │   ├── agents/           # Competitor, ModelProvider, Research, HF, Digest
│   │   ├── api/routes/       # REST: runs, sources, findings, digests, config, analytics, scheduler, pipeline-configs, meta
│   │   ├── config/           # Settings (env + YAML)
│   │   ├── core/             # Exceptions
│   │   ├── db/               # SQLAlchemy models, async session, migrations
│   │   ├── orchestration/    # RunManager, APScheduler
│   │   ├── schemas/          # Pydantic request/response
│   │   ├── services/         # Fetcher, Extractor, ChangeDetector, Summarizer, Dedup, PDF, Email, AnalyticsService
│   │   ├── utils/            # SOTA detection, entity normalization, agent auto-detection
│   │   └── main.py
│   ├── config/
│   │   └── radar.yaml        # Default agent config (URLs, agents)
│   ├── requirements.txt
│   └── .env.example
├── frontend/                 # Next.js 14 (App Router)
│   ├── app/
│   │   ├── page.tsx          # Dashboard
│   │   ├── sources/          # Pipeline & source management (1 URL → 1 Agent)
│   │   ├── runs/             # Run history
│   │   ├── findings/         # Explorer + filters + diff view
│   │   ├── analytics/        # SOTA Watch, Entity Heatmap, Diff Viewer
│   │   ├── scheduler/        # Scheduled jobs management
│   │   └── digests/          # Archive + PDF download
│   ├── lib/
│   │   ├── api.ts            # API client (single source of truth for API_BASE)
│   │   └── useMeta.ts        # Dynamic agent/category metadata hook
│   └── package.json
├── docker-compose.yml
└── README.md
```

## How to run

### Prerequisites

- **Python 3.10+**
- **Node.js 18+** (for frontend)
- Optional: **OpenAI API key** (for LLM summarization; otherwise rule-based fallback)

### 1. Backend

```bash
cd backend
python -m venv .venv
# Windows:
.venv\Scripts\activate
# macOS/Linux:
# source .venv/bin/activate

pip install -r requirements.txt
cp .env.example .env
# Edit .env if you want OpenAI, SMTP, or different DB

# Run from backend directory so config and storage paths resolve
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

- API: **http://localhost:8000**
- Health: **http://localhost:8000/health**
- API docs: **http://localhost:8000/docs**

### 2. Frontend

```bash
cd frontend
npm install
npm run dev
```

- UI: **http://localhost:3000**

### 3. Docker (alternative)

```bash
docker-compose up --build
```

- Backend: **http://localhost:8000**
- Frontend: **http://localhost:3000**

### 4. Optional: Playwright (for JS-heavy pages)

```bash
cd backend
playwright install chromium
```

## Configuration

- **Backend config file**: `backend/config/radar.yaml`
  Defines `global` (run time, rate limits, email recipients) and `agents` (competitors, model_providers, research, hf_benchmarks) with URLs, RSS feeds, keywords.
- **Environment**: `backend/.env`
  Database URL, `OPENAI_API_KEY`, SMTP settings, `CORS_ORIGINS`, etc.

## Key features

- **Multi-Agent Source Configuration**: Each URL maps to exactly one agent (1 URL → 1 Agent). Sources are grouped under named pipelines.
- **Automatic Agent Detection**: When adding a source URL, the system auto-detects the appropriate agent based on domain and keyword rules.
- **SOTA Detection**: Findings are automatically scanned for state-of-the-art claims using 18 regex patterns with weighted confidence scoring.
- **Entity Normalization**: Entities (OpenAI, DeepMind, Meta, etc.) are normalized to canonical forms for consistent heatmap aggregation.
- **Impact Scoring**: Each finding receives an impact score: `0.35*Relevance + 0.25*Novelty + 0.20*Credibility + 0.20*Actionability`.
- **Scheduler**: Configurable scheduled jobs (daily, hourly, interval) with timezone support and status tracking.
- **Analytics**: SOTA Watch (backend-powered SOTA claim tracking), Entity Heatmap (entity vs 6 topics: models, research, benchmarks, pricing, safety, tooling), and Diff Viewer (day-over-day comparison).
- **IST Timezone Consistency**: All timestamps displayed in the UI are formatted in IST (Asia/Kolkata).

## Demo flow (what judges want)

1. Open **http://localhost:3000**
2. Go to **Pipeline** → **Add Pipeline** → enter name, add source URLs (agent auto-detected) → Save
3. **Dashboard** → **Run now** (select pipeline or run from YAML) → wait for run to finish
4. **Findings** → see findings with impact scores, SOTA badges; toggle **Compare Yesterday** for diff view
5. **Analytics** → SOTA Watch (benchmark claims), Entity Heatmap (who dominates what), Diff Viewer
6. **Digest archive** → **Download PDF** (includes SOTA Watch section)
7. **Scheduler** → create a scheduled job linked to a pipeline for automated daily runs
8. If email is configured, inbox receives the digest with PDF attached

## API summary

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/runs/` | List runs |
| POST | `/api/runs/` | Trigger run |
| GET | `/api/runs/{id}` | Get run |
| GET | `/api/sources/` | List sources (?agent_id=&pipeline_id=) |
| POST | `/api/sources/` | Create source (auto-detects agent if omitted) |
| GET | `/api/sources/detect-agent?url=` | Auto-detect agent for a URL |
| PATCH | `/api/sources/{id}` | Update source |
| DELETE | `/api/sources/{id}` | Delete source |
| GET | `/api/findings/` | List findings (?run_id=&agent_id=&category=&created_after=&limit=) |
| GET | `/api/findings/{id}` | Get finding detail |
| GET | `/api/analytics/sota-watch` | SOTA findings (is_sota=true, ordered by date) |
| GET | `/api/analytics/entity-heatmap` | Entity vs topic frequency matrix (?days=7) |
| GET | `/api/digests/` | List digests |
| GET | `/api/digests/{id}` | Get digest |
| GET | `/api/digests/{id}/download` | Download PDF |
| GET | `/api/pipeline-configs/` | List pipeline configs |
| POST | `/api/pipeline-configs/` | Create pipeline config |
| PATCH | `/api/pipeline-configs/{id}` | Update pipeline config |
| DELETE | `/api/pipeline-configs/{id}` | Delete pipeline config |
| GET | `/api/scheduler/` | List scheduled jobs |
| POST | `/api/scheduler/` | Create scheduled job |
| PATCH | `/api/scheduler/{id}` | Update scheduled job |
| DELETE | `/api/scheduler/{id}` | Delete scheduled job |
| GET | `/api/meta/` | Dynamic agent/category metadata |
| GET | `/api/config/` | Get radar YAML config |

## Non-functional notes

- **Reliability**: One agent can fail without blocking the digest (per-agent results stored).
- **Observability**: Logs and `agent_results` per run; trace per URL in logs.
- **Rate limiting**: Per-domain throttle; configurable in YAML and settings.
- **Secrets**: Use `.env` (or a vault) for API keys and SMTP; never commit secrets.
- **Cost**: Caching and content hashing avoid re-summarizing unchanged pages.

## Testing (high level)

- **Unit**: HTML extraction, date parsing, dedup hashing, SOTA detection, entity normalization, PDF build.
- **Integration**: End-to-end run against static test pages; simulate 404/timeouts.
- **Quality**: Assert numeric claims in summaries map to evidence snippets; same content → similar summary.

## Documentation

- **Backend**: See `backend/README.md` (if present) and docstrings in `app/agents/`, `app/services/`, `app/orchestration/`.
- **Spec**: This repo implements the hackathon spec: multi-agent pipeline, configurable sources, dedup, ranking, PDF, email, and minimal Web UI (dashboard, sources, runs, findings, digest archive).
