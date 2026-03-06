"""Analytics aggregation service for SOTA Watch and Entity Heatmap.

Provides fast, pre-aggregated data structures that the analytics API
endpoints return directly to the frontend.
"""

import logging
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Finding
from app.utils.entity_normalizer import normalize_entity

logger = logging.getLogger(__name__)

HEATMAP_TOPICS = [
    "models",
    "research",
    "benchmarks",
    "pricing",
    "safety",
    "tooling",
]

_TOPIC_KEYWORDS: dict[str, list[str]] = {
    "models": [
        "model", "llm", "gpt", "claude", "gemini", "llama", "mistral",
        "foundation model", "language model", "multimodal", "vision",
        "embedding", "fine-tune", "training", "weights", "parameters",
    ],
    "research": [
        "research", "paper", "arxiv", "study", "publication", "findings",
        "experiment", "methodology", "novel", "approach", "technique",
    ],
    "benchmarks": [
        "benchmark", "leaderboard", "evaluation", "score", "ranking",
        "performance", "accuracy", "sota", "state-of-the-art", "mmlu",
        "hellaswag", "humaneval", "gsm8k", "math", "arena",
    ],
    "pricing": [
        "pricing", "cost", "price", "token", "api pricing", "subscription",
        "free tier", "enterprise", "billing", "rate limit",
    ],
    "safety": [
        "safety", "alignment", "guardrail", "red team", "jailbreak",
        "responsible", "ethics", "bias", "toxicity", "moderation",
        "content filter", "harm", "risk",
    ],
    "tooling": [
        "tool", "api", "sdk", "plugin", "integration", "framework",
        "library", "platform", "developer", "agent", "function calling",
        "rag", "retrieval", "deployment", "inference",
    ],
}


def _classify_topics(text: str, tags: list[str]) -> list[str]:
    """Determine which topics a finding is relevant to."""
    lower = (text + " " + " ".join(tags)).lower()
    matched = []
    for topic, keywords in _TOPIC_KEYWORDS.items():
        if any(kw in lower for kw in keywords):
            matched.append(topic)
    return matched if matched else ["research"]


async def get_sota_findings(
    db: AsyncSession, limit: int = 20
) -> List[Dict[str, Any]]:
    """Return the most recent SOTA findings ordered by date."""
    q = (
        select(Finding)
        .where(Finding.is_sota == True)  # noqa: E712
        .order_by(Finding.date_detected.desc())
        .limit(limit)
    )
    result = await db.execute(q)
    rows = result.scalars().all()
    return [
        {
            "id": f.id,
            "title": f.title,
            "entities": f.entities or [],
            "source_url": f.source_url,
            "date_detected": (
                f.date_detected.isoformat() if f.date_detected else None
            ),
            "confidence": f.confidence,
            "sota_confidence": f.sota_confidence,
            "category": f.category,
            "agent_id": f.agent_id,
            "summary_short": f.summary_short,
        }
        for f in rows
    ]


async def get_entity_heatmap(
    db: AsyncSession, days: int = 7
) -> Dict[str, Any]:
    """Build entity-vs-topic frequency matrix from recent findings.

    Returns:
        {
            "entities": ["OpenAI", "Anthropic", ...],
            "topics": ["models", "research", ...],
            "matrix": [[5, 2, 1, ...], ...]
        }
    """
    since = datetime.now(timezone.utc) - timedelta(days=days)
    q = select(Finding).where(Finding.created_at >= since)
    result = await db.execute(q)
    rows = result.scalars().all()

    entity_topic_counts: Dict[str, Dict[str, int]] = defaultdict(
        lambda: defaultdict(int)
    )

    for f in rows:
        combined_text = " ".join(filter(None, [
            f.title, f.summary_short, f.summary_long,
        ]))
        tags = f.tags or []
        topics = _classify_topics(combined_text, tags)

        entities = f.entities or []
        if not entities and f.publisher:
            entities = [f.publisher]

        for raw_ent in entities:
            ent = normalize_entity(raw_ent)
            for topic in topics:
                entity_topic_counts[ent][topic] += 1

    all_entities = sorted(entity_topic_counts.keys())
    matrix = [
        [entity_topic_counts[ent].get(t, 0) for t in HEATMAP_TOPICS]
        for ent in all_entities
    ]

    return {
        "entities": all_entities,
        "topics": HEATMAP_TOPICS,
        "matrix": matrix,
    }
