"""Run Manager: execute agents in parallel, persist findings, run digest agent."""

import asyncio
import hashlib
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

import yaml
from sqlalchemy import select

from app.agents.competitor import CompetitorAgent
from app.agents.digest import DigestAgent
from app.agents.hf_benchmarks import HFBenchmarksAgent
from app.agents.model_provider import ModelProviderAgent
from app.agents.research import ResearchAgent
from app.config import get_settings
from app.db.database import async_session
from app.db.models import Extraction, Finding, Run, Snapshot, Source
from app.schemas.finding import FindingCreate
from app.schemas.run import RunStatus
from app.services.dedup import DedupService
from app.services.run_logger import RunLogCollector

logger = logging.getLogger(__name__)


def _normalize_url(url: str) -> str:
    """Normalize URL for comparison: strip, lowercase scheme+host, remove trailing slash."""
    u = (url or "").strip()
    if not u:
        return ""
    u = u.rstrip("/")
    return u


def load_radar_config(full: bool = False) -> Dict[str, Any]:
    """Load radar config from YAML.

    full=False (default): only global settings; agent sources come from DB.
    full=True: load entire YAML including agents section (for explicit YAML runs).
    """
    settings = get_settings()
    path = Path(settings.config_path)
    if not path.is_absolute():
        path = Path.cwd() / path
    if not path.exists():
        alt = Path.cwd() / "backend" / "config" / "radar.yaml"
        if alt.exists():
            path = alt
        else:
            return {"global": {}, "agents": {}}
    with open(path) as f:
        data = yaml.safe_load(f) or {}
    global_section = data.get("global") or {}
    if full:
        return {"global": global_section, "agents": data.get("agents") or {}}
    return {"global": global_section, "agents": {}}


async def merge_sources_into_config(config: Dict[str, Any]) -> Dict[str, Any]:
    """Build agent config from ALL enabled DB sources (daily re-crawl). Change detection skips unchanged content."""
    agents = config.setdefault("agents", {})
    source_ids: List[int] = []
    try:
        async with async_session() as session:
            result = await session.execute(select(Source).where(Source.enabled == True))
            sources = result.scalars().all()
    except Exception as e:
        logger.warning("Could not load sources from DB: %s", e)
        config["_source_ids"] = source_ids
        return config

    url_to_source_id: Dict[str, int] = {}
    for s in sources:
        if not s.url or not s.agent_id:
            continue
        source_ids.append(s.id)
        all_urls = [u.strip() for u in s.url.split(",") if u.strip()]
        for u in all_urls:
            url_to_source_id[u] = s.id
        name = (s.name or all_urls[0])[:200]
        if s.agent_id == "competitors":
            agents.setdefault("competitors", [])
            if not isinstance(agents["competitors"], list):
                agents["competitors"] = []
            agents["competitors"].append(
                {
                    "name": name,
                    "source_config_url": all_urls[0],
                    "release_urls": all_urls,
                    "rss_feeds": [s.rss_feed] if s.rss_feed else [],
                    "keywords": s.keywords if s.keywords is not None else [],
                    "selectors": s.selectors,
                    "domain_rate_limit": (
                        float(s.rate_limit) if s.rate_limit is not None else None
                    ),
                }
            )
        elif s.agent_id == "model_providers":
            agents.setdefault("model_providers", [])
            if not isinstance(agents["model_providers"], list):
                agents["model_providers"] = []
            agents["model_providers"].append(
                {
                    "name": name,
                    "source_config_url": all_urls[0],
                    "urls": all_urls,
                    "rss_feeds": [s.rss_feed] if s.rss_feed else [],
                    "focus": (
                        (s.extra_config or {}).get("focus")
                        if isinstance(s.extra_config, dict)
                        else None
                    ),
                    "selectors": s.selectors,
                    "domain_rate_limit": (
                        float(s.rate_limit) if s.rate_limit is not None else None
                    ),
                }
            )
        elif s.agent_id == "research":
            agents.setdefault("research", {})
            if not isinstance(agents["research"], dict):
                agents["research"] = {}
            curated = agents["research"].get("curated_urls") or []
            for u in all_urls:
                if u not in curated:
                    curated.append(u)
            agents["research"]["curated_urls"] = curated
            if (
                isinstance(s.extra_config, dict)
                and s.extra_config.get("relevance_keywords") is not None
            ):
                agents["research"]["relevance_keywords"] = s.extra_config.get(
                    "relevance_keywords"
                )
        elif s.agent_id == "hf_benchmarks":
            agents.setdefault("hf_benchmarks", {})
            if not isinstance(agents["hf_benchmarks"], dict):
                agents["hf_benchmarks"] = {}
            urls = agents["hf_benchmarks"].get("leaderboard_urls") or []
            for u in all_urls:
                if u not in urls:
                    urls.append(u)
            agents["hf_benchmarks"]["leaderboard_urls"] = urls

    config["_source_ids"] = source_ids
    config["_url_to_source_id"] = url_to_source_id

    for comp in agents.get("competitors") or []:
        if not comp.get("source_config_url"):
            urls = comp.get("release_urls") or []
            if urls:
                comp["source_config_url"] = urls[0].strip()
    for prov in agents.get("model_providers") or []:
        if not prov.get("source_config_url"):
            urls = prov.get("urls") or []
            if urls:
                prov["source_config_url"] = urls[0].strip()

    return config


def _impact_score(f: FindingCreate) -> float:
    """Impact = 0.35*Relevance + 0.25*Novelty + 0.20*Credibility + 0.20*Actionability."""
    has_tags = bool(f.tags)
    has_entities = bool(f.entities)
    relevance = 0.9 if (has_tags and has_entities) else 0.7 if has_tags else 0.5

    try:
        age_days = (datetime.now(timezone.utc) - f.date_detected).days
    except Exception:
        age_days = 0
    novelty = 1.0 if age_days <= 1 else 0.8 if age_days <= 7 else 0.5

    credibility = min(1.0, max(0.0, f.confidence))

    actionability = (
        0.8
        if f.why_it_matters and len(f.why_it_matters) > 20
        else 0.4 if f.why_it_matters else 0.2
    )

    return 0.35 * relevance + 0.25 * novelty + 0.20 * credibility + 0.20 * actionability


class RunManager:
    """Orchestrate one pipeline run: agents 1-4 -> dedup -> persist -> digest agent."""

    async def start_run(
        self,
        trigger: str = "manual",
        pipeline_name: str | None = None,
        pipeline_description: str | None = None,
        config_override: dict | None = None,
        use_yaml: bool = False,
    ):
        """Create run record and return (run_id, config).

        use_yaml=True: load full YAML (agents + global) and merge with DB sources.
        config_override: use provided JSON config and merge with DB sources.
        Neither: load only global from YAML, agents come from DB sources only.
        """
        if config_override:
            config = {
                "global": {},
                "agents": config_override.get("agents", config_override),
            }
            config = await merge_sources_into_config(config)
        elif use_yaml:
            config = load_radar_config(full=True)
            config = await merge_sources_into_config(config)
        else:
            config = load_radar_config()
            config = await merge_sources_into_config(config)
        agents = config.get("agents", {}) or {}
        research = (
            agents.get("research") if isinstance(agents.get("research"), dict) else {}
        )
        curated = research.get("curated_urls")
        research_urls = curated if isinstance(curated, list) else []
        hf_cfg = (
            agents.get("hf_benchmarks")
            if isinstance(agents.get("hf_benchmarks"), dict)
            else {}
        )
        hf_urls = (
            hf_cfg.get("leaderboard_urls") or [] if isinstance(hf_cfg, dict) else []
        )
        logger.info(
            "Pipeline sources (DB): competitors=%s model_providers=%s research_urls=%s hf_urls=%s",
            len(agents.get("competitors") or []),
            len(agents.get("model_providers") or []),
            len(research_urls),
            len(hf_urls),
        )
        async with async_session() as session:
            run = Run(
                pipeline_name=pipeline_name,
                pipeline_description=pipeline_description,
                status=RunStatus.PENDING.value,
                trigger=trigger,
                started_at=datetime.now(timezone.utc),
            )
            session.add(run)
            await session.flush()
            run_id = run.id
            try:
                run.status = RunStatus.RUNNING.value
                await session.commit()
            except Exception:
                await session.rollback()
                raise
        return run_id, config

    async def _execute_run(self, run_id: int, config: Dict[str, Any]) -> None:
        log_collector = RunLogCollector(run_id)
        log_collector.setFormatter(logging.Formatter("%(message)s"))
        root_logger = logging.getLogger("app")
        root_logger.addHandler(log_collector)

        logger.info("Pipeline background task started for run_id=%s", run_id)
        async with async_session() as session:
            run = await session.get(Run, run_id)
            if not run:
                logger.warning("Run %s not found", run_id)
                root_logger.removeHandler(log_collector)
                return
            try:
                logger.info(
                    "Run %s: starting pipeline (config agents: %s)",
                    run_id,
                    list(config.get("agents", {}).keys()),
                )
                agent_results: Dict[str, Any] = {}
                agents_config = config.get("agents", {})
                from app.agents.base import AgentContext

                since = datetime.now(timezone.utc).replace(
                    hour=0, minute=0, second=0, microsecond=0
                )
                context = AgentContext(
                    run_id=run_id, agent_config=agents_config, since_timestamp=since
                )

                max_concurrent = max(
                    1, getattr(get_settings(), "agent_max_concurrent", 2)
                )
                sem = asyncio.Semaphore(max_concurrent)

                async def run_agent(agent, ctx):
                    async with sem:
                        return await agent.run(ctx)

                AGENT_FACTORY = {
                    "competitors": ("Competitors", CompetitorAgent),
                    "model_providers": ("Model Providers", ModelProviderAgent),
                    "research": ("Research", ResearchAgent),
                    "hf_benchmarks": ("HF Benchmarks", HFBenchmarksAgent),
                }

                agents_to_run: List[tuple] = []
                for agent_key, (agent_label, agent_cls) in AGENT_FACTORY.items():
                    if agents_config.get(agent_key):
                        agents_to_run.append((agent_key, agent_label, agent_cls()))

                if not agents_to_run:
                    logger.info(
                        "Run %s: no sources configured — nothing to run", run_id
                    )

                results = await asyncio.gather(
                    *[run_agent(agent, context) for _, _, agent in agents_to_run],
                    return_exceptions=True,
                )

                all_findings: List[FindingCreate] = []
                for i, r in enumerate(results):
                    name, log_name, _ = agents_to_run[i]
                    if isinstance(r, Exception):
                        agent_results[name] = {
                            "status": "failed",
                            "error": str(r)[:500],
                            "count": 0,
                            "pages_processed": 0,
                        }
                        logger.error(
                            "Run %s: [AGENT %d/%d: %s] FAILED — %s",
                            run_id,
                            i + 1,
                            len(agents_to_run),
                            log_name,
                            str(r)[:500],
                        )
                    else:
                        pages = getattr(r, "pages_processed", 0)
                        agent_results[name] = {
                            "status": r.status,
                            "count": len(r.findings),
                            "error": r.error_message,
                            "pages_processed": pages,
                        }
                        all_findings.extend(r.findings)
                        logger.info(
                            "Run %s: [AGENT %d/%d: %s] status=%s pages_crawled=%d findings=%d",
                            run_id,
                            i + 1,
                            len(agents_to_run),
                            log_name,
                            r.status,
                            pages,
                            len(r.findings),
                        )
                        if r.error_message:
                            logger.warning(
                                "Run %s: [AGENT %s] partial error: %s",
                                run_id,
                                log_name,
                                r.error_message[:300],
                            )
                        for fi, finding in enumerate(r.findings):
                            logger.info(
                                "Run %s: [AGENT %s] Finding %d: '%s' (url=%s, diff_hash=%s, has_content=%s)",
                                run_id,
                                log_name,
                                fi + 1,
                                (finding.title or "")[:80],
                                str(finding.source_url)[:100],
                                "yes" if finding.diff_hash else "no",
                                (
                                    "yes"
                                    if (finding.raw_content or finding.extracted_text)
                                    else "no"
                                ),
                            )

                logger.info(
                    "Run %s: agents done, total raw findings=%s",
                    run_id,
                    len(all_findings),
                )
                dedup = DedupService()
                all_findings = dedup.deduplicate(all_findings)
                logger.info(
                    "Run %s: after dedup findings=%s", run_id, len(all_findings)
                )

                url_to_source_id_raw = config.get("_url_to_source_id") or {}
                url_to_source_id_norm: Dict[str, int] = {}
                for k, v in url_to_source_id_raw.items():
                    url_to_source_id_norm[_normalize_url(k)] = v

                def _resolve_source_id(cfg_url: str, src_url: str) -> int | None:
                    cfg_n = _normalize_url(cfg_url)
                    src_n = _normalize_url(src_url)
                    sid = url_to_source_id_norm.get(cfg_n) or url_to_source_id_norm.get(
                        src_n
                    )
                    if sid:
                        return sid
                    for key, val in url_to_source_id_norm.items():
                        if key and (src_n.startswith(key) or cfg_n.startswith(key)):
                            return val
                    return None

                saved_findings = 0
                saved_snapshots = 0
                saved_extractions = 0
                source_id_resolved = 0
                source_id_missing = 0

                for f in all_findings:
                    source_url_str = str(f.source_url or "").strip()
                    source_cfg_url = (f.source_config_url or "").strip()
                    source_id = _resolve_source_id(source_cfg_url, source_url_str)

                    if source_id:
                        source_id_resolved += 1
                    else:
                        source_id_missing += 1
                        logger.warning(
                            "Run %s: source_id not resolved for finding '%s' (config_url=%s, source_url=%s)",
                            run_id,
                            (f.title or "")[:60],
                            source_cfg_url,
                            source_url_str,
                        )

                    summary_short = (f.summary_short or f.title or "")[:1024]
                    finding = Finding(
                        run_id=run_id,
                        source_id=source_id,
                        title=(f.title or "Untitled")[:512],
                        date_detected=f.date_detected,
                        source_url=source_url_str[:2048],
                        publisher=(f.publisher[:256] if f.publisher else None),
                        category=(f.category or "release")[:64],
                        summary_short=summary_short[:1024],
                        summary_long=f.summary_long,
                        why_it_matters=f.why_it_matters,
                        evidence=f.evidence,
                        confidence=round(min(0.95, max(0.0, f.confidence)), 2),
                        tags=f.tags if isinstance(f.tags, list) else [],
                        entities=f.entities if isinstance(f.entities, list) else [],
                        diff_hash=f.diff_hash[:64] if f.diff_hash else None,
                        agent_id=(f.agent_id or "unknown")[:64],
                        raw_metadata=f.raw_metadata,
                        impact_score=_impact_score(f),
                    )
                    session.add(finding)
                    saved_findings += 1

                    content_hash = (
                        f.diff_hash[:64]
                        if f.diff_hash
                        else hashlib.sha256(source_url_str.encode()).hexdigest()[:64]
                    )
                    raw_content = f.raw_content or f.extracted_text or ""
                    snapshot = Snapshot(
                        url=source_url_str[:2048],
                        source_id=source_id,
                        fetched_at=datetime.now(timezone.utc),
                        content_hash=content_hash,
                        raw_content=raw_content[:100000] if raw_content else None,
                        content_type=f.content_type or "text/html",
                    )
                    session.add(snapshot)
                    await session.flush()
                    saved_snapshots += 1

                    extracted = f.extracted_text or raw_content or ""
                    extraction = Extraction(
                        url=source_url_str[:2048],
                        snapshot_id=snapshot.id,
                        title=(f.title or "Untitled")[:512],
                        published_date=f.date_detected,
                        text=extracted[:100000] if extracted else None,
                        extracted_metadata=f.raw_metadata,
                    )
                    session.add(extraction)
                    saved_extractions += 1

                logger.info(
                    "Run %s: DB persistence — findings=%d, snapshots=%d, extractions=%d, "
                    "source_id_resolved=%d, source_id_missing=%d",
                    run_id,
                    saved_findings,
                    saved_snapshots,
                    saved_extractions,
                    source_id_resolved,
                    source_id_missing,
                )
                run.agent_results = agent_results
                run.findings_count = len(all_findings)
                status = (
                    RunStatus.PARTIAL.value
                    if any(
                        ar.get("status") == "failed" for ar in agent_results.values()
                    )
                    else RunStatus.SUCCESS.value
                )
                run.status = status
                run.finished_at = datetime.now(timezone.utc)
                run.error_message = None
                await session.flush()

                digest_agent = DigestAgent(session)
                try:
                    await digest_agent.run(context)
                except Exception as e:
                    logger.exception("Digest agent failed: %s", e)

                processed_source_ids = config.get("_source_ids") or []
                if processed_source_ids:
                    for sid in processed_source_ids:
                        src = await session.get(Source, sid)
                        if src:
                            src.last_run_id = run_id
                    logger.info(
                        "Run %s: marked %s sources as processed",
                        run_id,
                        len(processed_source_ids),
                    )

                logger.info(
                    "Run %s: finished status=%s findings_count=%s",
                    run_id,
                    run.status,
                    run.findings_count,
                )
                root_logger.removeHandler(log_collector)
                for entry in log_collector.get_orm_entries():
                    session.add(entry)
                await session.commit()
            except Exception as e:
                logger.exception("Run %s failed: %s", run_id, e)
                run.status = RunStatus.FAILED.value
                run.finished_at = datetime.now(timezone.utc)
                run.error_message = str(e)[:2000]
                root_logger.removeHandler(log_collector)
                for entry in log_collector.get_orm_entries():
                    session.add(entry)
                try:
                    await session.commit()
                except Exception:
                    await session.rollback()
        return
