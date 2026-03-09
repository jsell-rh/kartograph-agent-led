"""Unit tests for KnowledgeGraphRepository (TDD - tests first).

Tests verify repository behavior with mocked dependencies.
Management repositories are pure PostgreSQL (no SpiceDB hydration) —
authorization is enforced at the FastAPI layer via SpiceDB permission checks.
"""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from management.domain.aggregates import KnowledgeGraph
from management.domain.value_objects import KnowledgeGraphId
from management.infrastructure.knowledge_graph_repository import (
    KnowledgeGraphRepository,
)
from management.infrastructure.models.knowledge_graph import KnowledgeGraphModel
from management.ports.repositories import IKnowledgeGraphRepository


TENANT_ID = "01ARZCX0P0HZGQP3MZXQQ0NNYY"
WORKSPACE_ID = "01ARZCX0P0HZGQP3MZXQQ0NNXX"
KG_ID = "01ARZCX0P0HZGQP3MZXQQ0NNZZ"
NOW = datetime(2026, 1, 8, 12, 0, 0, tzinfo=UTC)


@pytest.fixture
def mock_session() -> AsyncMock:
    return AsyncMock()


@pytest.fixture
def mock_outbox() -> MagicMock:
    outbox = MagicMock()
    outbox.append = AsyncMock()
    return outbox


@pytest.fixture
def mock_serializer() -> MagicMock:
    serializer = MagicMock()
    serializer.serialize.return_value = {"event": "payload"}
    return serializer


@pytest.fixture
def repository(mock_session, mock_outbox, mock_serializer) -> KnowledgeGraphRepository:
    return KnowledgeGraphRepository(
        session=mock_session,
        outbox=mock_outbox,
        serializer=mock_serializer,
    )


@pytest.fixture
def knowledge_graph() -> KnowledgeGraph:
    return KnowledgeGraph.create(
        tenant_id=TENANT_ID,
        workspace_id=WORKSPACE_ID,
        name="Test Graph",
        description="A test knowledge graph",
    )


def make_kg_model(kg_id: str = KG_ID) -> KnowledgeGraphModel:
    model = KnowledgeGraphModel()
    model.id = kg_id
    model.tenant_id = TENANT_ID
    model.workspace_id = WORKSPACE_ID
    model.name = "Test Graph"
    model.description = "Desc"
    model.created_at = NOW
    model.updated_at = NOW
    return model


class TestProtocolCompliance:
    """Repository must implement IKnowledgeGraphRepository protocol."""

    def test_implements_protocol(self, repository: KnowledgeGraphRepository) -> None:
        assert isinstance(repository, IKnowledgeGraphRepository)


class TestSaveNew:
    """Tests for saving a new knowledge graph."""

    @pytest.mark.asyncio
    async def test_save_new_adds_model_to_session(
        self,
        repository: KnowledgeGraphRepository,
        mock_session: AsyncMock,
        knowledge_graph: KnowledgeGraph,
    ) -> None:
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        await repository.save(knowledge_graph)

        mock_session.add.assert_called_once()

    @pytest.mark.asyncio
    async def test_save_new_flushes_session(
        self,
        repository: KnowledgeGraphRepository,
        mock_session: AsyncMock,
        knowledge_graph: KnowledgeGraph,
    ) -> None:
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        await repository.save(knowledge_graph)

        mock_session.flush.assert_called_once()

    @pytest.mark.asyncio
    async def test_save_new_appends_events_to_outbox(
        self,
        repository: KnowledgeGraphRepository,
        mock_session: AsyncMock,
        mock_outbox: MagicMock,
        knowledge_graph: KnowledgeGraph,
    ) -> None:
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        await repository.save(knowledge_graph)

        # KnowledgeGraphCreated event should be appended
        mock_outbox.append.assert_called_once()
        call_kwargs = mock_outbox.append.call_args.kwargs
        assert call_kwargs["event_type"] == "KnowledgeGraphCreated"
        assert call_kwargs["aggregate_type"] == "knowledge_graph"

    @pytest.mark.asyncio
    async def test_save_new_clears_aggregate_events(
        self,
        repository: KnowledgeGraphRepository,
        mock_session: AsyncMock,
        knowledge_graph: KnowledgeGraph,
    ) -> None:
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        await repository.save(knowledge_graph)

        # Events should be collected (cleared) from aggregate
        remaining_events = knowledge_graph.collect_events()
        assert remaining_events == []


class TestSaveExisting:
    """Tests for updating an existing knowledge graph."""

    @pytest.mark.asyncio
    async def test_save_existing_updates_model_fields(
        self,
        repository: KnowledgeGraphRepository,
        mock_session: AsyncMock,
        knowledge_graph: KnowledgeGraph,
    ) -> None:
        existing_model = make_kg_model(knowledge_graph.id.value)
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = existing_model
        mock_session.execute.return_value = mock_result

        knowledge_graph.collect_events()  # Clear creation event
        knowledge_graph.update(name="New Name", description="New Desc")

        await repository.save(knowledge_graph)

        assert existing_model.name == "New Name"
        assert existing_model.description == "New Desc"
        mock_session.add.assert_not_called()

    @pytest.mark.asyncio
    async def test_save_existing_appends_update_event(
        self,
        repository: KnowledgeGraphRepository,
        mock_session: AsyncMock,
        mock_outbox: MagicMock,
        knowledge_graph: KnowledgeGraph,
    ) -> None:
        existing_model = make_kg_model(knowledge_graph.id.value)
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = existing_model
        mock_session.execute.return_value = mock_result

        knowledge_graph.collect_events()  # Clear creation event
        knowledge_graph.update(name="New Name", description="New Desc")

        await repository.save(knowledge_graph)

        mock_outbox.append.assert_called_once()
        call_kwargs = mock_outbox.append.call_args.kwargs
        assert call_kwargs["event_type"] == "KnowledgeGraphUpdated"


class TestGetById:
    """Tests for get_by_id method."""

    @pytest.mark.asyncio
    async def test_returns_knowledge_graph_when_found(
        self,
        repository: KnowledgeGraphRepository,
        mock_session: AsyncMock,
    ) -> None:
        model = make_kg_model()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = model
        mock_session.execute.return_value = mock_result

        result = await repository.get_by_id(KnowledgeGraphId(value=KG_ID))

        assert result is not None
        assert isinstance(result, KnowledgeGraph)
        assert result.id.value == KG_ID
        assert result.name == "Test Graph"
        assert result.tenant_id == TENANT_ID
        assert result.workspace_id == WORKSPACE_ID

    @pytest.mark.asyncio
    async def test_returns_none_when_not_found(
        self,
        repository: KnowledgeGraphRepository,
        mock_session: AsyncMock,
    ) -> None:
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        result = await repository.get_by_id(KnowledgeGraphId(value=KG_ID))

        assert result is None

    @pytest.mark.asyncio
    async def test_returned_aggregate_has_no_pending_events(
        self,
        repository: KnowledgeGraphRepository,
        mock_session: AsyncMock,
    ) -> None:
        model = make_kg_model()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = model
        mock_session.execute.return_value = mock_result

        kg = await repository.get_by_id(KnowledgeGraphId(value=KG_ID))

        assert kg is not None
        assert kg.collect_events() == []


class TestListByWorkspace:
    """Tests for list_by_workspace method."""

    @pytest.mark.asyncio
    async def test_returns_list_of_knowledge_graphs(
        self,
        repository: KnowledgeGraphRepository,
        mock_session: AsyncMock,
    ) -> None:
        model1 = make_kg_model("01ARZCX0P0HZGQP3MZXQQ0NNA1")
        model2 = make_kg_model("01ARZCX0P0HZGQP3MZXQQ0NNA2")
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = [model1, model2]
        mock_result = MagicMock()
        mock_result.scalars.return_value = mock_scalars
        mock_session.execute.return_value = mock_result

        results = await repository.list_by_workspace(
            workspace_id=WORKSPACE_ID, tenant_id=TENANT_ID
        )

        assert len(results) == 2
        assert all(isinstance(kg, KnowledgeGraph) for kg in results)

    @pytest.mark.asyncio
    async def test_returns_empty_list_when_none_found(
        self,
        repository: KnowledgeGraphRepository,
        mock_session: AsyncMock,
    ) -> None:
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = []
        mock_result = MagicMock()
        mock_result.scalars.return_value = mock_scalars
        mock_session.execute.return_value = mock_result

        results = await repository.list_by_workspace(
            workspace_id=WORKSPACE_ID, tenant_id=TENANT_ID
        )

        assert results == []


class TestDelete:
    """Tests for delete method."""

    @pytest.mark.asyncio
    async def test_delete_returns_true_when_found(
        self,
        repository: KnowledgeGraphRepository,
        mock_session: AsyncMock,
        mock_outbox: MagicMock,
        knowledge_graph: KnowledgeGraph,
    ) -> None:
        model = make_kg_model(knowledge_graph.id.value)
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = model
        mock_session.execute.return_value = mock_result

        knowledge_graph.collect_events()  # Clear creation event
        knowledge_graph.mark_for_deletion()

        result = await repository.delete(knowledge_graph)

        assert result is True
        mock_session.delete.assert_called_once_with(model)

    @pytest.mark.asyncio
    async def test_delete_appends_deleted_event_to_outbox(
        self,
        repository: KnowledgeGraphRepository,
        mock_session: AsyncMock,
        mock_outbox: MagicMock,
        knowledge_graph: KnowledgeGraph,
    ) -> None:
        model = make_kg_model(knowledge_graph.id.value)
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = model
        mock_session.execute.return_value = mock_result

        knowledge_graph.collect_events()
        knowledge_graph.mark_for_deletion()

        await repository.delete(knowledge_graph)

        mock_outbox.append.assert_called_once()
        call_kwargs = mock_outbox.append.call_args.kwargs
        assert call_kwargs["event_type"] == "KnowledgeGraphDeleted"

    @pytest.mark.asyncio
    async def test_delete_returns_false_when_not_found(
        self,
        repository: KnowledgeGraphRepository,
        mock_session: AsyncMock,
        knowledge_graph: KnowledgeGraph,
    ) -> None:
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        result = await repository.delete(knowledge_graph)

        assert result is False
        mock_session.delete.assert_not_called()
