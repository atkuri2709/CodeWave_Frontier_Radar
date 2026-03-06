"""Simple file-based cache for summaries to avoid re-calling LLM when content unchanged."""

import hashlib
import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

CACHE_FILE = "data/summary_cache.json"
MAX_ENTRIES = 500


def _path() -> Path:
    p = Path(CACHE_FILE)
    if not p.is_absolute():
        p = Path.cwd() / p
    return p


def get_cache_key(
    source_url: str, content_hash: Optional[str], text_snippet: str
) -> str:
    if content_hash:
        return hashlib.sha256(f"{source_url}:{content_hash}".encode()).hexdigest()[:32]
    return hashlib.sha256(f"{source_url}:{text_snippet}".encode()).hexdigest()[:32]


def get_cached(key: str) -> Optional[Dict[str, Any]]:
    """Return cached summary dict if present."""
    path = _path()
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        entries = data.get("entries") if isinstance(data, dict) else {}
        if not isinstance(entries, dict):
            return None
        return entries.get(key)
    except Exception:
        return None


def set_cached(
    key: str, summary: Dict[str, Any], max_entries: int = MAX_ENTRIES
) -> None:
    """Store summary; trim to max_entries (oldest keys dropped)."""
    path = _path()
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        if path.exists():
            data = json.loads(path.read_text(encoding="utf-8"))
        else:
            data = {"entries": {}, "order": []}
        entries = data.get("entries") or {}
        order = data.get("order") or []
        entries[key] = summary
        if key in order:
            order.remove(key)
        order.append(key)
        while len(order) > max_entries:
            old = order.pop(0)
            entries.pop(old, None)
        data["entries"] = entries
        data["order"] = order
        path.write_text(json.dumps(data, indent=0), encoding="utf-8")
    except Exception as e:
        logger.debug("Summary cache write failed: %s", e)
