"""Dependency injection factories for Ingestion bounded context.

Uses an in-memory SyncJob repository until a DB-backed implementation
is provided by the ingestion infrastructure team (no migration exists yet).
"""

from __future__ import annotations

from ingestion.domain.aggregates.sync_job import SyncJob
from ingestion.domain.value_objects import SyncJobId, SyncJobStatus

# Module-level in-memory store (survives request lifetime, resets on restart)
_sync_job_store: dict[str, SyncJob] = {}


class InMemorySyncJobRepository:
    """In-memory ISyncJobRepository for development use.

    Satisfies the ISyncJobRepository protocol. Data is held in a
    module-level dict and does NOT persist across server restarts.

    Replace with a SQLAlchemy-backed implementation once the
    ingestion_sync_jobs migration is added.
    """

    async def save(self, sync_job: SyncJob) -> None:
        _sync_job_store[sync_job.id.value] = sync_job

    async def get_by_id(self, sync_job_id: SyncJobId) -> SyncJob | None:
        return _sync_job_store.get(sync_job_id.value)

    async def list_by_knowledge_graph(
        self,
        knowledge_graph_id: str,
        *,
        status: SyncJobStatus | None = None,
        limit: int = 50,
    ) -> list[SyncJob]:
        jobs = [
            j
            for j in _sync_job_store.values()
            if j.knowledge_graph_id == knowledge_graph_id
        ]
        if status is not None:
            jobs = [j for j in jobs if j.status == status]
        return sorted(jobs, key=lambda j: j.created_at, reverse=True)[:limit]

    async def list_by_data_source(
        self,
        data_source_id: str,
        *,
        status: SyncJobStatus | None = None,
        limit: int = 50,
    ) -> list[SyncJob]:
        jobs = [
            j for j in _sync_job_store.values() if j.data_source_id == data_source_id
        ]
        if status is not None:
            jobs = [j for j in jobs if j.status == status]
        return sorted(jobs, key=lambda j: j.created_at, reverse=True)[:limit]

    async def list_pending(self, *, limit: int = 100) -> list[SyncJob]:
        jobs = [
            j for j in _sync_job_store.values() if j.status == SyncJobStatus.PENDING
        ]
        return sorted(jobs, key=lambda j: j.created_at)[:limit]


# Singleton repository instance (shared across all requests)
_repo = InMemorySyncJobRepository()


def get_sync_job_repository() -> InMemorySyncJobRepository:
    """FastAPI dependency that returns the shared in-memory SyncJob repository."""
    return _repo
