"""LLM summarization with structured output (OpenAI, Claude, Grok, or Gemini).

Provider failover: on ANY error (not just 429), try the next provider.
Only fall back to the non-LLM fallback when ALL providers have been exhausted.
"""

import asyncio
import json
import logging
import re
import time
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

import httpx

from app.config import get_settings
from app.services.summary_cache import get_cached, get_cache_key, set_cached

logger = logging.getLogger(__name__)

GEMINI_BASE = "https://generativelanguage.googleapis.com/v1beta"

TIER1_DOMAINS = {
    "openai.com",
    "blog.openai.com",
    "anthropic.com",
    "www.anthropic.com",
    "ai.google",
    "blog.google",
    "deepmind.google",
    "ai.meta.com",
    "engineering.fb.com",
    "microsoft.com",
    "blogs.microsoft.com",
    "azure.microsoft.com",
    "stability.ai",
    "mistral.ai",
    "cohere.com",
    "nvidia.com",
    "developer.nvidia.com",
    "together.ai",
}
TIER2_DOMAINS = {
    "huggingface.co",
    "hf.co",
    "arxiv.org",
    "export.arxiv.org",
    "developers.googleblog.com",
    "aws.amazon.com",
    "cloud.google.com",
}
TIER3_DOMAINS = {
    "techcrunch.com",
    "theverge.com",
    "venturebeat.com",
    "wired.com",
    "arstechnica.com",
    "thenewstack.io",
    "infoworld.com",
    "zdnet.com",
    "reuters.com",
    "github.com",
    "github.blog",
}

_SIGNAL_WEIGHTS = {
    "source_tier": 0.30,
    "content_specificity": 0.25,
    "llm_assessment": 0.30,
    "evidence_quality": 0.15,
}


class ProviderError(Exception):
    """Non-retryable error from an LLM provider (auth, bad request, etc.)."""

    pass


class RateLimitError(Exception):
    """Raised when an LLM provider returns 429 Too Many Requests."""

    pass


_summary_last_call_time: float = 0
_summary_throttle_lock = asyncio.Lock()

_gemini_semaphore: Optional[asyncio.Semaphore] = None
_gemini_last_call_time: float = 0
_gemini_lock = asyncio.Lock()


def _extract_domain(url: str) -> str:
    try:
        return urlparse(url).netloc.lower().removeprefix("www.")
    except Exception:
        return ""


def _source_tier_score(source_url: str) -> float:
    """Rate source authority: Tier 1 official (0.90) > Tier 2 platform (0.72) > Tier 3 media (0.55) > unknown (0.35)."""
    domain = _extract_domain(source_url)
    for d in TIER1_DOMAINS:
        if domain == d or domain.endswith("." + d):
            return 0.90
    for d in TIER2_DOMAINS:
        if domain == d or domain.endswith("." + d):
            return 0.72
    for d in TIER3_DOMAINS:
        if domain == d or domain.endswith("." + d):
            return 0.55
    return 0.35


def _content_specificity_score(text: str) -> float:
    """Detect concrete evidence signals in the text via regex."""
    if not text:
        return 0.15
    lower = text[:8000].lower()
    score = 0.15
    if re.search(
        r"\b(january|february|march|april|may|june|july|august|september|october|november|december)\s+\d{1,2}",
        lower,
    ) or re.search(r"\b20\d{2}[-/]\d{2}", lower):
        score += 0.18
    if re.search(
        r"\bv\d+\.\d+|version\s+\d|gpt-\d|claude[\s-]\d|gemini[\s-]\d|llama[\s-]\d",
        lower,
    ):
        score += 0.18
    if re.search(
        r"\d+\.?\d*\s*%|\b\d{2,}\s*(tokens?|params?|parameters|b\b|m\b|k\b)", lower
    ):
        score += 0.20
    if re.search(
        r"\b(benchmark|accuracy|f1|bleu|rouge|mmlu|hellaswag|humaneval|gsm8k|math-500|gpqa)\b",
        lower,
    ):
        score += 0.15
    if re.search(r"https?://\S{15,}", lower):
        score += 0.07
    return min(1.0, score)


def _evidence_quality_score(evidence: str, text: str) -> float:
    """Check if real evidence was extracted from the content."""
    if not evidence or evidence == "Not stated" or len(evidence.strip()) < 15:
        return 0.25
    if text:
        norm_ev = " ".join(evidence.split()).lower()[:60]
        norm_text = " ".join(text.split()).lower()
        if norm_ev in norm_text:
            return 0.92
    if len(evidence.strip()) > 30:
        return 0.65
    return 0.40


def compute_confidence(
    llm_confidence: float,
    source_url: str,
    text: str,
    evidence: str,
) -> float:
    """Multi-signal confidence score (0.0–1.0). Mirrors real-world intelligence scoring."""
    w = _SIGNAL_WEIGHTS
    s_tier = _source_tier_score(source_url)
    s_content = _content_specificity_score(text)
    s_llm = max(0.0, min(1.0, llm_confidence))
    s_evidence = _evidence_quality_score(evidence, text)

    raw = (
        w["source_tier"] * s_tier
        + w["content_specificity"] * s_content
        + w["llm_assessment"] * s_llm
        + w["evidence_quality"] * s_evidence
    )
    final = round(min(0.95, max(0.10, raw)), 2)

    logger.debug(
        "Confidence breakdown — tier=%.2f content=%.2f llm=%.2f evidence=%.2f → raw=%.3f final=%.2f | %s",
        s_tier,
        s_content,
        s_llm,
        s_evidence,
        raw,
        final,
        source_url[:60],
    )
    return final


def _extract_first_sentence(text: str) -> str:
    """Extract the first meaningful sentence from text as evidence."""
    if not text:
        return "Not stated"
    cleaned = re.sub(r"\s+", " ", text).strip()
    for sep in (". ", ".\n", "! ", "? "):
        idx = cleaned.find(sep)
        if 20 < idx < 300:
            return cleaned[: idx + 1].strip()
    return cleaned[:250].strip() + "..." if len(cleaned) > 250 else cleaned


def _normalize_types(out: Dict[str, Any]) -> Dict[str, Any]:
    """Ensure summary fields have correct types (str not list, float not str)."""
    for key in ("summary_long", "summary_short", "why_it_matters"):
        if isinstance(out.get(key), list):
            out[key] = "\n".join(str(item) for item in out[key])
    if isinstance(out.get("evidence"), list):
        out["evidence"] = "; ".join(str(item) for item in out["evidence"])
    if isinstance(out.get("confidence"), str):
        try:
            out["confidence"] = float(out["confidence"])
        except (ValueError, TypeError):
            out["confidence"] = 0.7
    return out


def _parse_llm_json(raw: str, title: str) -> Dict[str, Any]:
    """Extract and parse JSON from LLM response (handles markdown code blocks)."""
    cleaned = raw.strip()
    if cleaned.startswith("```"):
        parts = cleaned.split("```")
        if len(parts) >= 2:
            inner = parts[1]
            if inner.startswith("json"):
                inner = inner[4:]
            cleaned = inner.strip()

    try:
        out = json.loads(cleaned)
    except json.JSONDecodeError:
        match = re.search(r"\{[\s\S]*\}", cleaned)
        if match:
            out = json.loads(match.group())
        else:
            raise

    out.setdefault("summary_short", title[:400])
    out.setdefault("summary_long", "")
    out.setdefault("why_it_matters", "")
    out.setdefault("evidence", "Not stated")
    out.setdefault("confidence", 0.7)
    out.setdefault("tags", [])
    out.setdefault("entities", [])

    return _normalize_types(out)


class SummarizerService:
    """Summarize extracted text into structured finding fields.

    Tries providers in order. On ANY failure (auth, network, parse, 429-exhausted),
    moves to the next provider. Only uses fallback when ALL providers fail.
    """

    def __init__(self):
        self.settings = get_settings()

    def _openai_client(self):
        key = (self.settings.openai_api_key or "").strip()
        if not key:
            return None
        try:
            from openai import AsyncOpenAI

            if key.startswith("sk-or-"):
                return AsyncOpenAI(
                    base_url="https://openrouter.ai/api/v1",
                    api_key=key,
                )
            return AsyncOpenAI(api_key=key)
        except Exception as e:
            logger.warning("OpenAI client init failed: %s", e)
            return None

    def _claude_client(self):
        if not (self.settings.anthropic_api_key or "").strip():
            return None
        try:
            from anthropic import AsyncAnthropic

            return AsyncAnthropic(api_key=self.settings.anthropic_api_key.strip())
        except Exception as e:
            logger.warning("Anthropic client init failed: %s", e)
            return None

    def _grok_client(self):
        key = getattr(self.settings, "grok_api_key", None)
        if not key or not key.strip():
            return None
        try:
            from openai import AsyncOpenAI

            return AsyncOpenAI(base_url="https://api.x.ai/v1", api_key=key.strip())
        except Exception as e:
            logger.warning("Grok client init failed: %s", e)
            return None

    def _available_providers(self) -> list:
        order = (
            (
                getattr(self.settings, "llm_provider_order", None)
                or "openai,claude,grok,gemini"
            )
            .strip()
            .lower()
        )
        wanted = [p.strip() for p in order.split(",") if p.strip()]
        out = []
        for p in wanted:
            if p == "openai" and (self.settings.openai_api_key or "").strip():
                out.append("openai")
            elif p == "claude" and (self.settings.anthropic_api_key or "").strip():
                out.append("claude")
            elif (
                p == "grok"
                and (getattr(self.settings, "grok_api_key", None) or "").strip()
            ):
                out.append("grok")
            elif p == "gemini" and (self.settings.gemini_api_key or "").strip():
                out.append("gemini")
        return out

    async def _global_throttle(self) -> None:
        global _summary_last_call_time
        delay = getattr(self.settings, "summarization_delay_seconds", 2.0)
        async with _summary_throttle_lock:
            now = time.monotonic()
            wait = _summary_last_call_time + delay - now
            if wait > 0:
                await asyncio.sleep(wait)
            _summary_last_call_time = time.monotonic()

    async def summarize(
        self,
        title: str,
        text: str,
        source_url: str,
        category: str = "release",
        hints: Optional[Dict[str, Any]] = None,
        content_hash: Optional[str] = None,
    ) -> Dict[str, Any]:
        hints = hints or {}
        max_entries = getattr(self.settings, "summary_cache_max_entries", 500)

        cache_key = (
            get_cache_key(source_url, content_hash, "")
            if content_hash
            else get_cache_key(source_url, None, (text or "")[:500])
        )
        cached = get_cached(cache_key) if cache_key else None
        if cached:
            return _normalize_types(cached)

        providers = self._available_providers()
        if not providers:
            logger.warning("No LLM providers configured. Using fallback summarizer.")
            return self._summarize_fallback(title, text, source_url, category)

        last_error: Optional[Exception] = None
        for provider in providers:
            try:
                await self._global_throttle()
                logger.debug("Trying LLM provider: %s", provider)
                out = await self._call_provider(
                    provider, title, text, source_url, category, hints
                )
                out = self._post_process(out, source_url, text)
                if max_entries and cache_key:
                    set_cached(cache_key, out, max_entries=max_entries)
                logger.debug(
                    "LLM provider %s succeeded for %s", provider, source_url[:80]
                )
                return out
            except RateLimitError as e:
                logger.info("Provider %s rate limited, trying next: %s", provider, e)
                last_error = e
                continue
            except Exception as e:
                logger.warning("Provider %s failed, trying next: %s", provider, e)
                last_error = e
                continue

        logger.warning(
            "All LLM providers failed. Last error: %s. Using fallback.", last_error
        )
        return self._summarize_fallback(title, text, source_url, category)

    async def _call_provider(
        self,
        provider: str,
        title: str,
        text: str,
        source_url: str,
        category: str,
        hints: Dict[str, Any],
    ) -> Dict[str, Any]:
        if provider == "openai":
            return await self._summarize_openai(
                title, text, source_url, category, hints
            )
        elif provider == "claude":
            return await self._summarize_claude(
                title, text, source_url, category, hints
            )
        elif provider == "grok":
            return await self._summarize_grok(title, text, source_url, category, hints)
        elif provider == "gemini":
            return await self._summarize_gemini(
                title, text, source_url, category, hints
            )
        raise ProviderError(f"Unknown provider: {provider}")

    def _post_process(
        self, out: Dict[str, Any], source_url: str, text: str
    ) -> Dict[str, Any]:
        """Compute multi-signal confidence and validate evidence."""
        evidence = out.get("evidence", "")
        if not evidence or evidence == "Not stated" or len(evidence.strip()) < 10:
            out["evidence"] = _extract_first_sentence(text)
        elif text:
            normalized_text = " ".join(text.split()).lower()
            normalized_evidence = " ".join(evidence.split()).lower()
            if (
                len(normalized_evidence) > 20
                and normalized_evidence[:40] not in normalized_text
            ):
                real_evidence = _extract_first_sentence(text)
                if real_evidence and real_evidence != "Not stated":
                    out["evidence"] = real_evidence

        if isinstance(out.get("evidence"), list):
            out["evidence"] = "; ".join(str(e) for e in out["evidence"])

        llm_conf = float(out.get("confidence", 0.5))
        out["confidence"] = compute_confidence(
            llm_confidence=llm_conf,
            source_url=source_url,
            text=text or "",
            evidence=str(out.get("evidence", "")),
        )

        return out

    def _prompt(
        self,
        title: str,
        text: str,
        source_url: str,
        category: str,
        hints: Optional[Dict[str, Any]] = None,
    ) -> str:
        hints = hints or {}

        focus_section = ""
        if hints.get("model_provider"):
            focus_section = (
                "\nThis is a foundation model provider update. Focus on extracting:\n"
                "- Model name/version, modalities, context length\n"
                "- Tool use / agents features\n"
                "- Pricing / quotas changes\n"
                "- Safety policy changes\n"
                "- Benchmarks claimed (with citations)\n"
            )
        elif hints.get("benchmark"):
            output_focus = hints.get("output_focus", "")
            focus_section = (
                "\nThis is a benchmark/leaderboard update. Focus on extracting:\n"
                "- Who moved up/down on the leaderboard\n"
                "- Which tasks improved\n"
                "- Model family trends (small models catching up, multimodal jumps)\n"
                "- Reproducibility notes (if metadata available)\n"
                "- Caveats (leaderboard bias, different eval settings)\n"
            )
            if output_focus:
                focus_section += f"- Additional focus: {output_focus}\n"
        elif category == "research":
            focus_section = (
                "\nThis is a research publication. Focus on extracting:\n"
                "- Core contribution (1-2 sentences)\n"
                "- What's new vs prior work\n"
                "- Practical implications (eval, data, training, inference, agents)\n"
                "- Relevance to: benchmarks/eval, data-centric, agentic, multimodal, safety/alignment\n"
            )

        focus_keywords = hints.get("focus") or hints.get("relevance_keywords") or []
        if focus_keywords and isinstance(focus_keywords, list):
            focus_section += f"\nKey topics to watch for: {', '.join(str(k) for k in focus_keywords)}\n"

        publisher = hints.get("publisher")
        publisher_line = f"\nPublisher: {publisher}" if publisher else ""

        return f"""Summarize this content for a daily AI/ML intelligence digest. Highlight only the most important updates, key facts, and strategic insights.

Title: {title}
Source: {source_url}
Category: {category}{publisher_line}
{focus_section}
Content (excerpt):
{text[:12000]}

Return ONLY a valid JSON object with exactly these keys (no extra text, no markdown):
{{
  "summary_short": "2-4 sentence summary (up to 150 words) describing what changed and key facts",
  "summary_long": "detailed bullet points covering all important changes, features, numbers, dates, model names, benchmarks, and technical details. Be comprehensive — include every notable fact from the content.",
  "why_it_matters": "3-5 sentences explaining the business and technical impact: who is affected, what should teams do, how this changes the competitive landscape",
  "evidence": "1-3 directly quoted sentences from the content above that support the summary",
  "confidence": <float 0-1 — your assessment of content quality only, see rules>,
  "tags": ["tag1", "tag2", "tag3"],
  "entities": ["company or model names mentioned"]
}}

Rules for confidence (rate the CONTENT QUALITY only — source authority is scored separately):
- 0.80-0.90 = every claim backed by hard numbers, benchmarks, dates, and reproducible evidence
- 0.65-0.79 = clear factual claims with some details, but not all verifiable in the text
- 0.50-0.64 = useful information but vague, marketing-heavy, or missing specifics
- 0.35-0.49 = thin content, mostly opinion, aggregated from elsewhere
- 0.20-0.34 = speculation, rumor, or unverifiable
- Below 0.20 = contradicted or clearly unreliable
Be strict. Most content should score 0.55-0.75.

Rules for evidence:
- MUST be a direct quote from the content above
- If no clear quote exists, use the most specific factual sentence
"""

    def _429_backoff(self, attempt: int) -> float:
        base = getattr(self.settings, "summarization_429_base_seconds", 2.0)
        return min(60.0, max(1.0, base**attempt))

    async def _summarize_openai(
        self,
        title: str,
        text: str,
        source_url: str,
        category: str,
        hints: Dict[str, Any],
    ) -> Dict[str, Any]:
        client = self._openai_client()
        if not client:
            raise ProviderError("OpenAI client unavailable")
        prompt = self._prompt(title, text, source_url, category, hints)
        max_retries = getattr(self.settings, "summarization_429_max_retries", 5)
        for attempt in range(max_retries + 1):
            try:
                resp = await client.chat.completions.create(
                    model=self.settings.openai_model,
                    messages=[{"role": "user", "content": prompt}],
                    max_tokens=self.settings.summarization_max_tokens,
                    temperature=0.2,
                )
                raw = resp.choices[0].message.content or ""
                return _parse_llm_json(raw, title)
            except Exception as e:
                err_str = str(e).lower()
                if (
                    "429" in err_str
                    or "rate" in err_str
                    or "too many requests" in err_str
                ):
                    if attempt < max_retries:
                        wait = self._429_backoff(attempt)
                        logger.info(
                            "OpenAI 429, retry in %.1fs (attempt %d/%d)",
                            wait,
                            attempt + 1,
                            max_retries,
                        )
                        await asyncio.sleep(wait)
                        continue
                    raise RateLimitError(
                        f"OpenAI rate limited after {max_retries} retries"
                    ) from e
                raise ProviderError(f"OpenAI failed: {e}") from e
        raise ProviderError("OpenAI: max retries exhausted")

    async def _summarize_claude(
        self,
        title: str,
        text: str,
        source_url: str,
        category: str,
        hints: Dict[str, Any],
    ) -> Dict[str, Any]:
        client = self._claude_client()
        if not client:
            raise ProviderError("Claude client unavailable")
        prompt = self._prompt(title, text, source_url, category, hints)
        max_retries = getattr(self.settings, "summarization_429_max_retries", 5)
        for attempt in range(max_retries + 1):
            try:
                resp = await client.messages.create(
                    model=self.settings.anthropic_model,
                    max_tokens=self.settings.summarization_max_tokens,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.2,
                )
                raw = resp.content[0].text if resp.content else ""
                return _parse_llm_json(raw, title)
            except Exception as e:
                err_str = str(e).lower()
                if (
                    "429" in err_str
                    or "rate" in err_str
                    or "too many requests" in err_str
                ):
                    if attempt < max_retries:
                        wait = self._429_backoff(attempt)
                        logger.info(
                            "Claude 429, retry in %.1fs (attempt %d/%d)",
                            wait,
                            attempt + 1,
                            max_retries,
                        )
                        await asyncio.sleep(wait)
                        continue
                    raise RateLimitError(
                        f"Claude rate limited after {max_retries} retries"
                    ) from e
                raise ProviderError(f"Claude failed: {e}") from e
        raise ProviderError("Claude: max retries exhausted")

    async def _summarize_grok(
        self,
        title: str,
        text: str,
        source_url: str,
        category: str,
        hints: Dict[str, Any],
    ) -> Dict[str, Any]:
        client = self._grok_client()
        if not client:
            raise ProviderError("Grok client unavailable")
        prompt = self._prompt(title, text, source_url, category, hints)
        model = getattr(self.settings, "grok_model", "grok-2-1212")
        max_retries = getattr(self.settings, "summarization_429_max_retries", 5)
        for attempt in range(max_retries + 1):
            try:
                resp = await client.chat.completions.create(
                    model=model,
                    messages=[{"role": "user", "content": prompt}],
                    max_tokens=self.settings.summarization_max_tokens,
                    temperature=0.2,
                )
                raw = resp.choices[0].message.content or ""
                return _parse_llm_json(raw, title)
            except Exception as e:
                err_str = str(e).lower()
                if (
                    "429" in err_str
                    or "rate" in err_str
                    or "too many requests" in err_str
                ):
                    if attempt < max_retries:
                        wait = self._429_backoff(attempt)
                        logger.info(
                            "Grok 429, retry in %.1fs (attempt %d/%d)",
                            wait,
                            attempt + 1,
                            max_retries,
                        )
                        await asyncio.sleep(wait)
                        continue
                    raise RateLimitError(
                        f"Grok rate limited after {max_retries} retries"
                    ) from e
                raise ProviderError(f"Grok failed: {e}") from e
        raise ProviderError("Grok: max retries exhausted")

    async def _gemini_rate_limit(self) -> None:
        global _gemini_semaphore, _gemini_last_call_time
        if _gemini_semaphore is None:
            async with _gemini_lock:
                if _gemini_semaphore is None:
                    n = max(1, getattr(self.settings, "gemini_max_concurrent", 1))
                    _gemini_semaphore = asyncio.Semaphore(n)
        delay = getattr(self.settings, "gemini_rate_limit_delay_seconds", 5.0)
        async with _gemini_semaphore:
            async with _gemini_lock:
                now = time.monotonic()
                wait = _gemini_last_call_time + delay - now
                if wait > 0:
                    await asyncio.sleep(wait)
                _gemini_last_call_time = time.monotonic()

    async def _summarize_gemini(
        self,
        title: str,
        text: str,
        source_url: str,
        category: str,
        hints: Dict[str, Any],
    ) -> Dict[str, Any]:
        key = (self.settings.gemini_api_key or "").strip()
        if not key:
            raise ProviderError("Gemini API key missing")
        await self._gemini_rate_limit()
        prompt = self._prompt(title, text, source_url, category, hints)
        models_to_try = [
            self.settings.gemini_model or "gemini-2.0-flash",
            "gemini-2.0-flash",
            "gemini-1.5-flash",
        ]
        seen = set()
        last_error: Optional[Exception] = None
        for model in models_to_try:
            if model in seen:
                continue
            seen.add(model)
            url = f"{GEMINI_BASE}/models/{model}:generateContent"
            params = {"key": key}
            payload = {
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {
                    "maxOutputTokens": self.settings.summarization_max_tokens,
                    "temperature": 0.2,
                },
            }
            max_retries = getattr(self.settings, "summarization_429_max_retries", 5)
            for attempt in range(max_retries + 1):
                try:
                    async with httpx.AsyncClient(timeout=60) as client:
                        resp = await client.post(url, params=params, json=payload)
                    global _gemini_last_call_time
                    async with _gemini_lock:
                        _gemini_last_call_time = time.monotonic()
                    if resp.status_code == 429:
                        if attempt < max_retries:
                            wait = self._429_backoff(attempt)
                            logger.info(
                                "Gemini 429, retry in %.1fs (attempt %d/%d)",
                                wait,
                                attempt + 1,
                                max_retries,
                            )
                            await asyncio.sleep(wait)
                            continue
                        raise RateLimitError("Gemini rate limited after retries")
                    if resp.status_code == 404:
                        logger.debug("Gemini model %s not found, trying next", model)
                        break
                    resp.raise_for_status()
                    data = resp.json()
                    candidates = data.get("candidates") or []
                    if not candidates:
                        raise ProviderError("No candidates in Gemini response")
                    parts = candidates[0].get("content", {}).get("parts") or []
                    raw = parts[0].get("text", "") if parts else ""
                    return _parse_llm_json(raw, title)
                except RateLimitError:
                    raise
                except httpx.HTTPStatusError as e:
                    last_error = e
                    if e.response.status_code == 429:
                        raise RateLimitError("Gemini 429") from e
                    break
                except Exception as e:
                    last_error = e
                    break
        raise ProviderError(f"Gemini failed: {last_error}") from last_error

    def _summarize_fallback(
        self, title: str, text: str, source_url: str, category: str
    ) -> Dict[str, Any]:
        """Non-LLM fallback. Extracts real data from text — no hardcoded placeholders."""
        cleaned = re.sub(r"\s+", " ", (text or "")).strip()
        excerpt = cleaned[:2000]
        lower = cleaned.lower()

        evidence = _extract_first_sentence(text)

        confidence = compute_confidence(
            llm_confidence=0.45,
            source_url=source_url,
            text=cleaned,
            evidence=evidence,
        )

        entities: List[str] = []
        for ent in [
            "OpenAI",
            "Google",
            "Meta",
            "Anthropic",
            "Microsoft",
            "Mistral",
            "Hugging Face",
            "NVIDIA",
            "Cohere",
            "Stability AI",
            "DeepMind",
            "GPT",
            "Claude",
            "Gemini",
            "Llama",
            "Mixtral",
            "Amazon",
            "AWS",
        ]:
            if ent.lower() in lower:
                entities.append(ent)

        tags: List[str] = [category]
        tag_patterns = {
            "api": r"\bapi\b",
            "pricing": r"\bpric",
            "safety": r"\bsafety\b",
            "benchmark": r"\bbenchmark",
            "multimodal": r"\bmultimodal",
            "agents": r"\bagent",
            "training": r"\btraining\b",
            "inference": r"\binference\b",
            "open-source": r"\bopen.?source\b",
        }
        for tag, pattern in tag_patterns.items():
            if re.search(pattern, lower) and tag not in tags:
                tags.append(tag)

        domain = _extract_domain(source_url) or "source"
        entity_str = f" involving {', '.join(entities[:3])}" if entities else ""
        why = f"New {category} update from {domain}{entity_str}."
        if any(
            re.search(p, lower)
            for p in [r"\bga\b", r"\bgeneral avail", r"\blaunch", r"\breleased?\b"]
        ):
            why += " Involves a product launch or GA release — may affect competitive positioning."
        elif re.search(r"\bbenchmark|\bleaderboard|\bsota\b", lower):
            why += " Contains benchmark or leaderboard data — may shift model rankings."
        elif re.search(r"\bresearch|\bpaper|\barxiv\b", lower):
            why += " New research publication — review for methodological advances."
        else:
            why += " Review for strategic or technical relevance."

        return {
            "summary_short": (
                (title + ". " + excerpt[: max(0, 900 - len(title))]).strip()
                if excerpt
                else title
            ),
            "summary_long": excerpt[:2000] if excerpt else title,
            "why_it_matters": why,
            "evidence": evidence,
            "confidence": confidence,
            "tags": tags[:15],
            "entities": entities[:15],
        }
