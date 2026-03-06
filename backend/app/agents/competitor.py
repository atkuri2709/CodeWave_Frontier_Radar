"""Agent #1 — Competitor Release Watcher.

Discovery: RSS preferred → sitemap → crawl list.
Fetch: HTTP first; fallback to headless when content empty/short.
Change detection via content fingerprint; skip re-summarization when unchanged (cache).
Rank by impact: GA, pricing, API, latency, security, compliance.
"""

import logging
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Set, Tuple
from urllib.parse import urlparse

from app.agents.base import AgentContext, AgentResult, BaseAgent
from app.config import get_settings
from app.schemas.finding import FindingCreate
from app.services.change_detector import ChangeDetector
from app.services.extractor import ExtractorService
from app.services.fetcher import FetcherService
from app.services.summarizer import SummarizerService

logger = logging.getLogger(__name__)

# Sitemap indicators: URL is a sitemap (index or urlset) to be fetched for page URLs
SITEMAP_INDICATORS = ("sitemap", ".xml")


def _is_sitemap_url(url: str) -> bool:
    if not url:
        return False
    lower = url.strip().lower()
    return any(ind in lower for ind in SITEMAP_INDICATORS) and (
        ".xml" in lower or "sitemap" in lower
    )


def _domain(url: str) -> str:
    try:
        return urlparse(url).netloc or "unknown"
    except Exception:
        return "unknown"


BROAD_RELEASE_TERMS = [
    "release", "changelog", "update", "announce", "introducing", "launch",
    "new", "model", "api", "feature", "version", "v1", "v2", "beta", "ga",
    "generally available", "preview", "deprecat",
]


def _matches_keywords(text: str, keywords: List[str]) -> bool:
    """True if keywords is empty, or any keyword matches, or any broad release term matches."""
    if not text:
        return False
    if not keywords:
        return True
    lower = text.lower()
    if any((k or "").lower() in lower for k in keywords):
        return True
    return any(term in lower for term in BROAD_RELEASE_TERMS)


def _impact_score_finding(f: FindingCreate) -> float:
    """
    Rank by impact: GA, pricing, API, latency, security, compliance.
    Higher = more impact. Used to sort competitor findings.
    """
    score = 0.0
    combined = " ".join(
        [
            (f.title or ""),
            (f.summary_short or ""),
            (f.summary_long or ""),
            (f.why_it_matters or ""),
            " ".join(f.tags or []),
        ]
    ).lower()
    if re.search(r"\b(ga|general availability|generally available)\b", combined):
        score += 1.0
    if re.search(r"\b(pricing|price|cost|\\$|usd)\b", combined):
        score += 0.9
    if re.search(r"\b(api|sdk|endpoint|rest)\b", combined):
        score += 0.8
    if re.search(r"\b(latency|throughput|performance|speed)\b", combined):
        score += 0.7
    if re.search(r"\b(security|compliance|soc|gdpr|hipaa)\b", combined):
        score += 0.8
    score += f.confidence * 0.3
    return score


class CompetitorAgent(BaseAgent):
    agent_id = "competitors"

    def __init__(self):
        self.fetcher = FetcherService()
        self.extractor = ExtractorService()
        self.detector = ChangeDetector()
        self.summarizer = SummarizerService()
        self.settings = get_settings()

    def _max_pages_per_domain(self, context: AgentContext) -> int:
        """From global config in context or app settings."""
        global_cfg = (context.agent_config or {}).get("global") or {}
        if isinstance(global_cfg, dict):
            v = global_cfg.get("max_pages_per_domain")
            if v is not None and isinstance(v, (int, float)):
                return max(1, int(v))
        return max(1, getattr(self.settings, "max_pages_per_domain", 50))

    async def _discover_urls_from_sitemap(
        self,
        sitemap_url: str,
        rate_limit: float | None,
        max_urls: int,
    ) -> List[str]:
        """Fetch sitemap (or sitemap index) and return page URLs (follow index once)."""
        try:
            code, body, ct, _ = await self.fetcher.fetch(
                sitemap_url, rate_limit=rate_limit
            )
            if code != 200 or not body:
                return []
            urls = self.extractor.parse_sitemap(body)
            if not urls:
                return []
            # If these look like sitemap URLs (index), fetch first few and collect page URLs
            sitemap_like = [u for u in urls if _is_sitemap_url(u)]
            page_urls = [u for u in urls if not _is_sitemap_url(u)]
            for u in sitemap_like[:5]:
                if len(page_urls) >= max_urls:
                    break
                try:
                    c, b, _, _ = await self.fetcher.fetch(u, rate_limit=rate_limit)
                    if c == 200 and b:
                        page_urls.extend(self.extractor.parse_sitemap(b))
                except Exception as e:
                    logger.debug("Sitemap fetch %s failed: %s", u, e)
            return page_urls[:max_urls]
        except Exception as e:
            logger.warning("Sitemap discovery %s failed: %s", sitemap_url, e)
            return []

    async def run(self, context: AgentContext) -> AgentResult:
        findings: List[FindingCreate] = []
        pages_crawled = 0
        config = context.agent_config or {}
        competitors = config.get("competitors") or []
        if not competitors:
            return AgentResult(
                agent_id=self.agent_id, findings=[], status="success", pages_processed=0
            )

        max_per_domain = self._max_pages_per_domain(context)
        since = context.since_timestamp

        for ci, comp in enumerate(competitors):
            name = comp.get("name") or "Unknown"
            release_urls = comp.get("release_urls") or []
            rss_feeds = comp.get("rss_feeds") or []
            logger.info(
                "[Competitors] Processing source %d/%d: '%s' — %d URLs, %d RSS feeds, config_url=%s",
                ci + 1, len(competitors), name, len(release_urls), len(rss_feeds),
                comp.get("source_config_url", "none"),
            )
            keywords = comp.get("keywords")
            if keywords is None:
                keywords = []
            selectors = comp.get("selectors")
            domain_rate_limit = comp.get("domain_rate_limit")
            if domain_rate_limit is not None:
                try:
                    domain_rate_limit = float(domain_rate_limit)
                except (TypeError, ValueError):
                    domain_rate_limit = None

            # --- 1) RSS first: discover entries, filter by since_timestamp ---
            seen_urls: Set[str] = set()
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
                        link = (e.get("link") or e.get("id") or "").strip()
                        if not link or link in seen_urls:
                            continue
                        pub = e.get("published")
                        if since and pub and pub < since:
                            continue
                        seen_urls.add(link)
                        if keywords and not _matches_keywords(
                            (e.get("title") or "")
                            + " "
                            + (e.get("content") or "")
                            + (e.get("summary") or ""),
                            keywords,
                        ):
                            continue
                        try:
                            f = await self._rss_entry_to_finding(e, name, context, comp)
                            if f:
                                findings.append(f)
                        except Exception as e:
                            logger.warning(
                                "RSS entry to finding failed %s: %s", link, e
                            )
                except Exception as e:
                    logger.warning("Competitor RSS %s failed: %s", feed_url, e)

            # --- 2) Sitemap / release_urls: discover page URLs, respect max per domain ---
            domain_counts: Dict[str, int] = {}
            to_fetch: List[Tuple[str, str, Any]] = []  # (url, publisher_name, comp)

            for url in release_urls:
                if not url or not isinstance(url, str):
                    continue
                url = url.strip()
                domain = _domain(url)
                if domain_counts.get(domain, 0) >= max_per_domain:
                    continue
                if _is_sitemap_url(url):
                    discovered = await self._discover_urls_from_sitemap(
                        url,
                        domain_rate_limit,
                        max_per_domain - domain_counts.get(domain, 0),
                    )
                    for u in discovered:
                        d = _domain(u)
                        if domain_counts.get(d, 0) >= max_per_domain:
                            continue
                        if u not in seen_urls:
                            seen_urls.add(u)
                            domain_counts[d] = domain_counts.get(d, 0) + 1
                            to_fetch.append((u, name, comp))
                else:
                    if url in seen_urls:
                        continue
                    seen_urls.add(url)
                    domain_counts[domain] = domain_counts.get(domain, 0) + 1
                    to_fetch.append((url, name, comp))

            logger.info("[Competitors] '%s': %d page URLs to fetch (after discovery)", name, len(to_fetch))
            # --- 3) Fetch each page URL: HTTP then headless fallback, extract, change detect, summarize ---
            for fi, (url, publisher_name, comp_config) in enumerate(to_fetch):
                rate = comp_config.get("domain_rate_limit")
                if rate is not None:
                    try:
                        rate = float(rate)
                    except (TypeError, ValueError):
                        rate = None
                selectors = comp_config.get("selectors")
                keywords_list = comp_config.get("keywords") or []

                try:
                    code, html, _, content_hash = await self.fetcher.fetch(
                        url, rate_limit=rate
                    )
                    pages_crawled += 1
                    if code != 200:
                        logger.info("[Competitors] '%s' URL %d/%d: HTTP %d — skipped", name, fi + 1, len(to_fetch), code)
                        continue
                    title, text, pub_date, meta = self.extractor.extract_html(
                        html, url, selectors
                    )
                    if not (text or "").strip() or len((text or "").strip()) < 200:
                        try:
                            code2, html2, _, content_hash = await self.fetcher.fetch(
                                url, rate_limit=rate, use_browser=True
                            )
                            if code2 == 200 and html2:
                                title, text, pub_date, meta = (
                                    self.extractor.extract_html(html2, url, selectors)
                                )
                        except Exception as e:
                            logger.debug("Headless fallback for %s: %s", url, e)
                    if not (text or "").strip():
                        logger.info("[Competitors] '%s' URL %d/%d: empty content — skipped", name, fi + 1, len(to_fetch))
                        continue
                    if keywords_list and not _matches_keywords(
                        (title or "") + " " + (text or ""), keywords_list
                    ):
                        logger.info("[Competitors] '%s' URL %d/%d: no keyword match — skipped", name, fi + 1, len(to_fetch))
                        continue
                    diff_hash = self.detector.content_hash(text)
                    if await self.detector.hash_exists_in_db(diff_hash):
                        logger.info("[Competitors] '%s' URL %d/%d: content unchanged — skipped", name, fi + 1, len(to_fetch))
                        continue
                    summary = await self.summarizer.summarize(
                        title or url,
                        text,
                        url,
                        "release",
                        {"publisher": publisher_name, "keywords": keywords_list},
                        content_hash=diff_hash,
                    )
                    short = (summary.get("summary_short") or title or url).strip()[:1024]
                    source_cfg_url = comp_config.get("source_config_url")
                    finding = FindingCreate(
                        title=(title or url)[:512],
                        date_detected=pub_date or since or datetime.now(timezone.utc),
                        source_url=url,
                        publisher=publisher_name,
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
                        raw_metadata=meta if meta else None,
                        source_config_url=source_cfg_url,
                        raw_content=html,
                        content_type="text/html",
                        extracted_text=text,
                    )
                    findings.append(finding)
                    logger.info("[Competitors] '%s' URL %d/%d: created finding '%s'", name, fi + 1, len(to_fetch), (title or url)[:80])
                except Exception as e:
                    logger.error("[Competitors] '%s' URL %d/%d FAILED (%s): %s", name, fi + 1, len(to_fetch), url[:80], e)

        # --- 4) Rank by impact (GA, pricing, API, latency, security, compliance) ---
        findings.sort(key=_impact_score_finding, reverse=True)

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
        context: AgentContext,
        comp_config: Dict[str, Any] | None = None,
    ) -> FindingCreate | None:
        """Build a finding from an RSS/Atom entry; use content for diff_hash."""
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
            {"publisher": publisher},
            content_hash=diff_hash,
        )
        short = (summary.get("summary_short") or title).strip()[:1024]
        source_cfg_url = (comp_config or {}).get("source_config_url")
        rss_meta = {
            "title": title, "link": link, "author": entry.get("author"),
            "published": pub.isoformat() if pub else None, "source": "rss",
        }
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
            raw_metadata=rss_meta,
            source_config_url=source_cfg_url,
            raw_content=content,
            content_type="application/rss+xml",
            extracted_text=content,
        )
