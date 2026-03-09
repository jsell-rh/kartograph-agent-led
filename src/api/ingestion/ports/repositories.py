"""Repository protocols (ports) for the Ingestion bounded context (AIHCM-176).

Repository protocols define the persistence interface for aggregates.
Implementations are in the infrastructure layer; these are the abstractions
the application layer depends on.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from ingestion.domain.aggregates.sync_job import SyncJob
from ingestion.domain.value_objects import SyncJobId, SyncJobStatus


@runtime_checkable
class ISyncJobRepository(Protocol):
    """Repository for SyncJob aggregate persistence.

    All methods are async; implementations use asyncpg/SQLAlchemy.
    """

    async def save(self, sync_job: SyncJob) -> None:
        """Persist a SyncJob aggregate.

        Creates a new record or updates an existing one. Also persists
        domain events to the outbox for downstream processing.

        Args:
            sync_job: The SyncJob aggregate to persist
        """
        ...

    async def get_by_id(self, sync_job_id: SyncJobId) -> SyncJob | None:
        """Retrieve a SyncJob by its ID.

        Args:
            sync_job_id: The unique identifier of the sync job

        Returns:
            The SyncJob aggregate, or None if not found
        """
        ...

    async def list_by_knowledge_graph(
        self,
        knowledge_graph_id: str,
        *,
        status: SyncJobStatus | None = None,
        limit: int = 50,
    ) -> list[SyncJob]:
        """List SyncJobs for a knowledge graph, optionally filtered by status.

        Args:
            knowledge_graph_id: The knowledge graph to query
            status: Optional status filter
            limit: Maximum number of results (default 50)

        Returns:
            List of SyncJob aggregates, ordered by created_at descending
        """
        ...

    async def list_pending(self, *, limit: int = 100) -> list[SyncJob]:
        """List PENDING SyncJobs across all tenants.

        Used by the sync scheduler to find jobs that need to be dispatched.

        Args:
            limit: Maximum number of results (default 100)

        Returns:
            List of PENDING SyncJob aggregates, ordered by created_at ascending
        """
        ...
