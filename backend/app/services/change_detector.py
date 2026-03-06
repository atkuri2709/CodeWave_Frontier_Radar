"""Change detection via content hashing. Checks DB for previously seen content."""

import hashlib
import logging
from typing import Optional

from sqlalchemy import select, func

logger = logging.getLogger(__name__)


class ChangeDetector:
    """Detect if content changed since last snapshot (by hash)."""

    def content_hash(self, text: str) -> str:
        """Canonical hash for dedup and change detection."""
        normalized = " ".join(text.split()).strip().lower()
        return hashlib.sha256(normalized.encode("utf-8")).hexdigest()

    def is_new_or_changed(
        self, current_hash: str, last_known_hash: Optional[str]
    ) -> bool:
        if last_known_hash is None:
            return True
        return current_hash != last_known_hash

    async def hash_exists_in_db(self, diff_hash: str) -> bool:
        """Check if a finding with this diff_hash already exists in any previous run."""
        if not diff_hash:
            return False
        try:
            from app.db.database import async_session
            from app.db.models import Finding

            async with async_session() as session:
                result = await session.execute(
                    select(func.count())
                    .select_from(Finding)
                    .where(Finding.diff_hash == diff_hash)
                )
                count = result.scalar() or 0
                return count > 0
        except Exception as e:
            logger.debug("DB hash check failed: %s", e)
            return False
