# Frontier AI Radar

**Daily Multi-Agent Intelligence System** — Crawls configurable sources, summarizes and ranks updates, compiles a polished PDF digest, and can email it to you and a configurable distribution list.

## Product overview

- **Competitor releases** — Product/blog/changelog updates
- **Foundation model providers** — Model launches, API/pricing, eval claims
- **Research publications** — arXiv, curated URLs (LLMs, multimodal, agents, eval)
- **Hugging Face benchmarks** — Leaderboards and SOTA trends
- **Daily PDF digest** — Executive summary + sections + citations
- **Email delivery** — Optional SMTP with PDF attachment
- **Web UI** — Dashboard, sources, run history, findings explorer, digest archive

## Repository structure

```
Hackathon/
├── backend/                 # Python FastAPI + agents
│   ├── app/
│   │   ├── agents/           # Competitor, ModelProvider, Research, HF, Digest
│   │   ├── api/routes/       # REST: runs, sources, findings, digests, config
│   │   ├── config/           # Settings (env + YAML)
│   │   ├── core/             # Exceptions
│   │   ├── db/               # SQLAlchemy models, async session
│   │   ├── orchestration/    # RunManager, scheduler
│   │   ├── schemas/          # Pydantic request/response
│   │   ├── services/         # Fetcher, Extractor, ChangeDetector, Summarizer, Dedup, PDF, Email
│   │   └── main.py
│   ├── config/
│   │   └── radar.yaml        # Default agent config (URLs, agents)
│   ├── requirements.txt
│   └── .env.example
├── frontend/                 # Next.js 14 (App Router)
│   ├── app/
│   │   ├── page.tsx          # Dashboard
│   │   ├── sources/          # Manage URLs
│   │   ├── runs/             # Run history
│   │   ├── findings/         # Explorer + filters
│   │   └── digests/          # Archive + PDF download
│   ├── lib/api.ts            # API client
│   └── package.json
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

### 3. Optional: Playwright (for JS-heavy pages)

If you use headless browser fallback for crawling:

```bash
cd backend
playwright install chromium
```

## Configuration

- **Backend config file**: `backend/config/radar.yaml`  
  Defines `global` (run time, rate limits, email recipients) and `agents` (competitors, model_providers, research, hf_benchmarks) with URLs, RSS feeds, keywords.
- **Environment**: `backend/.env`  
  Database URL, `OPENAI_API_KEY`, SMTP settings, `CORS_ORIGINS`, etc.

## Demo flow (what judges want)

1. Open **http://localhost:3000**
2. Go to **Sources** → **Add source** (e.g. URL + agent “Competitors”) → Save
3. **Dashboard** → **Run now** → wait for run to finish (status in **Runs**)
4. **Findings** → see new findings; **Digest archive** → **Download PDF**
5. If email is configured, inbox receives the digest with PDF attached

## API summary

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/runs/` | List runs |
| POST | `/api/runs/` | Trigger run `{ "trigger": "manual" }` |
| GET | `/api/runs/{id}` | Get run |
| GET | `/api/sources/` | List sources (?agent_id=) |
| POST | `/api/sources/` | Create source |
| PATCH | `/api/sources/{id}` | Update source |
| DELETE | `/api/sources/{id}` | Delete source |
| GET | `/api/findings/?run_id=&agent_id=&category=` | List findings |
| GET | `/api/findings/{id}` | Get finding |
| GET | `/api/digests/` | List digests |
| GET | `/api/digests/{id}` | Get digest |
| GET | `/api/digests/{id}/download` | Download PDF |
| GET | `/api/config/` | Get radar YAML config |

## Non-functional notes

- **Reliability**: One agent can fail without blocking the digest (per-agent results stored).
- **Observability**: Logs and `agent_results` per run; trace per URL in logs.
- **Rate limiting**: Per-domain throttle; configurable in YAML and settings.
- **Secrets**: Use `.env` (or a vault) for API keys and SMTP; never commit secrets.
- **Cost**: Caching and content hashing avoid re-summarizing unchanged pages when you add snapshot/diff logic.

## Testing (high level)

- **Unit**: HTML extraction, date parsing, dedup hashing, PDF build (with mocked findings).
- **Integration**: End-to-end run against static test pages; simulate 404/timeouts.
- **Quality**: Assert numeric claims in summaries map to evidence snippets; same content → similar summary.

## Documentation

- **Backend**: See `backend/README.md` (if present) and docstrings in `app/agents/`, `app/services/`, `app/orchestration/`.
- **Spec**: This repo implements the hackathon spec: multi-agent pipeline, configurable sources, dedup, ranking, PDF, email, and minimal Web UI (dashboard, sources, runs, findings, digest archive).
