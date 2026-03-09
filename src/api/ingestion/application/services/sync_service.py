"""SyncService application service (AIHCM-178).

Orchestrates the full ingestion sync lifecycle:
1. Create a SyncJob aggregate (PENDING)
2. Save it to the repository (with SyncJobCreated outbox event)
3. Transition to RUNNING and save (with SyncJobStarted outbox event)
4. Run the adapter to fetch raw content changes
5. Package changes into a JobPackage and store it
6. Transition to COMPLETED or FAILED and save (with outbox events)

The outbox worker (already generalized in AIHCM-175) picks up domain events
and delivers them to downstream contexts (e.g., triggers Extraction).
"""

from __future__ import annotations

import structlog
from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from ingestion.domain.aggregates.sync_job import SyncJob
from ingestion.ports.adapters import IIngestionAdapter
from ingestion.ports.repositories import ISyncJobRepository
from shared_kernel.datasource_types import DataSourceAdapterType
from shared_kernel.job_package import JobPackage

logger = structlog.get_logger(__name__)


@runtime_checkable
class IJobPackageStore(Protocol):
    """Port for persisting JobPackages (e.g., object storage or database BLOB)."""

    async def store(self, package: JobPackage) -> str:
        """Persist a JobPackage and return its ID."""
        ...


@dataclass
class SyncRequest:
    """Input data for a sync run.

    Attributes:
        knowledge_graph_id: The knowledge graph to synchronize
        data_source_id: The data source to ingest from
        tenant_id: Tenant isolation boundary
        adapter_type: Which adapter type is being used
        adapter: The concrete adapter instance to run
        since_cursor: Cursor from a previous sync run (None = first sync)
    """

    knowledge_graph_id: str
    data_source_id: str
    tenant_id: str
    adapter_type: DataSourceAdapterType
    adapter: IIngestionAdapter
    since_cursor: str | None = None


class SyncService:
    """Orchestrates the ingestion sync lifecycle.

    Coordinates the SyncJob aggregate, adapter execution, JobPackage
    creation, and persistence. Domain events are emitted to the outbox
    via the SyncJob aggregate and persisted by the repository.
    """

    def __init__(
        self,
        sync_job_repository: ISyncJobRepository,
        job_package_store: IJobPackageStore,
    ) -> None:
        self._repo = sync_job_repository
        self._pkg_store = job_package_store

    async def run(self, request: SyncRequest) -> SyncJob:
        """Execute a full sync run.

        Args:
            request: SyncRequest containing adapter and context information

        Returns:
            The final SyncJob aggregate (COMPLETED or FAILED status)
        """
        # 1. Create SyncJob in PENDING state
        job = SyncJob.create(
            knowledge_graph_id=request.knowledge_graph_id,
            data_source_id=request.data_source_id,
            tenant_id=request.tenant_id,
            adapter_type=request.adapter_type,
        )
        await self._repo.save(job)

        # 2. Transition to RUNNING
        job.start()
        await self._repo.save(job)

        # 3. Run adapter and package results
        try:
            changeset = await request.adapter.fetch_changeset(
                since_cursor=request.since_cursor
            )
            manifest, raw_files = changeset.to_manifest_and_raw_files()
            package = JobPackage.create(
                knowledge_graph_id=request.knowledge_graph_id,
                data_source_id=request.data_source_id,
                tenant_id=request.tenant_id,
                adapter_type=request.adapter_type,
                manifest=manifest,
                raw_files=raw_files,
            )
            job_package_id = await self._pkg_store.store(package)

            # 4. Mark COMPLETED
            job.complete(job_package_id=job_package_id)
            await self._repo.save(job)

        except Exception as exc:
            error_message = str(exc)
            logger.error(
                "sync_job_failed",
                sync_job_id=job.id.value,
                tenant_id=request.tenant_id,
                error=error_message,
            )
            job.fail(error_message=error_message)
            await self._repo.save(job)

        return job
