"""Daily scheduler using APScheduler.

Reads scheduled jobs from the `scheduled_jobs` DB table (managed via UI).
Each ScheduledJob row becomes an APScheduler job with its own cron/interval trigger.
Supports daily, weekly, monthly, yearly, and interval frequencies.
"""

import asyncio
import logging
from datetime import date, datetime
from typing import Optional

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from app.orchestration.run_manager import RunManager

logger = logging.getLogger(__name__)

_scheduler: Optional[AsyncIOScheduler] = None


def _job_id(scheduler_name: str) -> str:
    return f"scheduled_{scheduler_name}"


def _parse_time(run_time: str) -> tuple[int, int]:
    try:
        parts = str(run_time).strip().split(":")
        h = int(parts[0])
        m = int(parts[1]) if len(parts) > 1 else 0
        return max(0, min(23, h)), max(0, min(59, m))
    except Exception:
        logger.warning("Invalid run_time '%s', defaulting to 06:30", run_time)
        return 6, 30


def _get_timezone(tz_str: str):
    try:
        from zoneinfo import ZoneInfo
        return ZoneInfo(tz_str)
    except Exception:
        logger.warning("Invalid timezone '%s', using system default", tz_str)
        return None


def _parse_date(d: str | None) -> date | None:
    if not d:
        return None
    try:
        return datetime.strptime(d, "%Y-%m-%d").date()
    except Exception:
        return None


async def _run_pipeline(pipeline_name: str):
    """Execute the full pipeline for a specific scheduled job."""
    manager = RunManager()
    try:
        run_id, run_config = await manager.start_run(
            trigger="schedule", pipeline_name=pipeline_name,
        )
        logger.info("Scheduled run started: pipeline=%s run_id=%s", pipeline_name, run_id)
        asyncio.create_task(manager._execute_run(run_id, run_config))
    except Exception as e:
        logger.exception("Scheduled pipeline '%s' failed: %s", pipeline_name, e)


def _load_jobs_sync():
    """Synchronously load all ScheduledJob rows (for use during scheduler start)."""
    import sqlite3
    from app.config import get_settings
    settings = get_settings()
    db_url = settings.database_url
    db_path = db_url.split("///")[-1].split("?")[0]
    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cur = conn.execute("SELECT * FROM scheduled_jobs WHERE enabled = 1")
        rows = [dict(r) for r in cur.fetchall()]
        conn.close()
        return rows
    except Exception as e:
        logger.warning("Could not load scheduled_jobs from DB: %s", e)
        return []


def _parse_hm(t: str | None) -> tuple[int, int] | None:
    """Parse 'HH:MM' into (hour, minute) or return None."""
    if not t:
        return None
    try:
        parts = str(t).strip().split(":")
        h = int(parts[0])
        m = int(parts[1]) if len(parts) > 1 else 0
        return max(0, min(23, h)), max(0, min(59, m))
    except Exception:
        return None


def _auto_disable_job(job_id: int | None):
    """Mark an expired job as disabled in the DB so it won't be loaded again."""
    if not job_id:
        return
    import sqlite3
    from app.config import get_settings
    settings = get_settings()
    db_path = settings.database_url.split("///")[-1].split("?")[0]
    try:
        conn = sqlite3.connect(db_path)
        conn.execute("UPDATE scheduled_jobs SET enabled = 0 WHERE id = ?", (job_id,))
        conn.commit()
        conn.close()
        logger.info("Auto-disabled expired scheduled job id=%s", job_id)
    except Exception as e:
        logger.warning("Could not auto-disable job %s: %s", job_id, e)


def _build_trigger(job: dict):
    """Build an APScheduler trigger from a job row."""
    from datetime import time as dt_time

    frequency = job.get("frequency", "daily")
    run_time = job.get("run_time") or "06:30"
    tz_str = job.get("timezone") or "UTC"
    hour, minute = _parse_time(run_time)
    tz = _get_timezone(tz_str)

    start_dt = _parse_date(job.get("start_date"))
    end_dt = _parse_date(job.get("end_date"))
    start_hm = _parse_hm(job.get("start_time"))
    end_hm = _parse_hm(job.get("end_time"))

    kwargs: dict = {}
    if tz:
        kwargs["timezone"] = tz
    if start_dt:
        st = dt_time(start_hm[0], start_hm[1]) if start_hm else datetime.min.time()
        kwargs["start_date"] = datetime.combine(start_dt, st)
    if end_dt:
        et = dt_time(end_hm[0], end_hm[1]) if end_hm else dt_time(23, 59, 59)
        kwargs["end_date"] = datetime.combine(end_dt, et)
    elif end_hm and not end_dt:
        et = dt_time(end_hm[0], end_hm[1])
        kwargs["end_date"] = datetime.combine(date.today(), et)

    if frequency == "interval" and job.get("interval_minutes"):
        minutes = max(1, int(job["interval_minutes"]))
        return IntervalTrigger(minutes=minutes, **kwargs), f"every {minutes} min"

    if frequency == "weekly":
        trigger = CronTrigger(day_of_week="mon", hour=hour, minute=minute, **kwargs)
        return trigger, f"weekly Mon {hour:02d}:{minute:02d} {tz_str}"

    if frequency == "monthly":
        trigger = CronTrigger(day=1, hour=hour, minute=minute, **kwargs)
        return trigger, f"monthly 1st {hour:02d}:{minute:02d} {tz_str}"

    if frequency == "yearly":
        trigger = CronTrigger(month=1, day=1, hour=hour, minute=minute, **kwargs)
        return trigger, f"yearly Jan 1 {hour:02d}:{minute:02d} {tz_str}"

    trigger = CronTrigger(hour=hour, minute=minute, **kwargs)
    return trigger, f"daily {hour:02d}:{minute:02d} {tz_str}"


def start_scheduler() -> None:
    """Start the scheduler with jobs from the DB. Must be called from the asyncio event loop thread."""
    global _scheduler

    if _scheduler is not None and _scheduler.running:
        logger.debug("Scheduler already running, skipping start")
        return

    jobs = _load_jobs_sync()
    if not jobs:
        logger.info("No enabled scheduled jobs in DB — scheduler not started")
        _scheduler = None
        return

    _scheduler = AsyncIOScheduler()
    now = datetime.now()
    added = 0

    for job in jobs:
        pipeline_name = job["pipeline_name"]
        scheduler_name = job.get("scheduler_name", pipeline_name)
        jid = _job_id(scheduler_name)
        trigger, desc = _build_trigger(job)

        end_date_val = getattr(trigger, "end_date", None)
        if end_date_val is not None:
            end_naive = end_date_val.replace(tzinfo=None) if end_date_val.tzinfo else end_date_val
            if end_naive < now:
                logger.info("Skipping expired schedule '%s' (ended %s)", scheduler_name, end_date_val)
                _auto_disable_job(job.get("id"))
                continue

        _scheduler.add_job(
            _run_pipeline, trigger, id=jid, replace_existing=True,
            args=[pipeline_name],
        )
        added += 1
        logger.info("Scheduled '%s' (pipeline: %s): %s", scheduler_name, pipeline_name, desc)

    if added == 0:
        logger.info("All scheduled jobs are expired or none to run — scheduler not started")
        _scheduler = None
        return

    try:
        _scheduler.start()
        logger.info("Scheduler started with %d job(s)", added)
    except Exception as e:
        logger.error("Failed to start scheduler: %s", e)
        _scheduler = None


def stop_scheduler() -> None:
    global _scheduler
    if _scheduler is not None:
        try:
            if _scheduler.running:
                _scheduler.shutdown(wait=False)
                logger.info("Scheduler stopped")
        except Exception as e:
            logger.warning("Error stopping scheduler: %s", e)
        _scheduler = None


def restart_scheduler() -> None:
    """Restart scheduler. Safe to call from any context — schedules itself on the event loop."""
    try:
        loop = asyncio.get_running_loop()
        loop.call_soon(_do_restart)
    except RuntimeError:
        _do_restart()


def _do_restart():
    logger.info("Restarting scheduler with fresh DB config...")
    stop_scheduler()
    start_scheduler()


def get_scheduler_status() -> dict:
    running = _scheduler is not None and _scheduler.running if _scheduler else False
    jobs_info = []
    if running and _scheduler:
        for job in _scheduler.get_jobs():
            info = {"id": job.id, "name": job.name}
            if job.next_run_time:
                info["next_run"] = job.next_run_time.isoformat()
            jobs_info.append(info)

    return {
        "running": running,
        "job_count": len(jobs_info),
        "jobs": jobs_info,
    }
