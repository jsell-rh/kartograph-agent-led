"""Domain exceptions for the Ingestion bounded context."""

from __future__ import annotations


class IngestionDomainError(Exception):
    """Base class for all Ingestion domain errors."""


class InvalidSyncJobTransitionError(IngestionDomainError):
    """Raised when an invalid status transition is attempted on a SyncJob.

    For example: trying to start() a job that is already RUNNING,
    or trying to complete() a job that is still PENDING.
    """


class SyncJobAlreadyTerminalError(IngestionDomainError):
    """Raised when attempting to mutate a SyncJob that is already in a terminal state.

    COMPLETED and FAILED are terminal states — a job in these states
    cannot be transitioned further.
    """
