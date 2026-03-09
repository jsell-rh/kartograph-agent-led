"""JobPackage shared kernel artifact (AIHCM-173).

The JobPackage is the output contract of the Ingestion bounded context
and the input contract for the Extraction bounded context. It packages
raw content files and a sync manifest into a zip archive.

Both Ingestion (producer) and Extraction (consumer) reference this module,
which is why it belongs in the shared_kernel rather than either context.
"""

from __future__ import annotations

import io
import json
import zipfile
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import TypeVar

from ulid import ULID

from shared_kernel.datasource_types import DataSourceAdapterType

T = TypeVar("T", bound="JobPackageId")

_METADATA_FILENAME = "kartograph_meta.json"
_MANIFEST_FILENAME = "manifest.json"


@dataclass(frozen=True)
class JobPackageId:
    """Identifier for a JobPackage.

    Uses ULID for sortability and distribution-friendly generation.
    """

    value: str

    def __str__(self) -> str:
        return self.value

    @classmethod
    def generate(cls: type[T]) -> T:
        """Generate a new JobPackageId using ULID."""
        return cls(value=str(ULID()))

    @classmethod
    def from_string(cls: type[T], value: str) -> T:
        """Create a JobPackageId from a string.

        Args:
            value: ULID string

        Raises:
            ValueError: If value is not a valid ULID
        """
        try:
            ULID.from_str(value)
        except ValueError as e:
            raise ValueError(f"Invalid {cls.__name__}: {value}") from e
        return cls(value=value)


class ChangeOperation(StrEnum):
    """The type of change a file/resource underwent during ingestion.

    Drives downstream Extraction processing:
    - ADD / UPDATE: content is present in the archive; extract entities/relationships.
    - DELETE: resource was removed; issue delete operations in the graph.
    """

    ADD = "add"
    UPDATE = "update"
    DELETE = "delete"


@dataclass(frozen=True)
class ManifestEntry:
    """A single file/resource entry in the sync manifest.

    Attributes:
        path: Relative path of the file within the raw content archive
        operation: The type of change (ADD, UPDATE, DELETE)
        content_hash: SHA-256 hash of the file content, or None for DELETE entries
    """

    path: str
    operation: ChangeOperation
    content_hash: str | None

    def to_dict(self) -> dict:
        """Serialize to a plain dict for JSON encoding."""
        return {
            "path": self.path,
            "operation": str(self.operation),
            "content_hash": self.content_hash,
        }

    @classmethod
    def from_dict(cls, data: dict) -> ManifestEntry:
        """Deserialize from a plain dict."""
        return cls(
            path=data["path"],
            operation=ChangeOperation(data["operation"]),
            content_hash=data.get("content_hash"),
        )


@dataclass(frozen=True)
class SyncManifest:
    """Describes all changes discovered during a single sync run.

    The manifest lists every file/resource that was added, updated,
    or deleted since the last successful sync. It is stored as
    ``manifest.json`` inside the JobPackage zip archive.

    Attributes:
        entries: Ordered list of ManifestEntry objects
    """

    entries: list[ManifestEntry] = field(default_factory=list)

    def to_json(self) -> str:
        """Serialize the manifest to a JSON string."""
        return json.dumps(
            {"entries": [e.to_dict() for e in self.entries]},
            ensure_ascii=False,
            indent=2,
        )

    @classmethod
    def from_json(cls, json_str: str) -> SyncManifest:
        """Deserialize a manifest from a JSON string.

        Args:
            json_str: JSON produced by to_json()

        Returns:
            SyncManifest instance
        """
        data = json.loads(json_str)
        return cls(entries=[ManifestEntry.from_dict(e) for e in data["entries"]])

    def counts_by_operation(self) -> dict[ChangeOperation, int]:
        """Count entries grouped by ChangeOperation.

        Returns:
            Dict mapping each ChangeOperation to its entry count
        """
        result: dict[ChangeOperation, int] = {}
        for entry in self.entries:
            result[entry.operation] = result.get(entry.operation, 0) + 1
        return result

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, SyncManifest):
            return NotImplemented
        return self.entries == other.entries

    def __hash__(self) -> int:
        return hash(tuple(self.entries))


@dataclass
class JobPackage:
    """Packages raw content and a sync manifest for the Extraction context.

    A JobPackage is produced at the end of a successful ingestion run.
    It is serialized as a zip archive containing:
    - ``manifest.json``: the SyncManifest (what changed)
    - ``kartograph_meta.json``: package metadata (IDs, adapter type, timestamps)
    - One file per non-DELETE ManifestEntry: the raw file content

    The Extraction context reads JobPackages from object storage (or a
    similar staging area), processes the manifest entries, and produces
    a MutationLog of graph operations.

    Attributes:
        id: Unique identifier for this package
        knowledge_graph_id: The knowledge graph this package targets
        data_source_id: The data source that was ingested
        tenant_id: Tenant isolation boundary
        adapter_type: Which adapter produced the raw content
        manifest: What changed in this sync run
        raw_files: Raw content keyed by file path (empty for delete-only runs)
        created_at: When this package was created
    """

    id: JobPackageId
    knowledge_graph_id: str
    data_source_id: str
    tenant_id: str
    adapter_type: DataSourceAdapterType
    manifest: SyncManifest
    raw_files: dict[str, bytes] = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    @classmethod
    def create(
        cls,
        knowledge_graph_id: str,
        data_source_id: str,
        tenant_id: str,
        adapter_type: DataSourceAdapterType,
        manifest: SyncManifest,
        raw_files: dict[str, bytes] | None = None,
    ) -> JobPackage:
        """Factory method for creating a new JobPackage.

        Args:
            knowledge_graph_id: The knowledge graph this package targets
            data_source_id: The data source that was ingested
            tenant_id: Tenant isolation boundary
            adapter_type: Which adapter produced the raw content
            manifest: The sync manifest describing what changed
            raw_files: Raw file content keyed by relative path (optional)

        Returns:
            A new JobPackage with a generated ID and current timestamp
        """
        return cls(
            id=JobPackageId.generate(),
            knowledge_graph_id=knowledge_graph_id,
            data_source_id=data_source_id,
            tenant_id=tenant_id,
            adapter_type=adapter_type,
            manifest=manifest,
            raw_files=raw_files or {},
            created_at=datetime.now(UTC),
        )

    def to_zip(self) -> bytes:
        """Serialize the JobPackage as a zip archive.

        The archive contains:
        - ``kartograph_meta.json``: package metadata
        - ``manifest.json``: the sync manifest
        - One file per entry in ``raw_files``

        Returns:
            Bytes of the zip archive
        """
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
            # Write package metadata
            meta = {
                "id": self.id.value,
                "knowledge_graph_id": self.knowledge_graph_id,
                "data_source_id": self.data_source_id,
                "tenant_id": self.tenant_id,
                "adapter_type": str(self.adapter_type),
                "created_at": self.created_at.isoformat(),
            }
            zf.writestr(
                _METADATA_FILENAME, json.dumps(meta, ensure_ascii=False, indent=2)
            )

            # Write manifest
            zf.writestr(_MANIFEST_FILENAME, self.manifest.to_json())

            # Write raw file content
            for path, content in self.raw_files.items():
                zf.writestr(path, content)

        return buffer.getvalue()

    @classmethod
    def from_zip(cls, zip_bytes: bytes) -> JobPackage:
        """Deserialize a JobPackage from a zip archive produced by to_zip().

        Args:
            zip_bytes: Bytes of a zip archive produced by to_zip()

        Returns:
            JobPackage instance reconstructed from the archive
        """
        with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
            meta = json.loads(zf.read(_METADATA_FILENAME))
            manifest = SyncManifest.from_json(zf.read(_MANIFEST_FILENAME).decode())

            reserved = {_METADATA_FILENAME, _MANIFEST_FILENAME}
            raw_files = {
                name: zf.read(name) for name in zf.namelist() if name not in reserved
            }

        return cls(
            id=JobPackageId(value=meta["id"]),
            knowledge_graph_id=meta["knowledge_graph_id"],
            data_source_id=meta["data_source_id"],
            tenant_id=meta["tenant_id"],
            adapter_type=DataSourceAdapterType(meta["adapter_type"]),
            manifest=manifest,
            raw_files=raw_files,
            created_at=datetime.fromisoformat(meta["created_at"]),
        )
