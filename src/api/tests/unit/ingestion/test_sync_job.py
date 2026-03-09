"""Unit tests for SyncJob aggregate (AIHCM-176).

SyncJob is the primary aggregate in the Ingestion bounded context.
It represents the lifecycle of a single synchronization operation:
from creation through running to completion or failure.
"""

from __future__ import annotations

from datetime import datetime

import pytest

from ingestion.domain.aggregates.sync_job import SyncJob
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
from ingestion.domain.value_objects import SyncJobId, SyncJobStatus
from shared_kernel.datasource_types import DataSourceAdapterType


class TestSyncJobCreate:
    """Tests for SyncJob.create() factory method."""

    def test_create_sets_all_fields(self):
        """create() should set all fields correctly."""
        job = SyncJob.create(
            knowledge_graph_id="kg-123",
            data_source_id="ds-456",
            tenant_id="tenant-789",
            adapter_type=DataSourceAdapterType.GITHUB,
        )
        assert isinstance(job.id, SyncJobId)
        assert job.knowledge_graph_id == "kg-123"
        assert job.data_source_id == "ds-456"
        assert job.tenant_id == "tenant-789"
        assert job.adapter_type == DataSourceAdapterType.GITHUB
        assert job.status == SyncJobStatus.PENDING
        assert job.job_package_id is None
        assert job.error_message is None
        assert isinstance(job.created_at, datetime)
        assert isinstance(job.updated_at, datetime)
        assert job.created_at == job.updated_at

    def test_create_generates_unique_ids(self):
        """Each create() should generate a unique SyncJobId."""
        job1 = SyncJob.create(
            knowledge_graph_id="kg",
            data_source_id="ds",
            tenant_id="t",
            adapter_type=DataSourceAdapterType.GITHUB,
        )
        job2 = SyncJob.create(
            knowledge_graph_id="kg",
            data_source_id="ds",
            tenant_id="t",
            adapter_type=DataSourceAdapterType.GITHUB,
        )
        assert job1.id != job2.id

    def test_create_emits_sync_job_created_event(self):
        """create() should emit a SyncJobCreated event."""
        job = SyncJob.create(
            knowledge_graph_id="kg-1",
            data_source_id="ds-1",
            tenant_id="tenant-1",
            adapter_type=DataSourceAdapterType.GITHUB,
        )
        events = job.collect_events()
        assert len(events) == 1
        event = events[0]
        assert isinstance(event, SyncJobCreated)
        assert event.sync_job_id == job.id.value
        assert event.knowledge_graph_id == "kg-1"
        assert event.data_source_id == "ds-1"
        assert event.tenant_id == "tenant-1"
        assert event.adapter_type == DataSourceAdapterType.GITHUB
        assert isinstance(event.occurred_at, datetime)

    def test_collect_events_clears_pending(self):
        """collect_events() should clear the pending events list."""
        job = SyncJob.create(
            knowledge_graph_id="kg",
            data_source_id="ds",
            tenant_id="t",
            adapter_type=DataSourceAdapterType.GITHUB,
        )
        job.collect_events()
        assert job.collect_events() == []


class TestSyncJobStart:
    """Tests for SyncJob.start() method."""

    def _pending_job(self) -> SyncJob:
        job = SyncJob.create(
            knowledge_graph_id="kg",
            data_source_id="ds",
            tenant_id="t",
            adapter_type=DataSourceAdapterType.GITHUB,
        )
        job.collect_events()  # clear creation event
        return job

    def test_start_transitions_to_running(self):
        """start() should set status to RUNNING."""
        job = self._pending_job()
        job.start()
        assert job.status == SyncJobStatus.RUNNING

    def test_start_emits_sync_job_started_event(self):
        """start() should emit a SyncJobStarted event."""
        job = self._pending_job()
        job.start()
        events = job.collect_events()
        assert len(events) == 1
        assert isinstance(events[0], SyncJobStarted)
        assert events[0].sync_job_id == job.id.value

    def test_start_updates_updated_at(self):
        """start() should update the updated_at timestamp."""
        job = self._pending_job()
        before = job.updated_at
        job.start()
        assert job.updated_at >= before

    def test_start_from_non_pending_raises(self):
        """start() on a non-PENDING job should raise InvalidSyncJobTransitionError."""
        job = self._pending_job()
        job.start()
        job.collect_events()
        with pytest.raises(InvalidSyncJobTransitionError):
            job.start()


class TestSyncJobComplete:
    """Tests for SyncJob.complete() method."""

    def _running_job(self) -> SyncJob:
        job = SyncJob.create(
            knowledge_graph_id="kg",
            data_source_id="ds",
            tenant_id="t",
            adapter_type=DataSourceAdapterType.GITHUB,
        )
        job.collect_events()
        job.start()
        job.collect_events()
        return job

    def test_complete_transitions_to_completed(self):
        """complete() should set status to COMPLETED."""
        job = self._running_job()
        job.complete(job_package_id="pkg-001")
        assert job.status == SyncJobStatus.COMPLETED

    def test_complete_sets_job_package_id(self):
        """complete() should record the job_package_id."""
        job = self._running_job()
        job.complete(job_package_id="pkg-abc")
        assert job.job_package_id == "pkg-abc"

    def test_complete_emits_sync_job_completed_event(self):
        """complete() should emit a SyncJobCompleted event."""
        job = self._running_job()
        job.complete(job_package_id="pkg-001")
        events = job.collect_events()
        assert len(events) == 1
        assert isinstance(events[0], SyncJobCompleted)
        assert events[0].sync_job_id == job.id.value
        assert events[0].job_package_id == "pkg-001"

    def test_complete_from_non_running_raises(self):
        """complete() on a PENDING job should raise InvalidSyncJobTransitionError."""
        job = SyncJob.create(
            knowledge_graph_id="kg",
            data_source_id="ds",
            tenant_id="t",
            adapter_type=DataSourceAdapterType.GITHUB,
        )
        job.collect_events()
        with pytest.raises(InvalidSyncJobTransitionError):
            job.complete(job_package_id="pkg-001")

    def test_complete_again_raises(self):
        """complete() on an already COMPLETED job should raise SyncJobAlreadyTerminalError."""
        job = self._running_job()
        job.complete(job_package_id="pkg-001")
        job.collect_events()
        with pytest.raises(SyncJobAlreadyTerminalError):
            job.complete(job_package_id="pkg-002")


class TestSyncJobFail:
    """Tests for SyncJob.fail() method."""

    def _running_job(self) -> SyncJob:
        job = SyncJob.create(
            knowledge_graph_id="kg",
            data_source_id="ds",
            tenant_id="t",
            adapter_type=DataSourceAdapterType.GITHUB,
        )
        job.collect_events()
        job.start()
        job.collect_events()
        return job

    def test_fail_transitions_to_failed(self):
        """fail() should set status to FAILED."""
        job = self._running_job()
        job.fail(error_message="network timeout")
        assert job.status == SyncJobStatus.FAILED

    def test_fail_records_error_message(self):
        """fail() should record the error message."""
        job = self._running_job()
        job.fail(error_message="rate limit exceeded")
        assert job.error_message == "rate limit exceeded"

    def test_fail_emits_sync_job_failed_event(self):
        """fail() should emit a SyncJobFailed event."""
        job = self._running_job()
        job.fail(error_message="boom")
        events = job.collect_events()
        assert len(events) == 1
        assert isinstance(events[0], SyncJobFailed)
        assert events[0].sync_job_id == job.id.value
        assert events[0].error_message == "boom"

    def test_fail_on_pending_job_raises(self):
        """fail() on a PENDING job should raise InvalidSyncJobTransitionError."""
        job = SyncJob.create(
            knowledge_graph_id="kg",
            data_source_id="ds",
            tenant_id="t",
            adapter_type=DataSourceAdapterType.GITHUB,
        )
        job.collect_events()
        with pytest.raises(InvalidSyncJobTransitionError):
            job.fail(error_message="error")

    def test_fail_on_completed_raises(self):
        """fail() on a COMPLETED job should raise SyncJobAlreadyTerminalError."""
        job = self._running_job()
        job.complete(job_package_id="pkg-001")
        job.collect_events()
        with pytest.raises(SyncJobAlreadyTerminalError):
            job.fail(error_message="too late")
