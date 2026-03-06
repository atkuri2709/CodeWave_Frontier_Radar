"""Config API: get/save radar YAML config."""

from pathlib import Path

import yaml
from fastapi import APIRouter, HTTPException

from app.config import get_settings
from app.orchestration.run_manager import load_radar_config

router = APIRouter()


@router.get("")
async def get_config():
    """Return current radar config (from YAML)."""
    return load_radar_config()


@router.put("")
async def save_config(config: dict):
    """Persist config to YAML (optional; for hackathon UI edit)."""
    settings = get_settings()
    path = Path(settings.config_path)
    if not path.is_absolute():
        path = Path.cwd() / path
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with open(path, "w") as f:
            yaml.safe_dump(config, f, default_flow_style=False, sort_keys=False)
        return {"ok": True, "path": str(path)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
