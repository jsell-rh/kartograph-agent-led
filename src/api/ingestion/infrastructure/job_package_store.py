"""In-memory JobPackage store for development use.

Implements the IJobPackageStore protocol from SyncService.
Data is held in a module-level dict and does NOT persist across
server restarts.

Replace with an object-storage-backed implementation (e.g., S3, GCS,
or a DB BLOB column) once durability is required.
"""

from __future__ import annotations

from ulid import ULID

from shared_kernel.job_package import JobPackage

# Module-level store shared across all worker iterations
_store: dict[str, JobPackage] = {}


class InMemoryJobPackageStore:
    """In-memory implementation of the IJobPackageStore protocol.

    Satisfies the IJobPackageStore port required by SyncService.
    Packages are keyed by a generated ULID string.
    """

    async def store(self, package: JobPackage) -> str:
        """Persist a JobPackage and return its ID."""
        pkg_id = str(ULID())
        _store[pkg_id] = package
        return pkg_id

    async def load(self, pkg_id: str) -> JobPackage | None:
        """Retrieve a previously stored JobPackage by ID."""
        return _store.get(pkg_id)
