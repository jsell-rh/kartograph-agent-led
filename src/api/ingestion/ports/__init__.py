"""Port definitions (interfaces) for the Ingestion bounded context."""

from ingestion.ports.adapters import IIngestionAdapter, IngestionChangeset
from ingestion.ports.repositories import ISyncJobRepository

__all__ = ["IIngestionAdapter", "IngestionChangeset", "ISyncJobRepository"]
