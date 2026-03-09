"""Unit tests for JobPackage shared kernel artifact (AIHCM-173).

The JobPackage is the output contract of the Ingestion bounded context
and the input contract for the Extraction bounded context. It lives in
the shared_kernel so both contexts can reference it without coupling.
"""

from __future__ import annotations

import io
import zipfile
from datetime import datetime

import pytest

from shared_kernel.datasource_types import DataSourceAdapterType
from shared_kernel.job_package import (
    ChangeOperation,
    JobPackage,
    JobPackageId,
    ManifestEntry,
    SyncManifest,
)


class TestJobPackageId:
    """Tests for JobPackageId value object."""

    def test_generate_creates_valid_ulid(self):
        """generate() should produce a valid ULID-based ID."""
        pkg_id = JobPackageId.generate()
        assert isinstance(pkg_id.value, str)
        assert len(pkg_id.value) > 0

    def test_generate_creates_unique_ids(self):
        """Each generate() call should produce a unique ID."""
        ids = {JobPackageId.generate().value for _ in range(100)}
        assert len(ids) == 100

    def test_from_string_roundtrips(self):
        """from_string(id.value) should reconstruct the same ID."""
        original = JobPackageId.generate()
        restored = JobPackageId.from_string(original.value)
        assert restored == original

    def test_str_returns_value(self):
        """str() should return the underlying value."""
        pkg_id = JobPackageId.generate()
        assert str(pkg_id) == pkg_id.value

    def test_equality_is_value_based(self):
        """Two IDs with same value should be equal."""
        val = JobPackageId.generate().value
        assert JobPackageId(value=val) == JobPackageId(value=val)


class TestChangeOperation:
    """Tests for ChangeOperation enum."""

    def test_has_add_update_delete(self):
        """ChangeOperation must include ADD, UPDATE, DELETE."""
        assert ChangeOperation.ADD == "add"
        assert ChangeOperation.UPDATE == "update"
        assert ChangeOperation.DELETE == "delete"

    def test_is_string_enum(self):
        """ChangeOperation values should be usable as strings."""
        assert str(ChangeOperation.ADD) == "add"


class TestManifestEntry:
    """Tests for ManifestEntry value object."""

    def test_create_with_all_fields(self):
        """ManifestEntry should store path, operation, and content_hash."""
        entry = ManifestEntry(
            path="src/main.py",
            operation=ChangeOperation.UPDATE,
            content_hash="abc123",
        )
        assert entry.path == "src/main.py"
        assert entry.operation == ChangeOperation.UPDATE
        assert entry.content_hash == "abc123"

    def test_delete_entry_has_no_content_hash(self):
        """DELETE entries should allow None content_hash (file is gone)."""
        entry = ManifestEntry(
            path="src/old.py",
            operation=ChangeOperation.DELETE,
            content_hash=None,
        )
        assert entry.content_hash is None

    def test_is_immutable(self):
        """ManifestEntry should be immutable (frozen dataclass)."""
        entry = ManifestEntry(
            path="f.py", operation=ChangeOperation.ADD, content_hash="h"
        )
        with pytest.raises((AttributeError, TypeError)):
            entry.path = "other.py"  # type: ignore[misc]

    def test_equality_is_value_based(self):
        """Two entries with same fields should be equal."""
        e1 = ManifestEntry(
            path="a.py", operation=ChangeOperation.ADD, content_hash="h1"
        )
        e2 = ManifestEntry(
            path="a.py", operation=ChangeOperation.ADD, content_hash="h1"
        )
        assert e1 == e2


class TestSyncManifest:
    """Tests for SyncManifest value object."""

    def test_create_with_entries(self):
        """SyncManifest should hold a list of ManifestEntry objects."""
        entries = [
            ManifestEntry(
                path="a.py", operation=ChangeOperation.ADD, content_hash="h1"
            ),
            ManifestEntry(
                path="b.py", operation=ChangeOperation.DELETE, content_hash=None
            ),
        ]
        manifest = SyncManifest(entries=entries)
        assert len(manifest.entries) == 2

    def test_empty_manifest_is_valid(self):
        """An empty manifest (no changes) is valid."""
        manifest = SyncManifest(entries=[])
        assert manifest.entries == []

    def test_to_json_produces_valid_json(self):
        """to_json() should produce a JSON string representing the manifest."""
        import json

        entries = [
            ManifestEntry(
                path="src/app.py", operation=ChangeOperation.UPDATE, content_hash="xyz"
            ),
        ]
        manifest = SyncManifest(entries=entries)
        json_str = manifest.to_json()
        parsed = json.loads(json_str)
        assert "entries" in parsed
        assert len(parsed["entries"]) == 1
        assert parsed["entries"][0]["path"] == "src/app.py"
        assert parsed["entries"][0]["operation"] == "update"
        assert parsed["entries"][0]["content_hash"] == "xyz"

    def test_from_json_roundtrips(self):
        """from_json(manifest.to_json()) should reproduce the manifest."""
        entries = [
            ManifestEntry(
                path="a.py", operation=ChangeOperation.ADD, content_hash="h1"
            ),
            ManifestEntry(
                path="b.py", operation=ChangeOperation.DELETE, content_hash=None
            ),
        ]
        original = SyncManifest(entries=entries)
        restored = SyncManifest.from_json(original.to_json())
        assert restored == original

    def test_counts_by_operation(self):
        """counts_by_operation() should return counts per ChangeOperation."""
        entries = [
            ManifestEntry(
                path="a.py", operation=ChangeOperation.ADD, content_hash="h1"
            ),
            ManifestEntry(
                path="b.py", operation=ChangeOperation.ADD, content_hash="h2"
            ),
            ManifestEntry(
                path="c.py", operation=ChangeOperation.DELETE, content_hash=None
            ),
        ]
        manifest = SyncManifest(entries=entries)
        counts = manifest.counts_by_operation()
        assert counts[ChangeOperation.ADD] == 2
        assert counts[ChangeOperation.DELETE] == 1
        assert counts.get(ChangeOperation.UPDATE, 0) == 0


class TestJobPackage:
    """Tests for JobPackage domain object."""

    def _make_manifest(self) -> SyncManifest:
        return SyncManifest(
            entries=[
                ManifestEntry(
                    path="README.md",
                    operation=ChangeOperation.UPDATE,
                    content_hash="abc",
                ),
            ]
        )

    def test_create_sets_all_fields(self):
        """create() factory method should set all fields correctly."""
        manifest = self._make_manifest()
        pkg = JobPackage.create(
            knowledge_graph_id="kg-123",
            data_source_id="ds-456",
            tenant_id="tenant-789",
            adapter_type=DataSourceAdapterType.GITHUB,
            manifest=manifest,
        )
        assert isinstance(pkg.id, JobPackageId)
        assert pkg.knowledge_graph_id == "kg-123"
        assert pkg.data_source_id == "ds-456"
        assert pkg.tenant_id == "tenant-789"
        assert pkg.adapter_type == DataSourceAdapterType.GITHUB
        assert pkg.manifest == manifest
        assert isinstance(pkg.created_at, datetime)

    def test_create_generates_unique_ids(self):
        """Each create() call should generate a unique ID."""
        manifest = self._make_manifest()
        pkg1 = JobPackage.create(
            knowledge_graph_id="kg",
            data_source_id="ds",
            tenant_id="t",
            adapter_type=DataSourceAdapterType.GITHUB,
            manifest=manifest,
        )
        pkg2 = JobPackage.create(
            knowledge_graph_id="kg",
            data_source_id="ds",
            tenant_id="t",
            adapter_type=DataSourceAdapterType.GITHUB,
            manifest=manifest,
        )
        assert pkg1.id != pkg2.id

    def test_to_zip_produces_valid_zip(self):
        """to_zip() should produce a valid zip archive."""
        manifest = self._make_manifest()
        pkg = JobPackage.create(
            knowledge_graph_id="kg-123",
            data_source_id="ds-456",
            tenant_id="tenant-789",
            adapter_type=DataSourceAdapterType.GITHUB,
            manifest=manifest,
            raw_files={"README.md": b"# Hello"},
        )
        zip_bytes = pkg.to_zip()
        assert isinstance(zip_bytes, bytes)
        with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
            names = zf.namelist()
            assert "manifest.json" in names
            assert "README.md" in names

    def test_to_zip_includes_manifest_json(self):
        """The manifest.json in the zip should match the manifest."""
        import json

        manifest = self._make_manifest()
        pkg = JobPackage.create(
            knowledge_graph_id="kg",
            data_source_id="ds",
            tenant_id="t",
            adapter_type=DataSourceAdapterType.GITHUB,
            manifest=manifest,
        )
        zip_bytes = pkg.to_zip()
        with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
            manifest_json = json.loads(zf.read("manifest.json"))
        assert manifest_json["entries"][0]["path"] == "README.md"

    def test_from_zip_roundtrips(self):
        """from_zip(pkg.to_zip()) should reconstruct the package."""
        manifest = SyncManifest(
            entries=[
                ManifestEntry(
                    path="src/app.py", operation=ChangeOperation.ADD, content_hash="h1"
                ),
            ]
        )
        original = JobPackage.create(
            knowledge_graph_id="kg-1",
            data_source_id="ds-1",
            tenant_id="t-1",
            adapter_type=DataSourceAdapterType.GITHUB,
            manifest=manifest,
            raw_files={"src/app.py": b"print('hello')"},
        )
        zip_bytes = original.to_zip()
        restored = JobPackage.from_zip(zip_bytes)
        assert restored.id == original.id
        assert restored.knowledge_graph_id == "kg-1"
        assert restored.data_source_id == "ds-1"
        assert restored.tenant_id == "t-1"
        assert restored.adapter_type == DataSourceAdapterType.GITHUB
        assert restored.manifest == original.manifest
        assert restored.raw_files.get("src/app.py") == b"print('hello')"

    def test_empty_raw_files_is_valid(self):
        """A JobPackage with no raw files (e.g., all deletes) is valid."""
        manifest = SyncManifest(
            entries=[
                ManifestEntry(
                    path="old.py", operation=ChangeOperation.DELETE, content_hash=None
                ),
            ]
        )
        pkg = JobPackage.create(
            knowledge_graph_id="kg",
            data_source_id="ds",
            tenant_id="t",
            adapter_type=DataSourceAdapterType.GITHUB,
            manifest=manifest,
            raw_files={},
        )
        zip_bytes = pkg.to_zip()
        with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
            assert "manifest.json" in zf.namelist()
