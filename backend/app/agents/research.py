"""Agent #3 — Research Publication Scout.

Track latest publications on LLMs/foundation models. Configurable: arXiv categories,
Semantic Scholar, OpenReview, curated lab blogs. Output: core contribution,
what's new vs prior work, practical implications. Relevance scoring for
benchmarks/eval, data-centric, agentic, multimodal, safety/alignment.
"""

import logging
import re
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from typing import Any, List

import httpx

from app.agents.base import AgentContext, AgentResult, BaseAgent
from app.schemas.finding import FindingCreate
from app.services.change_detector import ChangeDetector
from app.services.extractor import ExtractorService
from app.services.fetcher import FetcherService
from app.services.summarizer import SummarizerService

logger = logging.getLogger(__name__)


def _relevance_score(text: str) -> float:
    """
    Score papers higher for: benchmarks/eval, data-centric, agentic, multimodal, safety.
    Used to rank research findings. No hardcoded list—pattern-based.
    """
    if not text:
        return 0.0
    lower = text.lower()
    score = 0.0
    if re.search(r"\b(benchmark|eval(uation)?|metric|leaderboard)\b", lower):
        score += 1.0
    if re.search(
        r"\b(data-centric|curation|synthetic|preference learning|rlhf|dpo)\b", lower
    ):
        score += 0.9
    if re.search(r"\b(agent(ic)?|tool use|memory|workflow)\b", lower):
        score += 0.85
    if re.search(r"\b(multimodal|video|vision|robotics|physical)\b", lower):
        score += 0.85
    if re.search(r"\b(safety|alignment|red-?team|policy|compliance)\b", lower):
        score += 0.9
    return score


def _matches_keywords(text: str, keywords: List[str]) -> bool:
    """True if keywords is empty or at least one keyword appears in text (case-insensitive)."""
    if not text:
        return False
    if not keywords:
        return True
    lower = text.lower()
    return any((k or "").lower() in lower for k in keywords)


class ResearchAgent(BaseAgent):
    agent_id = "research"

    def __init__(self):
        self.fetcher = FetcherService()
        self.extractor = ExtractorService()
        self.detector = ChangeDetector()
        self.summarizer = SummarizerService()

    async def run(self, context: AgentContext) -> AgentResult:
        findings: List[FindingCreate] = []
        pages_crawled = 0
        config = context.agent_config or {}
        research_cfg = config.get("research")
        if not isinstance(research_cfg, dict):
            research_cfg = {}
        curated_urls = research_cfg.get("curated_urls") or []
        relevance_keywords = research_cfg.get("relevance_keywords")
        if relevance_keywords is None:
            relevance_keywords = []
        if not isinstance(relevance_keywords, list):
            relevance_keywords = []

        since = context.since_timestamp

        # arXiv: only when not disabled by config
        if not research_cfg.get("disable_arxiv", False):
            arxiv_cats = research_cfg.get("arxiv_categories") or []
            if arxiv_cats:
                try:
                    arxiv_findings = await self._fetch_arxiv(
                        arxiv_cats, relevance_keywords, context
                    )
                    findings.extend(arxiv_findings)
                    pages_crawled += 1
                except Exception as e:
                    logger.warning("arXiv fetch failed: %s", e)

        logger.info(
            "[Research] %d curated URLs to process, arxiv=%s",
            len(curated_urls),
            "enabled" if not research_cfg.get("disable_arxiv", False) else "disabled",
        )
        # Curated URLs (lab blogs, etc.)
        for ui, url in enumerate(curated_urls):
            if not url or not isinstance(url, str):
                continue
            url = url.strip()
            try:
                code, html, _, _ = await self.fetcher.fetch(url)
                pages_crawled += 1
                if code != 200:
                    continue
                title, text, pub_date, meta = self.extractor.extract_html(html, url)
                if not (text or "").strip():
                    try:
                        code2, html2, _, _ = await self.fetcher.fetch(
                            url, use_browser=True
                        )
                        if code2 == 200 and html2:
                            title, text, pub_date, meta = self.extractor.extract_html(
                                html2, url
                            )
                    except Exception:
                        pass
                if not (text or "").strip():
                    continue
                if relevance_keywords and not _matches_keywords(
                    (title or "") + " " + (text or ""), relevance_keywords
                ):
                    continue
                diff_hash = self.detector.content_hash(text)
                if await self.detector.hash_exists_in_db(diff_hash):
                    logger.debug("Skipping %s: content unchanged", url)
                    continue
                summary = await self.summarizer.summarize(
                    title or url,
                    text,
                    url,
                    "research",
                    {"relevance_keywords": relevance_keywords},
                    content_hash=diff_hash,
                )
                short = (summary.get("summary_short") or title or url).strip()[:1024]
                findings.append(
                    FindingCreate(
                        title=(title or url)[:512],
                        date_detected=pub_date or since or datetime.now(timezone.utc),
                        source_url=url,
                        publisher=None,
                        category="research",
                        summary_short=short,
                        summary_long=summary.get("summary_long"),
                        why_it_matters=summary.get("why_it_matters"),
                        evidence=summary.get("evidence"),
                        confidence=float(summary.get("confidence", 0.6)),
                        tags=summary.get("tags") or [],
                        entities=summary.get("entities") or [],
                        diff_hash=diff_hash,
                        agent_id=self.agent_id,
                        raw_metadata=meta if meta else None,
                        source_config_url=url,
                        raw_content=html,
                        content_type="text/html",
                        extracted_text=text,
                    )
                )
                logger.info(
                    "[Research] URL %d/%d: created finding '%s'",
                    ui + 1,
                    len(curated_urls),
                    (title or url)[:80],
                )
            except Exception as e:
                logger.error(
                    "[Research] URL %d/%d FAILED (%s): %s",
                    ui + 1,
                    len(curated_urls),
                    url[:80],
                    e,
                )

        # Rank by relevance (benchmarks, eval, data-centric, agentic, multimodal, safety)
        findings.sort(
            key=lambda f: _relevance_score(
                (f.title or "")
                + " "
                + (f.summary_short or "")
                + " "
                + (f.summary_long or "")
                + " "
                + " ".join(f.tags or [])
            ),
            reverse=True,
        )

        return AgentResult(
            agent_id=self.agent_id,
            findings=findings,
            status="success",
            pages_processed=pages_crawled,
        )

    async def _fetch_arxiv(
        self,
        categories: List[str],
        relevance_keywords: List[str],
        context: AgentContext,
    ) -> List[FindingCreate]:
        """Query arXiv API; include papers matching relevance_keywords (or all if empty)."""
        findings: List[FindingCreate] = []
        query = " OR ".join(f"cat:{c}" for c in categories[:5])
        params = {
            "search_query": query,
            "sortBy": "submittedDate",
            "sortOrder": "descending",
            "max_results": 50,
        }
        async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
            resp = await client.get("https://export.arxiv.org/api/query", params=params)
            resp.raise_for_status()
            xml_text = resp.text
        ns = "http://www.w3.org/2005/Atom"
        root = ET.fromstring(xml_text)
        for entry in root.findall(f".//{{{ns}}}entry"):
            title_el = entry.find(f"{{{ns}}}title")
            link_el = entry.find(f"{{{ns}}}link")
            summary_el = entry.find(f"{{{ns}}}summary")
            published_el = entry.find(f"{{{ns}}}published")
            title = (
                title_el.text.strip().replace("\n", " ")
                if title_el is not None and title_el.text
                else "No title"
            )
            link = (link_el.get("href") or "") if link_el is not None else ""
            summary = (
                summary_el.text.strip().replace("\n", " ")
                if summary_el is not None and summary_el.text
                else ""
            )
            combined = f"{title} {summary}"
            if relevance_keywords and not _matches_keywords(
                combined, relevance_keywords
            ):
                continue
            pub_str = (
                published_el.text
                if published_el is not None and published_el.text
                else ""
            )
            try:
                pub = (
                    datetime.fromisoformat(pub_str.replace("Z", "+00:00"))
                    if pub_str
                    else datetime.now(timezone.utc)
                )
            except Exception:
                pub = datetime.now(timezone.utc)
            diff_hash = self.detector.content_hash(combined) if combined else None
            if diff_hash and await self.detector.hash_exists_in_db(diff_hash):
                continue
            sum_out = await self.summarizer.summarize(
                title,
                summary,
                link,
                "research",
                {"relevance_keywords": relevance_keywords},
                content_hash=diff_hash,
            )
            short = (sum_out.get("summary_short") or title).strip()[:1024]
            arxiv_meta = {
                "title": title,
                "link": link,
                "source": "arxiv",
                "published": pub.isoformat() if pub else None,
                "abstract": summary[:500] if summary else None,
            }
            findings.append(
                FindingCreate(
                    title=title[:512],
                    date_detected=pub,
                    source_url=link,
                    publisher="arXiv",
                    category="research",
                    summary_short=short,
                    summary_long=sum_out.get("summary_long"),
                    why_it_matters=sum_out.get("why_it_matters"),
                    evidence=sum_out.get("evidence"),
                    confidence=float(sum_out.get("confidence", 0.7)),
                    tags=sum_out.get("tags") or [],
                    entities=sum_out.get("entities") or [],
                    diff_hash=diff_hash,
                    agent_id=self.agent_id,
                    raw_metadata=arxiv_meta,
                    source_config_url=link,
                    raw_content=combined,
                    content_type="application/xml",
                    extracted_text=summary,
                )
            )
            if len(findings) >= 20:
                break
        return findings
