"""Agent #2 — Foundation Model Provider Release Watcher.

Track model releases, API updates, pricing, safety, and evaluation claims from
configurable provider URLs (docs, release notes, blog, status). Prefer official sources.
Output focus: model name/version, modalities, context length, tool use, pricing, safety, benchmarks.
Optional: SOTA claims can be flagged for verification (Agent #4).
"""

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List

from app.agents.base import AgentContext, AgentResult, BaseAgent
from app.schemas.finding import FindingCreate
from app.services.change_detector import ChangeDetector
from app.services.extractor import ExtractorService
from app.services.fetcher import FetcherService
from app.services.summarizer import SummarizerService

logger = logging.getLogger(__name__)


class ModelProviderAgent(BaseAgent):
    agent_id = "model_providers"

    def __init__(self):
        self.fetcher = FetcherService()
        self.extractor = ExtractorService()
        self.detector = ChangeDetector()
        self.summarizer = SummarizerService()

    async def run(self, context: AgentContext) -> AgentResult:
        findings: List[FindingCreate] = []
        pages_crawled = 0
        config = context.agent_config or {}
        providers = config.get("model_providers") or []
        if not providers:
            return AgentResult(
                agent_id=self.agent_id, findings=[], status="success", pages_processed=0
            )

        since = context.since_timestamp

        for pi, prov in enumerate(providers):
            name = prov.get("name") or "Unknown"
            urls = prov.get("urls") or []
            rss_feeds = prov.get("rss_feeds") or []
            logger.info(
                "[ModelProviders] Processing source %d/%d: '%s' — %d URLs, %d RSS feeds, config_url=%s",
                pi + 1,
                len(providers),
                name,
                len(urls),
                len(rss_feeds),
                prov.get("source_config_url", "none"),
            )
            focus = prov.get("focus")
            if focus is None:
                focus = []
            if not isinstance(focus, list):
                focus = []
            selectors = prov.get("selectors")
            domain_rate_limit = prov.get("domain_rate_limit")
            if domain_rate_limit is not None:
                try:
                    domain_rate_limit = float(domain_rate_limit)
                except (TypeError, ValueError):
                    domain_rate_limit = None

            seen_urls: set[str] = set()

            # RSS first
            for feed_url in rss_feeds:
                try:
                    code, body, ct, _ = await self.fetcher.fetch(
                        feed_url, rate_limit=domain_rate_limit
                    )
                    if code != 200 or not body:
                        continue
                    ct_lower = (ct or "").lower()
                    if (
                        "xml" not in ct_lower
                        and "rss" not in ct_lower
                        and "atom" not in ct_lower
                    ):
                        continue
                    entries = self.extractor.parse_rss(body, feed_url)
                    for e in entries:
                        entry_link = (e.get("link") or e.get("id") or "").strip()
                        if entry_link and entry_link in seen_urls:
                            continue
                        if entry_link:
                            seen_urls.add(entry_link)
                        try:
                            f = await self._rss_entry_to_finding(
                                e, name, focus, context, prov
                            )
                            if f:
                                findings.append(f)
                        except Exception as e:
                            logger.warning("Model provider RSS entry failed: %s", e)
                except Exception as e:
                    logger.warning("Model provider RSS %s failed: %s", feed_url, e)

            # Then URL list (docs, release notes, blog)
            for url in urls:
                if not url or not isinstance(url, str):
                    continue
                url = url.strip()
                if url in seen_urls:
                    continue
                seen_urls.add(url)
                try:
                    code, html, _, content_hash = await self.fetcher.fetch(
                        url, rate_limit=domain_rate_limit
                    )
                    pages_crawled += 1
                    if code != 200:
                        logger.info(
                            "[ModelProviders] '%s' URL: HTTP %d — skipped (%s)",
                            name,
                            code,
                            url[:80],
                        )
                        continue
                    title, text, pub_date, meta = self.extractor.extract_html(
                        html, url, selectors
                    )
                    if not (text or "").strip() or len((text or "").strip()) < 200:
                        try:
                            code2, html2, _, content_hash = await self.fetcher.fetch(
                                url, rate_limit=domain_rate_limit, use_browser=True
                            )
                            if code2 == 200 and html2:
                                title, text, pub_date, meta = (
                                    self.extractor.extract_html(html2, url, selectors)
                                )
                        except Exception as e:
                            logger.debug(
                                "Headless fallback model provider %s: %s", url, e
                            )
                    if not (text or "").strip():
                        logger.info(
                            "[ModelProviders] '%s' URL: empty content — skipped (%s)",
                            name,
                            url[:80],
                        )
                        continue
                    diff_hash = self.detector.content_hash(text)
                    if await self.detector.hash_exists_in_db(diff_hash):
                        logger.info(
                            "[ModelProviders] '%s' URL: content unchanged — skipped (%s)",
                            name,
                            url[:80],
                        )
                        continue
                    summary = await self.summarizer.summarize(
                        title or url,
                        text,
                        url,
                        "release",
                        {"publisher": name, "focus": focus, "model_provider": True},
                        content_hash=diff_hash,
                    )
                    short = (summary.get("summary_short") or title or url).strip()[
                        :1024
                    ]
                    entities = summary.get("entities") or []
                    tags = summary.get("tags") or []
                    raw_meta = dict(meta) if meta else {}
                    if summary.get("evidence") and any(
                        x in (summary.get("evidence") or "").lower()
                        for x in (
                            "sota",
                            "state of the art",
                            "best ",
                            "leading ",
                            "top ",
                        )
                    ):
                        raw_meta["sota_claim"] = True
                    source_cfg_url = prov.get("source_config_url")
                    finding = FindingCreate(
                        title=(title or url)[:512],
                        date_detected=pub_date or since or datetime.now(timezone.utc),
                        source_url=url,
                        publisher=name,
                        category="release",
                        summary_short=short,
                        summary_long=summary.get("summary_long"),
                        why_it_matters=summary.get("why_it_matters"),
                        evidence=summary.get("evidence"),
                        confidence=float(summary.get("confidence", 0.7)),
                        tags=tags,
                        entities=entities,
                        diff_hash=diff_hash,
                        agent_id=self.agent_id,
                        raw_metadata=raw_meta if raw_meta else None,
                        source_config_url=source_cfg_url,
                        raw_content=html,
                        content_type="text/html",
                        extracted_text=text,
                    )
                    findings.append(finding)
                    logger.info(
                        "[ModelProviders] '%s' URL: created finding '%s'",
                        name,
                        (title or url)[:80],
                    )
                except Exception as e:
                    logger.error(
                        "[ModelProviders] '%s' URL FAILED (%s): %s", name, url[:80], e
                    )

        return AgentResult(
            agent_id=self.agent_id,
            findings=findings,
            status="success",
            pages_processed=pages_crawled,
        )

    async def _rss_entry_to_finding(
        self,
        entry: Dict[str, Any],
        publisher: str,
        focus: List[str],
        context: AgentContext,
        prov_config: Dict[str, Any] | None = None,
    ) -> FindingCreate | None:
        link = (entry.get("link") or entry.get("id") or "").strip()
        title = (entry.get("title") or "No title").strip()[:512]
        content = entry.get("content") or entry.get("summary") or ""
        if isinstance(content, list):
            content = content[0].get("value", "") if content else ""
        content = (content or "").strip()
        pub = (
            entry.get("published")
            or context.since_timestamp
            or datetime.now(timezone.utc)
        )
        diff_hash = self.detector.content_hash(content) if content else None
        if diff_hash and await self.detector.hash_exists_in_db(diff_hash):
            logger.debug("Skipping RSS entry %s: content unchanged (hash exists)", link)
            return None
        summary = await self.summarizer.summarize(
            title,
            content or title,
            link,
            "release",
            {"publisher": publisher, "focus": focus, "model_provider": True},
            content_hash=diff_hash,
        )
        short = (summary.get("summary_short") or title).strip()[:1024]
        raw_meta = {
            "title": title,
            "link": link,
            "author": entry.get("author"),
            "published": pub.isoformat() if pub else None,
            "source": "rss",
        }
        if summary.get("evidence") and any(
            x in (summary.get("evidence") or "").lower()
            for x in ("sota", "state of the art", "best ", "leading ", "top ")
        ):
            raw_meta["sota_claim"] = True
        source_cfg_url = (prov_config or {}).get("source_config_url")
        return FindingCreate(
            title=title,
            date_detected=pub,
            source_url=link,
            publisher=publisher,
            category="release",
            summary_short=short,
            summary_long=summary.get("summary_long"),
            why_it_matters=summary.get("why_it_matters"),
            evidence=summary.get("evidence"),
            confidence=float(summary.get("confidence", 0.7)),
            tags=summary.get("tags") or [],
            entities=summary.get("entities") or [],
            diff_hash=diff_hash,
            agent_id=self.agent_id,
            raw_metadata=raw_meta,
            source_config_url=source_cfg_url,
            raw_content=content,
            content_type="application/rss+xml",
            extracted_text=content,
        )
