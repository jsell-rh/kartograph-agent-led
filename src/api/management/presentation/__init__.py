"""Management presentation layer.

Organizes presentation concerns by domain aggregate following DDD principles.
Each aggregate package contains its own routes and models.
"""

from __future__ import annotations

from fastapi import APIRouter

from management.presentation.data_sources import routes as data_source_routes
from management.presentation.knowledge_graphs import routes as kg_routes

router = APIRouter(
    prefix="/management",
    tags=["management"],
)

router.include_router(kg_routes.router)
router.include_router(data_source_routes.router)

__all__ = ["router"]
