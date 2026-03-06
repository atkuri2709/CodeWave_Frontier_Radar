# Frontier AI Radar — Detailed Documentation

## 1. System overview

The system is a **daily batch pipeline** that:

1. **Crawls** configurable sources (URLs, RSS) per agent
2. **Extracts** main text and metadata (HTML, RSS; optional PDF)
3. **Detects change** via content hashing to avoid re-processing unchanged pages
4. **Summarizes** with an LLM (or rule-based fallback) into structured findings
5. **Detects SOTA claims** using keyword pattern matching with confidence scoring
6. **Normalizes entities** to canonical forms (OpenAI, DeepMind, Meta, etc.)
7. **Deduplicates** and **clusters** findings by topic/entity
8. **Ranks** by impact (relevance, novelty, credibility, actionability)
9. **Compiles** a PDF digest (exec summary + sections + SOTA Watch + citations)
10. **Delivers** by email (optional) and stores PDF for the Web UI

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
| **SOTA detector** | Keyword pattern matching (18 patterns) with weighted confidence scoring |
| **Entity normalizer** | Canonical name mapping for 30+ AI companies and labs |
| **Dedup** | Same URL/title or diff_hash; cluster by category |
| **Knowledge store** | SQLite (or Postgres): sources, snapshots, extractions, findings, runs, digests, pipeline_configs, scheduled_jobs |
| **Analytics service** | SOTA Watch query + Entity Heatmap aggregation (entity vs 6 topics) |
| **PDF generator** | ReportLab: cover, exec summary, SOTA Watch, sections by category, appendix |
| **Email** | SMTP/Mailgun: inline summary + PDF attachment |
| **Web UI** | Next.js 14: dashboard, pipeline management, runs, findings, analytics, scheduler, digest archive |

### Data flow (one run)

```
Scheduler or POST /api/runs/
    → RunManager.start_run()
    → Create Run (status=running)
    → asyncio.gather(Competitor, ModelProvider, Research, HF)
    → DedupService.deduplicate(findings)
    → For each finding:
        → normalize_entities(entities)
        → detect_sota_claim(title + summary_long + evidence)
        → compute _impact_score()
    → Persist Finding rows (run_id, impact_score, is_sota, sota_confidence)
    → DigestAgent.run(): load findings, cluster, generate PDF (incl. SOTA Watch), email
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
- **Logic**: Prefer RSS → parse entries → summarize each; else fetch URL → extract HTML → change detect → summarize.
- **Output**: Findings with category=release, publisher=competitor name.

### Agent 2 — Foundation Model Provider Release Watcher

- **Config**: `agents.model_providers[]`: name, urls[], rss_feeds[], focus[] (models, api, pricing, safety).
- **Logic**: Same as competitor: RSS + URL fetch, extract, summarize. Focus on model name, modalities, context length, pricing, benchmarks claimed.
- **Output**: Findings category=release, publisher=provider.

### Agent 3 — Research Publication Scout

- **Config**: `agents.research`: arxiv_categories[], relevance_keywords[], curated_urls[].
- **Logic**: arXiv API (cat:cs.CL, etc.) + curated URLs. Filters by `since_timestamp` to skip old papers. Summarize with relevance scoring.
- **Output**: Findings category=research.

### Agent 4 — Hugging Face Benchmark Tracker

- **Config**: `agents.hf_benchmarks`: leaderboards[], tasks[], track_new_sota.
- **Logic**: Structured findings for configured leaderboards; can be extended with HF API.
- **Output**: Findings category=benchmark.

### Digest Agent

- **Input**: run_id (findings already in DB).
- **Steps**: Load findings for run → cluster by category → identify SOTA findings → build exec summary (top 7) → render PDF (ReportLab, includes SOTA Watch section) → optional email.
- **Output**: Digest row (pdf_path, executive_summary, top_finding_ids, recipients, sent_at).

---

## 4. SOTA Detection System

### Module: `backend/app/utils/sota_detection.py`

**Function**: `detect_sota_claim(text: str) → {"is_sota": bool, "confidence": float}`

**Logic**:
1. Combine title + summary_long + evidence into a single text
2. Lowercase and scan against 18 regex patterns (e.g., "state-of-the-art", "outperforms", "rank #1", "new benchmark record")
3. Each pattern has a weight (0.70–1.00)
4. Return `is_sota=True` if any pattern matches, with confidence = highest weight + small bonus for multiple matches

**Integration**: Called in `run_manager.py` when persisting each finding. Results stored as `Finding.is_sota` and `Finding.sota_confidence`.

---

## 5. Entity Normalization

### Module: `backend/app/utils/entity_normalizer.py`

**Function**: `normalize_entity(name: str) → str` / `normalize_entities(entities: list) → list`

**Logic**:
1. Strip whitespace and corporate suffixes (Inc, LLC, Ltd, etc.)
2. Lowercase lookup against `ENTITY_MAP` (30+ canonical mappings)
3. Return canonical name or cleaned original

**Mappings include**: OpenAI, Anthropic, DeepMind, Google, Meta, HuggingFace, Mistral AI, Cohere, Microsoft, NVIDIA, Amazon, Apple, Alibaba, Stability AI, xAI, Inflection AI, AI21 Labs.

**Integration**: Called in `run_manager.py` before persisting entities. Normalized entities are stored in `Finding.entities`.

---

## 6. Analytics

### SOTA Watch API: `GET /api/analytics/sota-watch?limit=20`

Queries findings where `is_sota=True`, ordered by `date_detected DESC`. Returns title, entities, source_url, confidence, sota_confidence, category, agent_id.

### Entity Heatmap API: `GET /api/analytics/entity-heatmap?days=7`

**Service**: `backend/app/services/analytics_service.py`

**Logic**:
1. Fetch findings from the last N days
2. For each finding, classify into topics using keyword matching: **models**, **research**, **benchmarks**, **pricing**, **safety**, **tooling**
3. Normalize entities and count occurrences per topic
4. Return `{ entities: [], topics: [], matrix: [[]] }` for frontend heatmap rendering

---

## 7. Configuration design

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

- **DATABASE_URL** — Default `sqlite+aiosqlite:///./data/radar.db`
- **OPENAI_API_KEY** — Optional; if missing, summarizer uses rule-based fallback
- **SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD, SMTP_FROM, EMAIL_RECIPIENTS** — Optional email (SMTP)
- **MAILGUN_API_KEY, MAILGUN_DOMAIN** — Optional email (Mailgun fallback)
- **CONFIG_PATH** — Path to radar.yaml (default `config/radar.yaml`)
- **CORS_ORIGINS** — e.g. `["http://localhost:3000"]`

---

## 8. Storage and data model

- **sources** — url, agent_id, pipeline_id, name, rss_feed, selectors, keywords, rate_limit, include_rules, exclude_rules, enabled, extra_config.
- **pipeline_configs** — pipeline_name, pipeline_description, config_json, enabled.
- **snapshots** — url, fetched_at, content_hash, raw_content (for change detection).
- **extractions** — url, title, published_date, text, metadata.
- **findings** — run_id, source_id, title, date_detected, source_url, publisher, category, summary_short/long, why_it_matters, evidence, confidence, tags, entities, diff_hash, agent_id, impact_score, **is_sota**, **sota_confidence**, raw_metadata.
- **runs** — pipeline_name, pipeline_description, status, started_at, finished_at, trigger, agent_results (JSON), findings_count, error_message.
- **digests** — run_id, pdf_path, executive_summary, top_finding_ids, recipients, sent_at.
- **scheduled_jobs** — pipeline_name, scheduler_name, frequency, run_time, timezone, start/end date/time, interval_minutes, enabled.
- **run_logs** — run_id, timestamp, level, logger_name, message.
- **email_recipients** — email addresses for digest distribution.

---

## 9. Ranking and impact score

Formula:
`Impact = 0.35*Relevance + 0.25*Novelty + 0.20*Credibility + 0.20*Actionability`

- **Relevance**: matches tracked entities/topics (tags + entities present → 0.9).
- **Novelty**: age-based (≤1 day → 1.0, ≤7 days → 0.8, older → 0.5).
- **Credibility**: confidence score from summarizer (clamped 0–1).
- **Actionability**: presence and length of why_it_matters field.

Implemented in `run_manager._impact_score()` and persisted as `Finding.impact_score`.

---

## 10. Security and compliance

- **Secrets**: Stored in .env (or vault); never in repo.
- **Rate limiting**: Per-domain throttle; configurable.
- **User-Agent**: Identifiable string in fetcher.
- **robots.txt**: Respect where required (fetcher can be extended to check).
- **PII**: Not collected; if detected, should be redacted in summarizer prompts.

---

## 11. API reference (summary)

### Core APIs

- **POST /api/runs/** — Trigger a pipeline run. Body: `{ "trigger": "manual", "pipeline_name": "..." }`.
- **GET /api/runs/** — List runs (latest first).
- **GET /api/runs/{id}** — Run detail + digest_id.
- **GET/POST/PATCH/DELETE /api/sources/** — CRUD sources (url, agent_id, pipeline_id, etc.).
- **GET /api/sources/detect-agent?url=** — Auto-detect the best agent for a URL.
- **GET /api/findings/** — List findings (?run_id=&agent_id=&category=&created_after=&created_before=&limit=&offset=).
- **GET /api/findings/{id}** — Finding detail (includes is_sota, sota_confidence, impact_score).

### Analytics APIs

- **GET /api/analytics/sota-watch?limit=20** — SOTA findings (is_sota=true), ordered by date.
- **GET /api/analytics/entity-heatmap?days=7** — Entity vs topic frequency matrix.

### Pipeline & Scheduler APIs

- **GET/POST/PATCH/DELETE /api/pipeline-configs/** — CRUD pipeline configurations.
- **GET/POST/PATCH/DELETE /api/scheduler/** — CRUD scheduled jobs.
- **GET /api/scheduler/status** — Scheduler running status.
- **POST /api/scheduler/restart** — Restart the scheduler.

### Other APIs

- **GET /api/digests/** — List digests.
- **GET /api/digests/{id}/download** — PDF file download.
- **GET/PUT /api/email-recipients** — Manage digest email recipients.
- **GET /api/meta/** — Dynamic agent and category metadata.
- **GET /api/config/** — Current radar YAML config.

---

## 12. Web UI (pages)

- **Dashboard**: Last run status (auto-refreshes every 60s), top 10 findings with impact/confidence scores, "Run now" (pipeline selector, YAML, JSON), download PDF link.
- **Pipeline (Sources)**: Add/edit/delete pipelines with source URLs. Each source has a URL and auto-detected agent. Pipeline active/inactive toggle. Delete protection if linked to a scheduler.
- **Runs**: Table of runs (status, started, findings count, link to digest).
- **Findings**: Filter by agent/category/entity/publisher/tag/search. Diff mode to compare today vs yesterday. Impact score and SOTA badge display.
- **Analytics**: Three tabs — Diff Viewer (added/removed/persisted), SOTA Watch (from `/analytics/sota-watch` API), Entity Heatmap (from `/analytics/entity-heatmap` API).
- **Scheduler**: Create/edit/delete scheduled jobs. Shows status (running/completed), next scheduled time. Toggle enable/disable.
- **Digest archive**: List digests, download PDF, manage email recipients.

Frontend calls backend at `NEXT_PUBLIC_API_URL` (default `http://localhost:8000/api`). CORS must allow the frontend origin.

---

## 13. How to run (recap)

1. **Backend**: `cd backend` → venv, `pip install -r requirements.txt`, `.env` from `.env.example` → `uvicorn app.main:app --reload --port 8000`.
2. **Frontend**: `cd frontend` → `npm install` → `npm run dev` (port 3000).
3. **Docker**: `docker-compose up --build` (backend on 8000, frontend on 3000).
4. **Demo**: Add pipeline with sources → Run now → View findings (with SOTA badges) → Analytics → Download PDF → Set up scheduler.

---

## 14. Deliverables checklist (spec)

- Multi-agent pipeline (4 crawlers + digest agent)
- Configurable URLs per agent (YAML + UI pipeline management)
- 1 URL → 1 Agent source mapping with auto-detection
- SOTA detection system with confidence scoring
- Entity normalization for consistent analytics
- Analytics: SOTA Watch API + Entity Heatmap API
- Daily scheduler + manual run
- Dedup + impact ranking
- PDF digest (branded template with SOTA Watch section)
- Email distribution (SMTP + Mailgun fallback)
- UI: dashboard, pipelines, runs, findings (with diff view), analytics, scheduler, digest archive
- Observability: logs, agent_results per run, per-URL trace in logs

All items above are implemented in this repository.
