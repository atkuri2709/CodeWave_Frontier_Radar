"""Frontier AI Radar — Entry Point.

Usage:
    python run.py api          Start FastAPI backend on port 8000
    python run.py pipeline     Run the pipeline once (all agents) and exit
    python run.py scheduler    Start the API with the daily scheduler
    python run.py both         Start API + scheduler (default)
"""

import argparse
import asyncio
import logging
import sys

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logging.getLogger("httpx").setLevel(logging.WARNING)

logger = logging.getLogger(__name__)


def run_api(host: str = "0.0.0.0", port: int = 8000):
    """Start the FastAPI server (includes scheduler via lifespan)."""
    import uvicorn

    uvicorn.run("app.main:app", host=host, port=port, reload=False)


async def run_pipeline():
    """Execute one full pipeline run (agents 1-4 → digest) and exit."""
    from app.db.database import init_db

    await init_db()

    from app.orchestration.run_manager import RunManager

    manager = RunManager()
    run_id, config = await manager.start_run(trigger="manual")
    logger.info("Pipeline started: run_id=%s", run_id)
    await manager._execute_run(run_id, config)
    logger.info("Pipeline finished: run_id=%s", run_id)


def main():
    parser = argparse.ArgumentParser(description="Frontier AI Radar")
    parser.add_argument(
        "mode",
        nargs="?",
        default="both",
        choices=["api", "pipeline", "scheduler", "both"],
        help="Run mode (default: both)",
    )
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()

    if args.mode == "pipeline":
        asyncio.run(run_pipeline())
    elif args.mode in ("api", "scheduler", "both"):
        run_api(host=args.host, port=args.port)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
