"""Domain events for the Ingestion bounded context."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Union

from shared_kernel.datasource_types import DataSourceAdapterType


@dataclass(frozen=True)
class SyncJobCreated:
    """Emitted when a new SyncJob is created."""

    sync_job_id: str
    knowledge_graph_id: str
    data_source_id: str
    tenant_id: str
    adapter_type: DataSourceAdapterType
    occurred_at: datetime


@dataclass(frozen=True)
class SyncJobStarted:
    """Emitted when a SyncJob transitions from PENDING to RUNNING."""

    sync_job_id: str
    tenant_id: str
    occurred_at: datetime


@dataclass(frozen=True)
class SyncJobCompleted:
    """Emitted when a SyncJob completes successfully."""

    sync_job_id: str
    tenant_id: str
    job_package_id: str
    occurred_at: datetime


@dataclass(frozen=True)
class SyncJobFailed:
    """Emitted when a SyncJob fails."""

    sync_job_id: str
    tenant_id: str
    error_message: str
    occurred_at: datetime


DomainEvent = Union[SyncJobCreated, SyncJobStarted, SyncJobCompleted, SyncJobFailed]
