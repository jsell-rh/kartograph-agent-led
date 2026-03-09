"""Adapter protocols (ports) for the Ingestion bounded context (AIHCM-176).

Defines the IIngestionAdapter protocol — the port that all data-source
adapters (GitHub, GitLab, Jira, etc.) must satisfy. Implementations
live in ingestion/infrastructure/adapters/.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable

from shared_kernel.job_package import ChangeOperation, ManifestEntry, SyncManifest


@dataclass
class ChangesetEntry:
    """A single file/resource change discovered by an adapter.

    Attributes:
        path: Relative path of the file within the repository/source
        operation: The type of change (ADD, UPDATE, DELETE)
        content: Raw file bytes, or None for DELETE entries
        content_hash: SHA-256 hex digest of content, or None for DELETE
    """

    path: str
    operation: ChangeOperation
    content: bytes | None
    content_hash: str | None

    @classmethod
    def from_content(
        cls,
        path: str,
        operation: ChangeOperation,
        content: bytes,
    ) -> ChangesetEntry:
        """Create a ChangesetEntry with auto-computed content hash.

        Args:
            path: File path
            operation: ADD or UPDATE
            content: Raw file bytes

        Returns:
            ChangesetEntry with SHA-256 hash computed
        """
        content_hash = hashlib.sha256(content).hexdigest()
        return cls(
            path=path, operation=operation, content=content, content_hash=content_hash
        )

    @classmethod
    def deleted(cls, path: str) -> ChangesetEntry:
        """Create a DELETE ChangesetEntry (no content)."""
        return cls(
            path=path, operation=ChangeOperation.DELETE, content=None, content_hash=None
        )


@dataclass
class IngestionChangeset:
    """The result of running an ingestion adapter.

    Contains all file changes discovered during a sync run and a
    cursor to use for the next incremental sync.

    Attributes:
        entries: Ordered list of ChangesetEntry objects
        next_cursor: Opaque cursor for the next incremental sync
                     (e.g., latest commit SHA for GitHub)
    """

    entries: list[ChangesetEntry] = field(default_factory=list)
    next_cursor: str = ""

    def to_manifest_and_raw_files(self) -> tuple[SyncManifest, dict[str, bytes]]:
        """Split the changeset into a SyncManifest and a raw-files dict.

        Returns:
            Tuple of (SyncManifest, raw_files) where raw_files maps
            file path → bytes for all non-DELETE entries.
        """
        manifest_entries: list[ManifestEntry] = []
        raw_files: dict[str, bytes] = {}

        for entry in self.entries:
            manifest_entries.append(
                ManifestEntry(
                    path=entry.path,
                    operation=entry.operation,
                    content_hash=entry.content_hash,
                )
            )
            if entry.content is not None:
                raw_files[entry.path] = entry.content

        return SyncManifest(entries=manifest_entries), raw_files


@runtime_checkable
class IIngestionAdapter(Protocol):
    """Protocol (port) that all data-source adapters must satisfy.

    Implementations live in ingestion/infrastructure/adapters/.
    Each implementation knows how to connect to a specific data source
    (GitHub, GitLab, Confluence, etc.) and fetch what changed.
    """

    async def fetch_changeset(
        self,
        *,
        since_cursor: str | None = None,
    ) -> IngestionChangeset:
        """Fetch all changes since the given cursor.

        Args:
            since_cursor: Opaque cursor from a previous sync run.
                          None means first sync — fetch the full current state.

        Returns:
            IngestionChangeset containing all detected changes and
            the next cursor to use for incremental syncs.
        """
        ...
