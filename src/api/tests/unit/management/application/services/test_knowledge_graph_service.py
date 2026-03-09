"""Unit tests for KnowledgeGraphService application service."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from management.application.services.knowledge_graph_service import (
    KnowledgeGraphService,
)
from management.domain.aggregates import KnowledgeGraph
from management.domain.value_objects import KnowledgeGraphId
from management.ports.exceptions import (
    UnauthorizedError,
)


@pytest.fixture
def mock_session():
    return AsyncMock()


@pytest.fixture
def mock_kg_repository():
    return AsyncMock()


@pytest.fixture
def mock_authz():
    authz = AsyncMock()
    authz.check_permission = AsyncMock(return_value=True)
    return authz


@pytest.fixture
def tenant_id():
    return "tenant-abc"


@pytest.fixture
def user_id():
    return "user-xyz"


@pytest.fixture
def service(mock_session, mock_kg_repository, mock_authz, tenant_id):
    return KnowledgeGraphService(
        session=mock_session,
        kg_repository=mock_kg_repository,
        authz=mock_authz,
        tenant_id=tenant_id,
    )


class TestKnowledgeGraphServiceCreate:
    """Tests for create_knowledge_graph()."""

    @pytest.mark.asyncio
    async def test_create_returns_knowledge_graph(self, service, mock_kg_repository):
        """create_knowledge_graph() should return a KnowledgeGraph aggregate."""
        mock_session_ctx = AsyncMock()
        mock_session_ctx.__aenter__ = AsyncMock(return_value=None)
        mock_session_ctx.__aexit__ = AsyncMock(return_value=None)
        service._session.begin = MagicMock(return_value=mock_session_ctx)
        mock_kg_repository.save = AsyncMock()

        kg = await service.create_knowledge_graph(
            name="My KG",
            workspace_id="ws-1",
            created_by="user-xyz",
        )

        assert isinstance(kg, KnowledgeGraph)
        assert kg.name == "My KG"
        assert kg.workspace_id == "ws-1"
        assert kg.tenant_id == "tenant-abc"

    @pytest.mark.asyncio
    async def test_create_calls_repository_save(self, service, mock_kg_repository):
        """create_knowledge_graph() should call repository.save()."""
        mock_session_ctx = AsyncMock()
        mock_session_ctx.__aenter__ = AsyncMock(return_value=None)
        mock_session_ctx.__aexit__ = AsyncMock(return_value=None)
        service._session.begin = MagicMock(return_value=mock_session_ctx)
        mock_kg_repository.save = AsyncMock()

        await service.create_knowledge_graph(
            name="My KG",
            workspace_id="ws-1",
            created_by="user-xyz",
        )

        mock_kg_repository.save.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_with_description(self, service, mock_kg_repository):
        """create_knowledge_graph() should accept optional description."""
        mock_session_ctx = AsyncMock()
        mock_session_ctx.__aenter__ = AsyncMock(return_value=None)
        mock_session_ctx.__aexit__ = AsyncMock(return_value=None)
        service._session.begin = MagicMock(return_value=mock_session_ctx)
        mock_kg_repository.save = AsyncMock()

        kg = await service.create_knowledge_graph(
            name="My KG",
            workspace_id="ws-1",
            created_by="user-xyz",
            description="A test knowledge graph",
        )

        assert kg.description == "A test knowledge graph"


class TestKnowledgeGraphServiceGet:
    """Tests for get_knowledge_graph()."""

    @pytest.mark.asyncio
    async def test_get_returns_knowledge_graph(
        self, service, mock_kg_repository, mock_authz
    ):
        """get_knowledge_graph() should return a KnowledgeGraph when found."""
        kg_id = KnowledgeGraphId.generate()
        fake_kg = MagicMock(spec=KnowledgeGraph)
        fake_kg.id = kg_id
        fake_kg.tenant_id = "tenant-abc"
        mock_kg_repository.get_by_id = AsyncMock(return_value=fake_kg)
        mock_authz.check_permission = AsyncMock(return_value=True)

        result = await service.get_knowledge_graph(
            kg_id=kg_id.value, user_id="user-xyz"
        )
        assert result == fake_kg

    @pytest.mark.asyncio
    async def test_get_returns_none_when_not_found(self, service, mock_kg_repository):
        """get_knowledge_graph() should return None when not found."""
        mock_kg_repository.get_by_id = AsyncMock(return_value=None)

        result = await service.get_knowledge_graph(
            kg_id="nonexistent-id", user_id="user-xyz"
        )
        assert result is None

    @pytest.mark.asyncio
    async def test_get_raises_unauthorized_without_view_permission(
        self, service, mock_kg_repository, mock_authz
    ):
        """get_knowledge_graph() should raise UnauthorizedError if user lacks VIEW permission."""
        kg_id = KnowledgeGraphId.generate()
        fake_kg = MagicMock(spec=KnowledgeGraph)
        fake_kg.id = kg_id
        fake_kg.tenant_id = "tenant-abc"
        mock_kg_repository.get_by_id = AsyncMock(return_value=fake_kg)
        mock_authz.check_permission = AsyncMock(return_value=False)

        with pytest.raises(UnauthorizedError):
            await service.get_knowledge_graph(kg_id=kg_id.value, user_id="user-xyz")


class TestKnowledgeGraphServiceList:
    """Tests for list_knowledge_graphs()."""

    @pytest.mark.asyncio
    async def test_list_returns_knowledge_graphs(self, service, mock_kg_repository):
        """list_knowledge_graphs() should return a list of KnowledgeGraph."""
        fake_kgs = [MagicMock(spec=KnowledgeGraph) for _ in range(3)]
        mock_kg_repository.list_by_workspace = AsyncMock(return_value=fake_kgs)

        result = await service.list_knowledge_graphs(workspace_id="ws-1")
        assert result == fake_kgs
        mock_kg_repository.list_by_workspace.assert_called_once_with(
            workspace_id="ws-1", tenant_id="tenant-abc"
        )

    @pytest.mark.asyncio
    async def test_list_returns_empty_list_when_none(self, service, mock_kg_repository):
        """list_knowledge_graphs() should return [] when no KGs exist."""
        mock_kg_repository.list_by_workspace = AsyncMock(return_value=[])

        result = await service.list_knowledge_graphs(workspace_id="ws-1")
        assert result == []


class TestKnowledgeGraphServiceDelete:
    """Tests for delete_knowledge_graph()."""

    @pytest.mark.asyncio
    async def test_delete_calls_repository(
        self, service, mock_kg_repository, mock_authz
    ):
        """delete_knowledge_graph() should call repository.delete()."""
        kg_id = KnowledgeGraphId.generate()
        fake_kg = MagicMock(spec=KnowledgeGraph)
        fake_kg.id = kg_id
        fake_kg.tenant_id = "tenant-abc"
        mock_kg_repository.get_by_id = AsyncMock(return_value=fake_kg)
        mock_kg_repository.delete = AsyncMock(return_value=True)
        mock_authz.check_permission = AsyncMock(return_value=True)

        mock_session_ctx = AsyncMock()
        mock_session_ctx.__aenter__ = AsyncMock(return_value=None)
        mock_session_ctx.__aexit__ = AsyncMock(return_value=None)
        service._session.begin = MagicMock(return_value=mock_session_ctx)

        await service.delete_knowledge_graph(kg_id=kg_id.value, user_id="user-xyz")

        mock_kg_repository.delete.assert_called_once()

    @pytest.mark.asyncio
    async def test_delete_raises_unauthorized_without_manage_permission(
        self, service, mock_kg_repository, mock_authz
    ):
        """delete_knowledge_graph() should raise UnauthorizedError if user lacks MANAGE permission."""
        kg_id = KnowledgeGraphId.generate()
        fake_kg = MagicMock(spec=KnowledgeGraph)
        fake_kg.id = kg_id
        fake_kg.tenant_id = "tenant-abc"
        mock_kg_repository.get_by_id = AsyncMock(return_value=fake_kg)
        mock_authz.check_permission = AsyncMock(return_value=False)

        with pytest.raises(UnauthorizedError):
            await service.delete_knowledge_graph(kg_id=kg_id.value, user_id="user-xyz")

    @pytest.mark.asyncio
    async def test_delete_returns_none_when_not_found(
        self, service, mock_kg_repository
    ):
        """delete_knowledge_graph() should return without error when KG not found."""
        mock_kg_repository.get_by_id = AsyncMock(return_value=None)

        result = await service.delete_knowledge_graph(
            kg_id="nonexistent-id", user_id="user-xyz"
        )
        assert result is None
