"""SOTA (State-of-the-Art) claim detection for findings.

Scans combined text (title + summary + evidence) for keywords that indicate
a new benchmark record, leaderboard topping, or performance breakthrough.
Returns a boolean flag and a confidence score weighted by keyword strength.
"""

import logging
import re
from typing import Dict

logger = logging.getLogger(__name__)

# (pattern, weight) — higher weight = stronger SOTA signal
SOTA_PATTERNS: list[tuple[str, float]] = [
    (r"\bstate[\-\s]of[\-\s]the[\-\s]art\b", 1.0),
    (r"\bsota\b", 1.0),
    (r"\bnew benchmark record\b", 0.95),
    (r"\btop of leaderboard\b", 0.95),
    (r"\brank\s*#?\s*1\b", 0.90),
    (r"\bhighest score\b", 0.90),
    (r"\bnew record\b", 0.85),
    (r"\bbest performance\b", 0.85),
    (r"\boutperforms?\b", 0.80),
    (r"\bsurpasses?\b", 0.80),
    (r"\bexceeds?\s+(previous|prior|existing)\b", 0.80),
    (r"\bleaderboard\b", 0.70),
    (r"\bbenchmark[\-\s]leading\b", 0.75),
    (r"\brecord[\-\s]breaking\b", 0.90),
    (r"\bsets?\s+a?\s*new\s+record\b", 0.90),
    (r"\btop[\-\s]performing\b", 0.75),
    (r"\bbest[\-\s]in[\-\s]class\b", 0.80),
    (r"\bworld[\-\s]record\b", 0.95),
]

_COMPILED = [(re.compile(p, re.IGNORECASE), w) for p, w in SOTA_PATTERNS]


def detect_sota_claim(text: str) -> Dict[str, object]:
    """Detect whether text contains a SOTA claim.

    Args:
        text: Combined text from title, summary_long, and evidence.

    Returns:
        {"is_sota": bool, "confidence": float} where confidence is the
        highest matched keyword weight, scaled to [0, 1].
    """
    if not text:
        return {"is_sota": False, "confidence": 0.0}

    lower = text.lower()
    best_weight = 0.0
    matched_count = 0

    for pattern, weight in _COMPILED:
        if pattern.search(lower):
            matched_count += 1
            if weight > best_weight:
                best_weight = weight

    if matched_count == 0:
        return {"is_sota": False, "confidence": 0.0}

    # Boost confidence slightly when multiple keywords match (max 1.0)
    bonus = min(0.1, (matched_count - 1) * 0.03)
    confidence = round(min(1.0, best_weight + bonus), 2)

    return {"is_sota": True, "confidence": confidence}
