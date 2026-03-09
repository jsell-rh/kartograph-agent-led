"""Unit tests for Ingestion domain value objects (AIHCM-176)."""

from __future__ import annotations

import pytest
from ulid import ULID

from ingestion.domain.value_objects import SyncJobId, SyncJobStatus


class TestSyncJobId:
    """Tests for SyncJobId value object."""

    def test_generate_creates_valid_ulid(self):
        """generate() should produce a valid ULID string."""
        job_id = SyncJobId.generate()
        assert isinstance(job_id.value, str)
        ULID.from_str(job_id.value)  # Should not raise

    def test_generate_creates_unique_ids(self):
        """Each call to generate() should produce a unique ID."""
        ids = {SyncJobId.generate().value for _ in range(100)}
        assert len(ids) == 100

    def test_from_string_roundtrips(self):
        """from_string(id.value) should reconstruct the same ID."""
        original = SyncJobId.generate()
        restored = SyncJobId.from_string(original.value)
        assert restored == original

    def test_from_string_rejects_invalid_ulid(self):
        """from_string() with invalid ULID should raise ValueError."""
        with pytest.raises(ValueError, match="Invalid"):
            SyncJobId.from_string("not-a-ulid")

    def test_str_returns_value(self):
        """str() should return the underlying ULID value."""
        job_id = SyncJobId.generate()
        assert str(job_id) == job_id.value

    def test_equality_is_value_based(self):
        """Two IDs with same value should be equal."""
        val = SyncJobId.generate().value
        assert SyncJobId(value=val) == SyncJobId(value=val)

    def test_is_immutable(self):
        """SyncJobId should be immutable."""
        job_id = SyncJobId.generate()
        with pytest.raises((AttributeError, TypeError)):
            job_id.value = "new-value"  # type: ignore[misc]


class TestSyncJobStatus:
    """Tests for SyncJobStatus enum."""

    def test_has_expected_statuses(self):
        """SyncJobStatus must include PENDING, RUNNING, COMPLETED, FAILED."""
        assert SyncJobStatus.PENDING == "pending"
        assert SyncJobStatus.RUNNING == "running"
        assert SyncJobStatus.COMPLETED == "completed"
        assert SyncJobStatus.FAILED == "failed"

    def test_is_string_enum(self):
        """SyncJobStatus values should be usable as strings."""
        assert str(SyncJobStatus.PENDING) == "pending"
