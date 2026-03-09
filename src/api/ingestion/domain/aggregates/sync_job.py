"""SyncJob aggregate for the Ingestion bounded context (AIHCM-176).

SyncJob represents the lifecycle of a single synchronization run:
from creation (PENDING) through execution (RUNNING) to terminal
state (COMPLETED or FAILED).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from ingestion.domain.events import (
    SyncJobCompleted,
    SyncJobCreated,
    SyncJobFailed,
    SyncJobStarted,
)
from ingestion.domain.exceptions import (
    InvalidSyncJobTransitionError,
    SyncJobAlreadyTerminalError,
)
from ingestion.domain.observability import DefaultSyncJobProbe, SyncJobProbe
from ingestion.domain.value_objects import SyncJobId, SyncJobStatus
from shared_kernel.datasource_types import DataSourceAdapterType

if TYPE_CHECKING:
    from ingestion.domain.events import DomainEvent

_TERMINAL_STATUSES = frozenset({SyncJobStatus.COMPLETED, SyncJobStatus.FAILED})


@dataclass
class SyncJob:
    """SyncJob aggregate representing a single ingestion sync run.

    Business rules:
    - Status transitions: PENDING → RUNNING → COMPLETED | FAILED
    - Only RUNNING jobs can be completed or failed
    - Terminal jobs (COMPLETED, FAILED) cannot be transitioned further

    Event collection:
    - All mutating operations record domain events
    - Events are collected via collect_events() for the outbox pattern
    """

    id: SyncJobId
    knowledge_graph_id: str
    data_source_id: str
    tenant_id: str
    adapter_type: DataSourceAdapterType
    status: SyncJobStatus
    created_at: datetime
    updated_at: datetime
    job_package_id: str | None = None
    error_message: str | None = None
    _pending_events: list[DomainEvent] = field(default_factory=list, repr=False)
    _probe: SyncJobProbe = field(
        default_factory=DefaultSyncJobProbe,
        repr=False,
    )

    @classmethod
    def create(
        cls,
        knowledge_graph_id: str,
        data_source_id: str,
        tenant_id: str,
        adapter_type: DataSourceAdapterType,
        *,
        probe: SyncJobProbe | None = None,
    ) -> SyncJob:
        """Factory method for creating a new SyncJob.

        Generates a unique ID, sets status to PENDING, and records
        the SyncJobCreated event.

        Args:
            knowledge_graph_id: The knowledge graph to synchronize
            data_source_id: The data source to ingest from
            tenant_id: The tenant that owns this job
            adapter_type: The adapter to use for ingestion
            probe: Optional observability probe

        Returns:
            A new SyncJob in PENDING status with SyncJobCreated event recorded
        """
        now = datetime.now(UTC)
        job = cls(
            id=SyncJobId.generate(),
            knowledge_graph_id=knowledge_graph_id,
            data_source_id=data_source_id,
            tenant_id=tenant_id,
            adapter_type=adapter_type,
            status=SyncJobStatus.PENDING,
            created_at=now,
            updated_at=now,
            _probe=probe or DefaultSyncJobProbe(),
        )
        job._pending_events.append(
            SyncJobCreated(
                sync_job_id=job.id.value,
                knowledge_graph_id=knowledge_graph_id,
                data_source_id=data_source_id,
                tenant_id=tenant_id,
                adapter_type=adapter_type,
                occurred_at=now,
            )
        )
        job._probe.created(
            sync_job_id=job.id.value,
            knowledge_graph_id=knowledge_graph_id,
            tenant_id=tenant_id,
        )
        return job

    def start(self) -> None:
        """Transition the SyncJob from PENDING to RUNNING.

        Raises:
            InvalidSyncJobTransitionError: If the job is not PENDING
            SyncJobAlreadyTerminalError: If the job is already terminal
        """
        if self.status in _TERMINAL_STATUSES:
            raise SyncJobAlreadyTerminalError(
                f"SyncJob {self.id} is already in terminal state {self.status}"
            )
        if self.status != SyncJobStatus.PENDING:
            raise InvalidSyncJobTransitionError(
                f"SyncJob {self.id} cannot transition from {self.status} to RUNNING"
            )
        now = datetime.now(UTC)
        self.status = SyncJobStatus.RUNNING
        self.updated_at = now
        self._pending_events.append(
            SyncJobStarted(
                sync_job_id=self.id.value,
                tenant_id=self.tenant_id,
                occurred_at=now,
            )
        )
        self._probe.started(sync_job_id=self.id.value, tenant_id=self.tenant_id)

    def complete(self, job_package_id: str) -> None:
        """Transition the SyncJob from RUNNING to COMPLETED.

        Args:
            job_package_id: The ID of the JobPackage produced by this run

        Raises:
            InvalidSyncJobTransitionError: If the job is not RUNNING
            SyncJobAlreadyTerminalError: If the job is already terminal
        """
        if self.status in _TERMINAL_STATUSES:
            raise SyncJobAlreadyTerminalError(
                f"SyncJob {self.id} is already in terminal state {self.status}"
            )
        if self.status != SyncJobStatus.RUNNING:
            raise InvalidSyncJobTransitionError(
                f"SyncJob {self.id} cannot complete from status {self.status}"
            )
        now = datetime.now(UTC)
        self.status = SyncJobStatus.COMPLETED
        self.job_package_id = job_package_id
        self.updated_at = now
        self._pending_events.append(
            SyncJobCompleted(
                sync_job_id=self.id.value,
                tenant_id=self.tenant_id,
                job_package_id=job_package_id,
                occurred_at=now,
            )
        )
        self._probe.completed(
            sync_job_id=self.id.value,
            tenant_id=self.tenant_id,
            job_package_id=job_package_id,
        )

    def fail(self, error_message: str) -> None:
        """Transition the SyncJob from RUNNING to FAILED.

        Args:
            error_message: Human-readable description of what went wrong

        Raises:
            InvalidSyncJobTransitionError: If the job is not RUNNING
            SyncJobAlreadyTerminalError: If the job is already terminal
        """
        if self.status in _TERMINAL_STATUSES:
            raise SyncJobAlreadyTerminalError(
                f"SyncJob {self.id} is already in terminal state {self.status}"
            )
        if self.status != SyncJobStatus.RUNNING:
            raise InvalidSyncJobTransitionError(
                f"SyncJob {self.id} cannot fail from status {self.status}"
            )
        now = datetime.now(UTC)
        self.status = SyncJobStatus.FAILED
        self.error_message = error_message
        self.updated_at = now
        self._pending_events.append(
            SyncJobFailed(
                sync_job_id=self.id.value,
                tenant_id=self.tenant_id,
                error_message=error_message,
                occurred_at=now,
            )
        )
        self._probe.failed(
            sync_job_id=self.id.value,
            tenant_id=self.tenant_id,
            error_message=error_message,
        )

    def collect_events(self) -> list[DomainEvent]:
        """Return and clear pending domain events.

        Returns:
            List of pending domain events (clears internal list)
        """
        events = self._pending_events.copy()
        self._pending_events.clear()
        return events
