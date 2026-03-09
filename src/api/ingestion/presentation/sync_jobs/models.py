"""Pydantic models for Sync Job API requests and responses."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from ingestion.domain.aggregates.sync_job import SyncJob
from shared_kernel.datasource_types import DataSourceAdapterType


class TriggerSyncRequest(BaseModel):
    """Request body for triggering a manual sync job."""

    knowledge_graph_id: str = Field(
        ..., description="The knowledge graph to synchronize"
    )
    data_source_id: str = Field(..., description="The data source to ingest from")
    adapter_type: DataSourceAdapterType = Field(
        ..., description="Adapter type (e.g. github)"
    )


class SyncJobResponse(BaseModel):
    """Response model for a SyncJob."""

    id: str = Field(..., description="SyncJob ID (ULID)")
    knowledge_graph_id: str = Field(..., description="Knowledge graph ID")
    data_source_id: str = Field(..., description="Data source ID")
    tenant_id: str = Field(..., description="Owning tenant ID")
    adapter_type: str = Field(..., description="Adapter type")
    status: str = Field(
        ..., description="Job status: pending, running, completed, failed"
    )
    created_at: datetime = Field(..., description="When the job was created")
    updated_at: datetime = Field(..., description="When the job was last updated")
    job_package_id: str | None = Field(
        None, description="ID of produced job package (COMPLETED only)"
    )
    error_message: str | None = Field(None, description="Error detail (FAILED only)")

    @classmethod
    def from_domain(cls, job: SyncJob) -> SyncJobResponse:
        """Convert a SyncJob domain aggregate to API response."""
        return cls(
            id=job.id.value,
            knowledge_graph_id=job.knowledge_graph_id,
            data_source_id=job.data_source_id,
            tenant_id=job.tenant_id,
            adapter_type=job.adapter_type.value,
            status=job.status.value,
            created_at=job.created_at,
            updated_at=job.updated_at,
            job_package_id=job.job_package_id,
            error_message=job.error_message,
        )
