"""Meta API: dynamic agent/category/config metadata for the frontend."""

from typing import List

from fastapi import APIRouter, Depends
from sqlalchemy import select, distinct
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.db.models import Finding

router = APIRouter()

AGENT_REGISTRY = [
    {
        "id": "competitors",
        "label": "Competitors",
        "badge": "agent-orange",
        "color": "#FF6A3D",
        "description": "Tracks competitor releases, changelogs, and announcements",
    },
    {
        "id": "model_providers",
        "label": "Model Providers",
        "badge": "agent-lavender",
        "color": "#9DAAF2",
        "description": "Monitors model provider blogs and release pages",
    },
    {
        "id": "research",
        "label": "Research",
        "badge": "agent-gold",
        "color": "#F4DB7D",
        "description": "Scouts latest AI research publications from arXiv and curated sources",
    },
    {
        "id": "hf_benchmarks",
        "label": "HF Benchmarks",
        "badge": "agent-navy",
        "color": "#1A2238",
        "description": "Monitors Hugging Face leaderboards for benchmark and SOTA changes",
    },
]

CATEGORY_REGISTRY = [
    {"id": "release", "label": "Release"},
    {"id": "research", "label": "Research"},
    {"id": "benchmark", "label": "Benchmark"},
]


@router.get("/agents")
async def get_agents():
    return AGENT_REGISTRY


@router.get("/categories")
async def get_categories(db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(distinct(Finding.category)).where(Finding.category.isnot(None))
    )
    db_categories = [r[0] for r in result.all() if r[0]]
    known_ids = {c["id"] for c in CATEGORY_REGISTRY}
    merged = list(CATEGORY_REGISTRY)
    for cat in db_categories:
        if cat not in known_ids:
            merged.append({"id": cat, "label": cat.capitalize()})
    return merged


@router.get("/")
async def get_meta(db: AsyncSession = Depends(get_db)):
    cat_result = await db.execute(
        select(distinct(Finding.category)).where(Finding.category.isnot(None))
    )
    db_categories = [r[0] for r in cat_result.all() if r[0]]
    known_ids = {c["id"] for c in CATEGORY_REGISTRY}
    categories = list(CATEGORY_REGISTRY)
    for cat in db_categories:
        if cat not in known_ids:
            categories.append({"id": cat, "label": cat.capitalize()})

    agent_result = await db.execute(
        select(distinct(Finding.agent_id)).where(Finding.agent_id.isnot(None))
    )
    db_agent_ids = {r[0] for r in agent_result.all() if r[0]}
    known_agent_ids = {a["id"] for a in AGENT_REGISTRY}
    agents = list(AGENT_REGISTRY)
    for aid in db_agent_ids:
        if aid not in known_agent_ids:
            agents.append(
                {
                    "id": aid,
                    "label": aid.replace("_", " ").title(),
                    "badge": "badge-zinc",
                    "color": "#6b7394",
                    "description": "",
                }
            )

    return {"agents": agents, "categories": categories}
