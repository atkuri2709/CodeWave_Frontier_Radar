"""Async database session and lifecycle — local SQLite only."""

from collections.abc import AsyncGenerator
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.config import get_settings

settings = get_settings()

# Ensure local SQLite file path exists (backend/data/ when run from backend)
_db_url = settings.database_url
if _db_url.startswith("sqlite"):
    # e.g. sqlite+aiosqlite:///./data/radar.db -> ./data/radar.db
    _path = _db_url.split("///")[-1].split("?")[0]
    if _path.startswith("./"):
        Path(_path).parent.mkdir(parents=True, exist_ok=True)

engine = create_async_engine(
    _db_url,
    echo=settings.debug,
)
async_session = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


class Base(DeclarativeBase):
    pass


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with async_session() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def init_db() -> None:
    """Create tables and add missing columns (SQLite local)."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        if "sqlite" in _db_url:
            _migrations = [
                (
                    "runs",
                    "findings_count",
                    "ALTER TABLE runs ADD COLUMN findings_count INTEGER DEFAULT 0",
                ),
                (
                    "runs",
                    "pipeline_name",
                    "ALTER TABLE runs ADD COLUMN pipeline_name VARCHAR(256)",
                ),
                (
                    "runs",
                    "pipeline_description",
                    "ALTER TABLE runs ADD COLUMN pipeline_description TEXT",
                ),
                (
                    "findings",
                    "impact_score",
                    "ALTER TABLE findings ADD COLUMN impact_score REAL",
                ),
                (
                    "findings",
                    "raw_metadata",
                    "ALTER TABLE findings ADD COLUMN raw_metadata TEXT",
                ),
                (
                    "sources",
                    "extra_config",
                    "ALTER TABLE sources ADD COLUMN extra_config TEXT",
                ),
                (
                    "sources",
                    "last_run_id",
                    "ALTER TABLE sources ADD COLUMN last_run_id INTEGER",
                ),
            ]

            def _run_migrations(sync_conn):
                for table, col, ddl in _migrations:
                    cur = sync_conn.execute(
                        text(
                            f"SELECT name FROM pragma_table_info('{table}') WHERE name = '{col}'"
                        )
                    )
                    if cur.fetchone() is None:
                        sync_conn.execute(text(ddl))

            await conn.run_sync(_run_migrations)
