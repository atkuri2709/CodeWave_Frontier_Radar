# Frontier AI Radar — Detailed Documentation

## 1. System overview

The system is a **daily batch pipeline** that:

1. **Crawls** configurable sources (URLs, RSS) per agent
2. **Extracts** main text and metadata (HTML, RSS; optional PDF)
3. **Detects change** via content hashing to avoid re-processing unchanged pages
4. **Summarizes** with an LLM (or rule-based fallback) into structured findings
5. **Deduplicates** and **clusters** findings by topic/entity
6. **Ranks** by impact (relevance, novelty, credibility, actionability)
7. **Compiles** a PDF digest (exec summary + sections + citations)
8. **Delivers** by email (optional) and stores PDF for the Web UI

**Non-goals (hackathon scope):** training models, full web-scale crawling, real-time monitoring.

---

## 2. Architecture

### Components

| Component | Role |
|-----------|------|
| **Orchestrator** | RunManager + APScheduler: trigger runs, run agents, persist results |
| **Agent workers** | 4 crawlers (Competitor, ModelProvider, Research, HF) + 1 Digest agent |
| **Fetcher** | HTTP + optional Playwright; rate limiting per domain |
| **Extractor** | HTML→text (trafilatura + BeautifulSoup), RSS/Atom parsing |
| **Change detector** | Content hash; skip re-summarization when unchanged |
| **Summarizer** | LLM (OpenAI) or rule-based; structured output + citations |
| **Dedup** | Same URL/title or diff_hash; cluster by category |
| **Knowledge store** | SQLite (or Postgres): sources, snapshots, extractions, findings, runs, digests |
| **PDF generator** | ReportLab: cover, exec summary, sections by category |
| **Email** | SMTP: inline summary + PDF attachment |
| **Web UI** | Next.js: dashboard, sources CRUD, runs, findings, digest archive |

### Data flow (one run)

```
Scheduler or POST /api/runs/
    → RunManager.start_run()
    → Create Run (status=running)
    → asyncio.gather(Competitor, ModelProvider, Research, HF)
    → DedupService.deduplicate(findings)
    → Persist Finding rows (run_id, impact_score)
    → DigestAgent.run(): load findings, cluster, PDF, email
    → Run.status = success/partial, Run.finished_at set
```

---

## 3. Agent specifications

### Shared interface

- **Input**: `AgentContext(run_id, agent_config, since_timestamp)`
- **Output**: `AgentResult(agent_id, findings[], status, error_message, pages_processed)`

**Finding schema**: title, date_detected, source_url, publisher, category (release|research|benchmark), summary_short (≤60 words), summary_long, why_it_matters, evidence, confidence (0–1), tags[], entities[], diff_hash, agent_id.

### Agent 1 — Competitor Release Watcher

- **Config**: `agents.competitors[]`: name, release_urls[], rss_feeds[], selectors, keywords[], domain_rate_limit.
- **Logic**: Prefer RSS → parse entries → summarize each; else fetch URL → extract HTML → change detect → summarize. Rank by impact (GA, pricing, API, security).
- **Output**: Findings with category=release, publisher=competitor name.

### Agent 2 — Foundation Model Provider Release Watcher

- **Config**: `agents.model_providers[]`: name, urls[], rss_feeds[], focus[] (models, api, pricing, safety).
- **Logic**: Same as competitor: RSS + URL fetch, extract, summarize. Focus on model name, modalities, context length, pricing, benchmarks claimed.
- **Output**: Findings category=release, publisher=provider.

### Agent 3 — Research Publication Scout

- **Config**: `agents.research`: arxiv_categories[], relevance_keywords[], curated_urls[].
- **Logic**: arXiv API (cat:cs.CL, etc.) + curated URLs. Summarize with relevance scoring (benchmark, eval, agent, multimodal, safety).
- **Output**: Findings category=research.

### Agent 4 — Hugging Face Benchmark Tracker

- **Config**: `agents.hf_benchmarks`: leaderboards[], tasks[], track_new_sota.
- **Logic**: Placeholder/structured findings for configured leaderboards; can be extended with HF API.
- **Output**: Findings category=benchmark.

### Digest Agent

- **Input**: run_id (findings already in DB).
- **Steps**: Load findings for run → cluster by category → build exec summary (top 7) → render PDF (ReportLab) → optional email.
- **Output**: Digest row (pdf_path, executive_summary, top_finding_ids, recipients, sent_at).

---

## 4. Configuration design

### radar.yaml

```yaml
global:
  run_time: "06:30"
  timezone: "America/Los_Angeles"
  max_pages_per_domain: 50
  default_rate_limit: 1.0
  email_recipients: []

agents:
  competitors: [{ name, release_urls, rss_feeds, keywords, domain_rate_limit }]
  model_providers: [{ name, urls, rss_feeds, focus }]
  research: { arxiv_categories, relevance_keywords, curated_urls }
  hf_benchmarks: { leaderboards, tasks, track_new_sota }
```

### Environment (.env)

- **DATABASE_URL** — Default `sqlite+aiosqlite:///./radar.db`
- **OPENAI_API_KEY** — Optional; if missing, summarizer uses rule-based fallback
- **SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD, SMTP_FROM, EMAIL_RECIPIENTS** — Optional email
- **CONFIG_PATH** — Path to radar.yaml (default `config/radar.yaml`)
- **CORS_ORIGINS** — e.g. `["http://localhost:3000"]`

---

## 5. Storage and data model

- **sources** — url, agent_id, name, rss_feed, selectors, keywords, rate_limit, enabled, etc.
- **snapshots** — url, fetched_at, content_hash, raw_content (for change detection / future diff).
- **extractions** — url, title, published_date, text, metadata (optional pipeline step).
- **findings** — run_id, source_id, title, date_detected, source_url, publisher, category, summary_short/long, why_it_matters, evidence, confidence, tags, entities, diff_hash, agent_id, impact_score.
- **runs** — status, started_at, finished_at, trigger, agent_results (JSON), findings_count, error_message.
- **digests** — run_id, pdf_path, executive_summary, top_finding_ids, recipients, sent_at.

Caching: if content_hash unchanged, skip re-summarization (implemented in change_detector + agent logic when snapshots are used).

---

## 6. Ranking and impact score

Formula (example):  
`Impact = 0.35*Relevance + 0.25*Novelty + 0.20*Credibility + 0.20*Actionability`

- **Relevance**: matches tracked entities/topics (tags, category).
- **Novelty**: new vs last run (simplified as default 0.8).
- **Credibility**: confidence score from summarizer (official source vs third-party).
- **Actionability**: presence of why_it_matters and concrete changes.

Implemented in `run_manager._impact_score()` and persisted as `Finding.impact_score`.

---

## 7. Security and compliance

- **Secrets**: Stored in .env (or vault); never in repo.
- **Rate limiting**: Per-domain throttle; configurable.
- **User-Agent**: Identifiable string in fetcher.
- **robots.txt**: Respect where required (fetcher can be extended to check).
- **PII**: Not collected; if detected, should be redacted in summarizer prompts.

---

## 8. API reference (summary)

- **POST /api/runs/** — Body: `{ "trigger": "manual" }`. Creates run, starts pipeline in background, returns Run.
- **GET /api/runs/** — List runs (latest first).
- **GET /api/runs/{id}** — Run detail + digest_id.
- **GET/POST/PATCH/DELETE /api/sources/** — CRUD sources (url, agent_id, name, etc.).
- **GET /api/findings/?run_id=&agent_id=&category=&limit=** — List findings.
- **GET /api/findings/{id}** — Finding detail.
- **GET /api/digests/** — List digests.
- **GET /api/digests/{id}** — Digest metadata.
- **GET /api/digests/{id}/download** — PDF file.
- **GET /api/config/** — Current radar YAML config.
- **PUT /api/config/** — Save config (body: YAML-like dict).

---

## 9. Web UI (hackathon)

- **Dashboard**: Last run status, top 10 updates, “Run now”, link to digest/run history.
- **Sources**: Add/edit/delete URLs, assign agent, list by agent.
- **Runs**: Table of runs (status, started, findings count, link to digest).
- **Findings**: Filter by agent/category, list with title, summary, confidence, link to source.
- **Digest archive**: List digests, download PDF.

Frontend calls backend at `NEXT_PUBLIC_API_URL` (default `http://localhost:8000/api`). CORS must allow the frontend origin.

---

## 10. How to run (recap)

1. **Backend**: `cd backend` → venv, `pip install -r requirements.txt`, `.env` from `.env.example` → `uvicorn app.main:app --reload --port 8000`.
2. **Frontend**: `cd frontend` → `npm install` → `npm run dev` (port 3000).
3. **Demo**: Add source → Run now → View findings → Download PDF (and optionally receive email).

---

## 11. Deliverables checklist (spec)

- Multi-agent pipeline (4 crawlers + digest agent)
- Configurable URLs per agent (YAML + UI)
- Daily scheduler + manual run
- Dedup + ranking
- PDF digest (branded template)
- Email distribution (optional)
- UI: sources, runs, archive
- Observability: logs, agent_results per run, per-URL trace in logs

All items above are implemented in this repository.
