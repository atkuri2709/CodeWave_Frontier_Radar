from fastapi import APIRouter

from app.api.routes import (
    runs,
    sources,
    findings,
    digests,
    config,
    email_recipients,
    scheduler,
    logs,
    pipeline_configs,
    meta,
    analytics,
)

api_router = APIRouter(prefix="/api")
api_router.include_router(runs.router, prefix="/runs", tags=["runs"])
api_router.include_router(sources.router, prefix="/sources", tags=["sources"])
api_router.include_router(findings.router, prefix="/findings", tags=["findings"])
api_router.include_router(digests.router, prefix="/digests", tags=["digests"])
api_router.include_router(
    email_recipients.router, prefix="/email-recipients", tags=["email-recipients"]
)
api_router.include_router(config.router, prefix="/config", tags=["config"])
api_router.include_router(scheduler.router, prefix="/scheduler", tags=["scheduler"])
api_router.include_router(logs.router, prefix="/logs", tags=["logs"])
api_router.include_router(
    pipeline_configs.router, prefix="/pipeline-configs", tags=["pipeline-configs"]
)
api_router.include_router(meta.router, prefix="/meta", tags=["meta"])
api_router.include_router(analytics.router, prefix="/analytics", tags=["analytics"])
