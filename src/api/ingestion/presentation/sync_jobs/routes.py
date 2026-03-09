"""FastAPI routes for Sync Job management."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from iam.application.value_objects import CurrentUser
from iam.dependencies.user import get_current_user
from ingestion.dependencies.services import (
    InMemorySyncJobRepository,
    get_sync_job_repository,
)
from ingestion.domain.aggregates.sync_job import SyncJob
from ingestion.domain.value_objects import SyncJobId, SyncJobStatus
from ingestion.presentation.sync_jobs.models import SyncJobResponse, TriggerSyncRequest

router = APIRouter(
    prefix="/sync-jobs",
    tags=["sync-jobs"],
)


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    response_model=SyncJobResponse,
)
async def trigger_sync(
    request: TriggerSyncRequest,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    repo: Annotated[InMemorySyncJobRepository, Depends(get_sync_job_repository)],
) -> SyncJobResponse:
    """Trigger a manual sync job for a data source.

    Creates a new SyncJob in PENDING status. The sync worker will
    pick it up and run it asynchronously.

    Args:
        request: Trigger request with data source and KG identifiers.
        current_user: Authenticated user with tenant context.
        repo: SyncJob repository.

    Returns:
        SyncJobResponse with PENDING status.
    """
    job = SyncJob.create(
        knowledge_graph_id=request.knowledge_graph_id,
        data_source_id=request.data_source_id,
        tenant_id=current_user.tenant_id.value,
        adapter_type=request.adapter_type,
    )
    await repo.save(job)
    return SyncJobResponse.from_domain(job)


@router.get(
    "",
    response_model=list[SyncJobResponse],
)
async def list_sync_jobs(
    data_source_id: str,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    repo: Annotated[InMemorySyncJobRepository, Depends(get_sync_job_repository)],
    knowledge_graph_id: str | None = None,
    status_filter: str | None = None,
    limit: int = 50,
) -> list[SyncJobResponse]:
    """List sync jobs for a data source.

    Args:
        data_source_id: Filter by data source ID.
        knowledge_graph_id: Optional KG filter (fetches by KG then filters by DS).
        current_user: Authenticated user with tenant context.
        repo: SyncJob repository.
        status_filter: Optional status filter (pending/running/completed/failed).
        limit: Maximum results.

    Returns:
        List of SyncJobResponse ordered by created_at descending.
    """
    parsed_status: SyncJobStatus | None = None
    if status_filter:
        try:
            parsed_status = SyncJobStatus(status_filter)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Invalid status filter: {status_filter}",
            )

    if knowledge_graph_id:
        jobs = await repo.list_by_knowledge_graph(
            knowledge_graph_id,
            status=parsed_status,
            limit=limit * 4,  # over-fetch since we'll filter by DS
        )
        jobs = [j for j in jobs if j.data_source_id == data_source_id][:limit]
    else:
        # Fall back to listing all and filtering in memory
        # (a real impl would have list_by_data_source on the repo)
        jobs = await repo.list_by_data_source(
            data_source_id, status=parsed_status, limit=limit
        )

    return [SyncJobResponse.from_domain(j) for j in jobs]


@router.get(
    "/{job_id}",
    response_model=SyncJobResponse,
)
async def get_sync_job(
    job_id: str,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    repo: Annotated[InMemorySyncJobRepository, Depends(get_sync_job_repository)],
) -> SyncJobResponse:
    """Get a sync job by ID.

    Args:
        job_id: SyncJob ULID.
        current_user: Authenticated user with tenant context.
        repo: SyncJob repository.

    Returns:
        SyncJobResponse.

    Raises:
        HTTPException: 404 if not found.
    """
    try:
        sync_job_id = SyncJobId.from_string(job_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid job ID: {job_id}",
        )

    job = await repo.get_by_id(sync_job_id)
    if job is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Sync job not found",
        )
    return SyncJobResponse.from_domain(job)
