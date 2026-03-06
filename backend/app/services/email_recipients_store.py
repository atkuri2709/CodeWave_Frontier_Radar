"""Persist and load email recipients for digest (UI-managed list)."""

import json
from pathlib import Path
from typing import List

# Resolve path relative to backend root (same dir as data/radar.db) so it persists regardless of cwd
_BACKEND_ROOT = Path(__file__).resolve().parent.parent.parent
RECIPIENTS_FILE = _BACKEND_ROOT / "data" / "email_recipients.json"


def _path() -> Path:
    return RECIPIENTS_FILE


def get_stored_recipients() -> List[str]:
    """Return list of emails from data/email_recipients.json, or empty list."""
    path = _path()
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        emails = data.get("emails") if isinstance(data, dict) else data
        if not isinstance(emails, list):
            return []
        return [str(e).strip() for e in emails if e and str(e).strip()]
    except Exception:
        return []


def save_recipients(emails: List[str]) -> None:
    """Persist emails to data/email_recipients.json."""
    path = _path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {"emails": [e.strip() for e in emails if e and e.strip()]}, indent=2
        ),
        encoding="utf-8",
    )
