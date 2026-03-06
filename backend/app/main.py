"""Frontier AI Radar - FastAPI application."""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

# Ensure app loggers (e.g. run_manager) emit to the terminal
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logging.getLogger("app").setLevel(logging.INFO)
# Avoid logging full request URLs (they can contain API keys); show WARNING and above only
logging.getLogger("httpx").setLevel(logging.WARNING)
from fastapi.middleware.cors import CORSMiddleware

from app.api import api_router
from app.config import get_settings
from app.db.database import init_db
from app.orchestration.scheduler import start_scheduler, stop_scheduler

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    start_scheduler()
    yield
    stop_scheduler()


app = FastAPI(
    title=settings.app_name,
    description="Daily Multi-Agent Intelligence System — Frontier AI Radar",
    version="0.1.0",
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(api_router)


@app.get("/health")
async def health():
    return {"status": "ok", "app": settings.app_name}
