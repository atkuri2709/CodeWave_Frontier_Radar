"""Deduplication via diff_hash, URL, and semantic similarity (title + entity overlap)."""

import hashlib
import logging
import re
from typing import List

from app.schemas.finding import FindingCreate

logger = logging.getLogger(__name__)

SIMILARITY_THRESHOLD = 0.70
STOPWORDS = frozenset(
    {
        "a",
        "an",
        "the",
        "and",
        "or",
        "of",
        "to",
        "in",
        "for",
        "on",
        "with",
        "is",
        "are",
        "was",
        "were",
        "be",
        "been",
        "by",
        "at",
        "from",
        "as",
        "this",
        "that",
        "it",
        "its",
        "new",
        "we",
        "our",
        "has",
        "have",
        "had",
    }
)


def _normalize_title(title: str) -> set[str]:
    """Convert title to a set of meaningful lowercase tokens."""
    words = re.findall(r"[a-z0-9]+", (title or "").lower())
    return {w for w in words if w not in STOPWORDS and len(w) > 1}


def _title_similarity(a: set[str], b: set[str]) -> float:
    """Jaccard similarity between two token sets."""
    if not a or not b:
        return 0.0
    intersection = a & b
    union = a | b
    return len(intersection) / len(union)


def _entity_overlap(a: list, b: list) -> float:
    """Fraction of shared entities between two findings."""
    set_a = {e.lower() for e in (a or [])}
    set_b = {e.lower() for e in (b or [])}
    if not set_a or not set_b:
        return 0.0
    return len(set_a & set_b) / len(set_a | set_b)


def _combined_similarity(
    f1: FindingCreate, f2: FindingCreate, tokens_a: set, tokens_b: set
) -> float:
    """Weighted combination: 60% title similarity + 40% entity overlap."""
    title_sim = _title_similarity(tokens_a, tokens_b)
    entity_sim = _entity_overlap(f1.entities, f2.entities)
    return 0.60 * title_sim + 0.40 * entity_sim


class DedupService:
    """Three-layer deduplication: diff_hash -> URL+title -> semantic similarity."""

    def deduplicate(self, findings: List[FindingCreate]) -> List[FindingCreate]:
        if not findings:
            return []

        # Layer 1: exact diff_hash dedup
        seen_hash: set[str] = set()
        after_hash: List[FindingCreate] = []
        for f in findings:
            h = f.diff_hash
            if h and h in seen_hash:
                continue
            if h:
                seen_hash.add(h)
            after_hash.append(f)

        # Layer 2: URL + title key dedup
        seen_key: set[tuple] = set()
        after_key: List[FindingCreate] = []
        for f in after_hash:
            url_str = str(f.source_url).strip().lower()
            key = (url_str, (f.title or "").strip()[:200].lower())
            if key in seen_key:
                continue
            seen_key.add(key)
            after_key.append(f)

        # Layer 3: semantic similarity (title tokens + entity overlap)
        accepted: List[FindingCreate] = []
        accepted_tokens: List[set[str]] = []

        for f in after_key:
            f_tokens = _normalize_title(f.title)
            is_dup = False
            for i, existing in enumerate(accepted):
                if f.category != existing.category:
                    continue
                sim = _combined_similarity(f, existing, f_tokens, accepted_tokens[i])
                if sim >= SIMILARITY_THRESHOLD:
                    logger.debug(
                        "Semantic dedup: dropping '%s' (sim=%.2f with '%s')",
                        (f.title or "")[:60],
                        sim,
                        (existing.title or "")[:60],
                    )
                    is_dup = True
                    break
            if not is_dup:
                accepted.append(f)
                accepted_tokens.append(f_tokens)

        removed = len(findings) - len(accepted)
        if removed:
            logger.info(
                "Dedup: %d → %d findings (%d duplicates removed)",
                len(findings),
                len(accepted),
                removed,
            )

        return accepted

    def cluster_by_topic(
        self,
        findings: List[FindingCreate],
    ) -> dict[str, List[FindingCreate]]:
        """Group by category for digest sections."""
        clusters: dict[str, List[FindingCreate]] = {
            "release": [],
            "research": [],
            "benchmark": [],
            "other": [],
        }
        for f in findings:
            cat = f.category if f.category in clusters else "other"
            clusters[cat].append(f)
        return clusters
