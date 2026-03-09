"""Observability probes for the Ingestion domain (Domain Oriented Observability)."""

from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class SyncJobProbe(Protocol):
    """Domain probe for SyncJob aggregate lifecycle events.

    Follows Domain Oriented Observability: domain operations emit probe events
    rather than raw log statements, enabling testability and observability.
    """

    def created(
        self, *, sync_job_id: str, knowledge_graph_id: str, tenant_id: str
    ) -> None:
        """Emitted when a SyncJob is created."""
        ...

    def started(self, *, sync_job_id: str, tenant_id: str) -> None:
        """Emitted when a SyncJob starts running."""
        ...

    def completed(
        self, *, sync_job_id: str, tenant_id: str, job_package_id: str
    ) -> None:
        """Emitted when a SyncJob completes successfully."""
        ...

    def failed(self, *, sync_job_id: str, tenant_id: str, error_message: str) -> None:
        """Emitted when a SyncJob fails."""
        ...


class DefaultSyncJobProbe:
    """No-op default probe — suitable for tests and environments without observability."""

    def created(
        self, *, sync_job_id: str, knowledge_graph_id: str, tenant_id: str
    ) -> None:
        pass

    def started(self, *, sync_job_id: str, tenant_id: str) -> None:
        pass

    def completed(
        self, *, sync_job_id: str, tenant_id: str, job_package_id: str
    ) -> None:
        pass

    def failed(self, *, sync_job_id: str, tenant_id: str, error_message: str) -> None:
        pass
