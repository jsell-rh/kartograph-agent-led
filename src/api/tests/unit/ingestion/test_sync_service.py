"""Unit tests for SyncService application service (AIHCM-178).

SyncService orchestrates the full ingestion lifecycle:
1. Create a SyncJob aggregate (PENDING)
2. Run the adapter to fetch changes
3. Package changes into a JobPackage
4. Persist the SyncJob (COMPLETED or FAILED)
5. Emit domain events via outbox for downstream contexts

All dependencies are mocked in unit tests.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from ingestion.application.services.sync_service import SyncService, SyncRequest
from ingestion.domain.value_objects import SyncJobStatus
from ingestion.ports.adapters import ChangesetEntry, IngestionChangeset
from shared_kernel.datasource_types import DataSourceAdapterType
from shared_kernel.job_package import ChangeOperation


def _make_service() -> tuple[SyncService, MagicMock, MagicMock]:
    """Create SyncService with mocked dependencies."""
    mock_repo = AsyncMock()
    mock_job_package_store = AsyncMock()
    service = SyncService(
        sync_job_repository=mock_repo,
        job_package_store=mock_job_package_store,
    )
    return service, mock_repo, mock_job_package_store


class TestSyncServiceRun:
    """Tests for SyncService.run() method."""

    @pytest.mark.asyncio
    async def test_run_creates_and_completes_sync_job(self):
        """run() should create a SyncJob, run adapter, and mark COMPLETED."""
        service, mock_repo, mock_store = _make_service()

        changeset = IngestionChangeset(
            entries=[
                ChangesetEntry.from_content(
                    "README.md", ChangeOperation.ADD, b"# Hello"
                ),
            ],
            next_cursor="sha_new",
        )
        mock_adapter = AsyncMock()
        mock_adapter.fetch_changeset = AsyncMock(return_value=changeset)
        mock_store.store = AsyncMock(return_value="pkg-001")

        request = SyncRequest(
            knowledge_graph_id="kg-1",
            data_source_id="ds-1",
            tenant_id="t-1",
            adapter_type=DataSourceAdapterType.GITHUB,
            adapter=mock_adapter,
            since_cursor=None,
        )
        result = await service.run(request)

        assert result.status == SyncJobStatus.COMPLETED
        assert result.job_package_id is not None
        # Verify job was saved at least twice: once pending, once completed
        assert mock_repo.save.call_count >= 2

    @pytest.mark.asyncio
    async def test_run_fails_sync_job_when_adapter_raises(self):
        """run() should mark SyncJob as FAILED when the adapter raises."""
        service, mock_repo, mock_store = _make_service()

        mock_adapter = AsyncMock()
        mock_adapter.fetch_changeset = AsyncMock(
            side_effect=RuntimeError("GitHub API rate limit exceeded")
        )

        request = SyncRequest(
            knowledge_graph_id="kg-1",
            data_source_id="ds-1",
            tenant_id="t-1",
            adapter_type=DataSourceAdapterType.GITHUB,
            adapter=mock_adapter,
            since_cursor=None,
        )
        result = await service.run(request)

        assert result.status == SyncJobStatus.FAILED
        assert result.error_message is not None
        assert (
            "rate limit" in result.error_message.lower()
            or "GitHub API" in result.error_message
        )

    @pytest.mark.asyncio
    async def test_run_passes_cursor_to_adapter(self):
        """run() should pass since_cursor to the adapter."""
        service, mock_repo, mock_store = _make_service()

        changeset = IngestionChangeset(entries=[], next_cursor="new_sha")
        mock_adapter = AsyncMock()
        mock_adapter.fetch_changeset = AsyncMock(return_value=changeset)
        mock_store.store = AsyncMock(return_value="pkg-002")

        request = SyncRequest(
            knowledge_graph_id="kg-1",
            data_source_id="ds-1",
            tenant_id="t-1",
            adapter_type=DataSourceAdapterType.GITHUB,
            adapter=mock_adapter,
            since_cursor="old_sha",
        )
        await service.run(request)

        mock_adapter.fetch_changeset.assert_called_once_with(since_cursor="old_sha")

    @pytest.mark.asyncio
    async def test_run_stores_job_package_with_changeset_data(self):
        """run() should store a JobPackage with the adapter's changeset data."""
        service, mock_repo, mock_store = _make_service()

        changeset = IngestionChangeset(
            entries=[
                ChangesetEntry.from_content(
                    "src/main.py", ChangeOperation.UPDATE, b"new code"
                ),
            ],
            next_cursor="abc",
        )
        mock_adapter = AsyncMock()
        mock_adapter.fetch_changeset = AsyncMock(return_value=changeset)
        mock_store.store = AsyncMock(return_value="pkg-003")

        request = SyncRequest(
            knowledge_graph_id="kg-99",
            data_source_id="ds-99",
            tenant_id="t-99",
            adapter_type=DataSourceAdapterType.GITHUB,
            adapter=mock_adapter,
            since_cursor=None,
        )
        await service.run(request)

        stored_pkg = mock_store.store.call_args[0][0]
        assert stored_pkg.knowledge_graph_id == "kg-99"
        assert stored_pkg.data_source_id == "ds-99"
        assert stored_pkg.tenant_id == "t-99"
        assert "src/main.py" in stored_pkg.raw_files


class TestSyncRequest:
    """Tests for SyncRequest data object."""

    def test_create_with_required_fields(self):
        """SyncRequest should store all required fields."""
        mock_adapter = MagicMock()
        req = SyncRequest(
            knowledge_graph_id="kg-1",
            data_source_id="ds-1",
            tenant_id="t-1",
            adapter_type=DataSourceAdapterType.GITHUB,
            adapter=mock_adapter,
            since_cursor="sha123",
        )
        assert req.knowledge_graph_id == "kg-1"
        assert req.since_cursor == "sha123"

    def test_since_cursor_defaults_to_none(self):
        """since_cursor should default to None for first sync."""
        mock_adapter = MagicMock()
        req = SyncRequest(
            knowledge_graph_id="kg",
            data_source_id="ds",
            tenant_id="t",
            adapter_type=DataSourceAdapterType.GITHUB,
            adapter=mock_adapter,
        )
        assert req.since_cursor is None
