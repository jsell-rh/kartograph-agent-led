"""Unit tests for GraphProvisioningHandler."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from graph.infrastructure.graph_provisioning_handler import (
    GraphProvisioningHandler,
    graph_name_for_kg,
)


class TestGraphNameForKg:
    """Tests for the graph_name_for_kg naming convention."""

    def test_prefixes_with_kg_underscore(self):
        assert graph_name_for_kg("01ABCDEFGHIJKLMNOPQRSTUV01").startswith("kg_")

    def test_lowercases_ulid(self):
        result = graph_name_for_kg("01ABCDEFGHIJKLMNOPQRSTUV01")
        assert result == "kg_01abcdefghijklmnopqrstuv01"

    def test_already_lowercase_unchanged(self):
        result = graph_name_for_kg("01abcdefghijklm")
        assert result == "kg_01abcdefghijklm"


class TestGraphProvisioningHandlerSupportedEventTypes:
    """Tests for supported_event_types."""

    def test_supports_knowledge_graph_created(self):
        handler = GraphProvisioningHandler(session_factory=MagicMock())
        assert "KnowledgeGraphCreated" in handler.supported_event_types()

    def test_supports_knowledge_graph_deleted(self):
        handler = GraphProvisioningHandler(session_factory=MagicMock())
        assert "KnowledgeGraphDeleted" in handler.supported_event_types()

    def test_does_not_support_other_events(self):
        handler = GraphProvisioningHandler(session_factory=MagicMock())
        assert "DataSourceCreated" not in handler.supported_event_types()
        assert "GroupCreated" not in handler.supported_event_types()


class TestGraphProvisioningHandlerHandle:
    """Tests for the handle method."""

    @pytest.fixture
    def mock_session_factory(self):
        """Mock async session factory with context manager support."""
        mock_session = AsyncMock()
        # scalar_one_or_none returns None by default (graph does not exist)
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_session.commit = AsyncMock()

        mock_factory = MagicMock()
        mock_factory.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_factory.return_value.__aexit__ = AsyncMock(return_value=False)
        return mock_factory, mock_session

    @pytest.mark.asyncio
    async def test_handles_knowledge_graph_created(self, mock_session_factory):
        """Should call create_graph when KnowledgeGraphCreated is received."""
        factory, session = mock_session_factory
        handler = GraphProvisioningHandler(session_factory=factory)

        await handler.handle(
            "KnowledgeGraphCreated",
            {
                "knowledge_graph_id": "01TESTID000000000000000001",
                "tenant_id": "tenant-123",
                "workspace_id": "ws-456",
                "name": "My KG",
                "description": "A test KG",
                "occurred_at": "2026-03-09T00:00:00Z",
            },
        )

        # Should have checked existence and created the graph
        assert session.execute.call_count == 2
        assert session.commit.call_count == 1

    @pytest.mark.asyncio
    async def test_does_not_create_if_graph_already_exists(self, mock_session_factory):
        """Should skip creation if AGE graph already exists (idempotent)."""
        factory, session = mock_session_factory
        # Simulate graph already exists
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = 1
        session.execute = AsyncMock(return_value=mock_result)

        handler = GraphProvisioningHandler(session_factory=factory)

        await handler.handle(
            "KnowledgeGraphCreated",
            {
                "knowledge_graph_id": "01TESTID000000000000000001",
                "tenant_id": "tenant-123",
                "workspace_id": "ws-456",
                "name": "My KG",
                "description": "A test KG",
                "occurred_at": "2026-03-09T00:00:00Z",
            },
        )

        # Only the existence check, no create_graph call
        assert session.execute.call_count == 1
        assert session.commit.call_count == 0

    @pytest.mark.asyncio
    async def test_uses_correct_graph_name_in_provisioning(self, mock_session_factory):
        """Should derive correct AGE graph name from knowledge_graph_id."""

        factory, session = mock_session_factory
        handler = GraphProvisioningHandler(session_factory=factory)

        kg_id = "01TESTID000000000000000002"
        await handler.handle(
            "KnowledgeGraphCreated",
            {
                "knowledge_graph_id": kg_id,
                "tenant_id": "tenant-abc",
                "workspace_id": "ws-xyz",
                "name": "KG2",
                "description": "",
                "occurred_at": "2026-03-09T00:00:00Z",
            },
        )

        # Second call should be the create_graph call
        second_call_args = session.execute.call_args_list[1]
        # The text() SQL and the params dict
        params = second_call_args[0][1]
        assert params["name"] == graph_name_for_kg(kg_id)

    @pytest.mark.asyncio
    async def test_ignores_unsupported_event_types(self, mock_session_factory):
        """Should be a no-op for unsupported event types."""
        factory, session = mock_session_factory
        handler = GraphProvisioningHandler(session_factory=factory)

        # No exception should be raised
        await handler.handle(
            "DataSourceCreated",
            {"data_source_id": "ds-1", "knowledge_graph_id": "kg-1"},
        )

        # No database calls
        session.execute.assert_not_called()

    @pytest.mark.asyncio
    async def test_handles_knowledge_graph_deleted(self, mock_session_factory):
        """Should call drop_graph when KnowledgeGraphDeleted is received."""
        factory, session = mock_session_factory
        # Graph exists
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = 1
        session.execute = AsyncMock(return_value=mock_result)

        handler = GraphProvisioningHandler(session_factory=factory)

        await handler.handle(
            "KnowledgeGraphDeleted",
            {
                "knowledge_graph_id": "01TESTID000000000000000001",
                "tenant_id": "tenant-123",
                "workspace_id": "ws-456",
                "occurred_at": "2026-03-10T00:00:00Z",
            },
        )

        # Should have checked existence and dropped the graph
        assert session.execute.call_count == 2
        assert session.commit.call_count == 1

    @pytest.mark.asyncio
    async def test_does_not_drop_if_graph_does_not_exist(self, mock_session_factory):
        """Should skip drop if AGE graph does not exist (idempotent)."""
        factory, session = mock_session_factory
        # Graph does not exist
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        session.execute = AsyncMock(return_value=mock_result)

        handler = GraphProvisioningHandler(session_factory=factory)

        await handler.handle(
            "KnowledgeGraphDeleted",
            {
                "knowledge_graph_id": "01TESTID000000000000000001",
                "tenant_id": "tenant-123",
                "workspace_id": "ws-456",
                "occurred_at": "2026-03-10T00:00:00Z",
            },
        )

        # Only existence check, no drop call
        assert session.execute.call_count == 1
        assert session.commit.call_count == 0
