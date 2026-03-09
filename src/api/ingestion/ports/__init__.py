"""Port definitions (interfaces) for the Ingestion bounded context."""

from ingestion.ports.repositories import ISyncJobRepository

__all__ = ["ISyncJobRepository"]
