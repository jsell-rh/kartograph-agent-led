"""Ingestion presentation layer.

Exposes sync job management endpoints for the dev-ui.
"""

from __future__ import annotations

from fastapi import APIRouter

from ingestion.presentation.sync_jobs import routes as sync_job_routes

router = APIRouter(
    prefix="/ingestion",
    tags=["ingestion"],
)

router.include_router(sync_job_routes.router)

__all__ = ["router"]
