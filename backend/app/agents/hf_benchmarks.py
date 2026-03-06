"""Agent #4 — Hugging Face Benchmark & Leaderboard Tracker.

Monitor configurable leaderboard URLs for benchmarking results and trends.
Output: who moved up/down, which tasks improved, model family trends,
reproducibility notes, caveats (bias, eval settings). Prefer APIs when
configured; fallback to HTML parsing. No hardcoded URLs—all from config.
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

KNOWN_LEADERBOARDS: Dict[str, str] = {
    "open_llm_leaderboard": "https://huggingface.co/spaces/open-llm-leaderboard/open_llm_leaderboard",
    "open_vlm_leaderboard": "https://huggingface.co/spaces/opencompass/open_vlm_leaderboard",
    "chatbot_arena": "https://huggingface.co/spaces/lmsys/chatbot-arena-leaderboard",
    "bigcode_leaderboard": "https://huggingface.co/spaces/bigcode/bigcode-models-leaderboard",
    "hallucinations_leaderboard": "https://huggingface.co/spaces/hallucinations-leaderboard/leaderboard",
}


class HFBenchmarksAgent(BaseAgent):
    agent_id = "hf_benchmarks"

    def __init__(self):
        self.fetcher = FetcherService()
        self.extractor = ExtractorService()
        self.detector = ChangeDetector()
        self.summarizer = SummarizerService()

    async def run(self, context: AgentContext) -> AgentResult:
        findings: List[FindingCreate] = []
        pages_crawled = 0
        config = context.agent_config or {}
        hf_cfg = config.get("hf_benchmarks")
        if not isinstance(hf_cfg, dict):
            hf_cfg = {}
        leaderboard_urls = hf_cfg.get("leaderboard_urls") or []
        leaderboards = hf_cfg.get("leaderboards") or []
        tasks = hf_cfg.get("tasks") or []
        track_new_sota = hf_cfg.get("track_new_sota", True)

        urls_to_fetch: List[str] = []
        for u in leaderboard_urls:
            if u and isinstance(u, str) and u.strip().startswith("http"):
                urls_to_fetch.append(u.strip())
        for x in leaderboards:
            if not x or not isinstance(x, str):
                continue
            x = x.strip()
            if x.startswith("http"):
                if x not in urls_to_fetch:
                    urls_to_fetch.append(x)
            elif x.lower() in KNOWN_LEADERBOARDS:
                resolved = KNOWN_LEADERBOARDS[x.lower()]
                if resolved not in urls_to_fetch:
                    urls_to_fetch.append(resolved)

        if not urls_to_fetch:
            return AgentResult(
                agent_id=self.agent_id, findings=[], status="success", pages_processed=0
            )

        since = context.since_timestamp

        logger.info("[HFBenchmarks] %d leaderboard URLs to process", len(urls_to_fetch))
        for ui, url in enumerate(urls_to_fetch):
            try:
                code, html, _, _ = await self.fetcher.fetch(url)
                pages_crawled += 1
                if code != 200:
                    continue
                title, text, pub_date, meta = self.extractor.extract_html(html, url)
                if not (text or "").strip() or len((text or "").strip()) < 150:
                    try:
                        code2, html2, _, _ = await self.fetcher.fetch(
                            url, use_browser=True
                        )
                        if code2 == 200 and html2:
                            title, text, pub_date, meta = self.extractor.extract_html(
                                html2, url
                            )
                    except Exception as e:
                        logger.debug("HF headless fallback %s: %s", url, e)
                if not (text or "").strip():
                    continue
                diff_hash = self.detector.content_hash(text)
                if await self.detector.hash_exists_in_db(diff_hash):
                    logger.debug("Skipping %s: content unchanged", url)
                    continue
                hints: Dict[str, Any] = {
                    "benchmark": True,
                    "publisher": "Hugging Face",
                    "track_sota": track_new_sota,
                    "tasks": tasks,
                    "output_focus": "who moved up/down, which tasks improved, model family trends, reproducibility notes, caveats (leaderboard bias, different eval settings)",
                }
                summary = await self.summarizer.summarize(
                    title or "Leaderboard",
                    text[:8000],
                    url,
                    "benchmark",
                    hints,
                    content_hash=diff_hash,
                )
                short = (
                    summary.get("summary_short")
                    or title
                    or "Hugging Face leaderboard update"
                ).strip()[:1024]
                finding = FindingCreate(
                    title=(title or "Hugging Face Leaderboard")[:512],
                    date_detected=pub_date or since or datetime.now(timezone.utc),
                    source_url=url,
                    publisher="Hugging Face",
                    category="benchmark",
                    summary_short=short,
                    summary_long=summary.get("summary_long"),
                    why_it_matters=summary.get("why_it_matters"),
                    evidence=summary.get("evidence"),
                    confidence=float(summary.get("confidence", 0.75)),
                    tags=summary.get("tags") or ["benchmark", "leaderboard"],
                    entities=summary.get("entities") or [],
                    diff_hash=diff_hash,
                    agent_id=self.agent_id,
                    raw_metadata=meta if meta else None,
                    source_config_url=url,
                    raw_content=html,
                    content_type="text/html",
                    extracted_text=text,
                )
                findings.append(finding)
                logger.info("[HFBenchmarks] URL %d/%d: created finding '%s'", ui + 1, len(urls_to_fetch), (title or url)[:80])
            except Exception as e:
                logger.error("[HFBenchmarks] URL %d/%d FAILED (%s): %s", ui + 1, len(urls_to_fetch), url[:80], e)

        return AgentResult(
            agent_id=self.agent_id,
            findings=findings,
            status="success",
            pages_processed=pages_crawled,
        )
