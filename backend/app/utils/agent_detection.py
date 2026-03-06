"""Automatic agent detection based on source URL.

Uses domain matching first, then keyword fallback. Defaults to 'competitors'.
"""

import logging
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

# Domain fragments → agent_id. Checked via `in` against the parsed hostname.
AGENT_DOMAIN_MAP: dict[str, list[str]] = {
    "hf_benchmarks": [
        "huggingface.co",
    ],
    "research": [
        "arxiv.org",
        "openreview.net",
        "semanticscholar.org",
        "aclweb.org",
        "paperswithcode.com",
    ],
    "model_providers": [
        "openai.com",
        "anthropic.com",
        "deepmind.google",
        "ai.google",
        "ai.meta.com",
        "cloud.google.com/vertex-ai",
        "aws.amazon.com/bedrock",
    ],
    "competitors": [
        "mistral.ai",
        "cohere.com",
        "together.ai",
        "perplexity.ai",
        "stability.ai",
        "aleph-alpha.com",
    ],
}

BENCHMARK_KEYWORDS = ["leaderboard", "benchmark", "evaluation", "ranking", "sota"]
RESEARCH_KEYWORDS = ["paper", "arxiv", "dataset", "survey", "transformer", "attention"]
MODEL_KEYWORDS = ["model", "gpt", "llm", "release", "api", "claude", "gemini"]


def extract_domain(url: str) -> str:
    """Extract the hostname from a URL, stripping 'www.' prefix."""
    try:
        host = urlparse(url).hostname or ""
        return host.lower().removeprefix("www.")
    except Exception:
        return ""


def detect_agent_by_domain(url: str) -> str | None:
    """Match URL domain against known domain fragments. Returns agent_id or None."""
    domain = extract_domain(url)
    full_url_lower = url.lower()
    if not domain:
        return None
    for agent_id, domains in AGENT_DOMAIN_MAP.items():
        for d in domains:
            if d in domain or d in full_url_lower:
                return agent_id
    return None


def detect_agent_by_keywords(url: str) -> str | None:
    """Fallback: scan the URL path/query for keywords. Returns agent_id or None."""
    low = url.lower()
    if any(kw in low for kw in BENCHMARK_KEYWORDS):
        return "hf_benchmarks"
    if any(kw in low for kw in RESEARCH_KEYWORDS):
        return "research"
    if any(kw in low for kw in MODEL_KEYWORDS):
        return "model_providers"
    return None


def detect_agent(url: str) -> str:
    """Detect the best agent for a URL. Domain rules first, keyword fallback, then 'competitors'."""
    agent = detect_agent_by_domain(url)
    if agent:
        logger.info("Agent detection (domain): %s → %s", url, agent)
        return agent
    agent = detect_agent_by_keywords(url)
    if agent:
        logger.info("Agent detection (keyword): %s → %s", url, agent)
        return agent
    logger.info("Agent detection (default): %s → competitors", url)
    return "competitors"
