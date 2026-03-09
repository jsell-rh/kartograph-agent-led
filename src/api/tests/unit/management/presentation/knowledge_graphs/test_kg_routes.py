"""Unit tests for KnowledgeGraph presentation routes."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from iam.application.value_objects import CurrentUser
from iam.dependencies.user import get_current_user
from iam.domain.value_objects import TenantId, UserId
from management.application.services.knowledge_graph_service import (
    KnowledgeGraphService,
)
from management.dependencies.services import get_kg_service
from management.domain.aggregates import KnowledgeGraph
from management.domain.value_objects import KnowledgeGraphId
from management.ports.exceptions import UnauthorizedError
from management.presentation.knowledge_graphs.routes import router


@pytest.fixture
def fake_kg():
    """Create a fake KnowledgeGraph aggregate for testing."""
    kg = MagicMock(spec=KnowledgeGraph)
    kg.id = KnowledgeGraphId.generate()
    kg.tenant_id = "tenant-1"
    kg.workspace_id = "ws-1"
    kg.name = "Test KG"
    kg.description = "A test knowledge graph"
    return kg


@pytest.fixture
def mock_service():
    """Create a mock KnowledgeGraphService."""
    return AsyncMock(spec=KnowledgeGraphService)


@pytest.fixture
def mock_current_user():
    """Create a mock CurrentUser for auth."""
    return CurrentUser(
        user_id=UserId(value="user-test"),
        username="testuser",
        tenant_id=TenantId.generate(),
    )


@pytest.fixture
def client(mock_service, mock_current_user):
    """Create test client with overridden service and auth dependencies."""
    test_app = FastAPI()
    test_app.include_router(router)
    test_app.dependency_overrides[get_kg_service] = lambda: mock_service
    test_app.dependency_overrides[get_current_user] = lambda: mock_current_user
    return TestClient(test_app)


class TestCreateKnowledgeGraph:
    """Tests for POST /knowledge-graphs."""

    def test_create_returns_201(self, client, mock_service, fake_kg):
        """POST should return 201 with created KG."""
        mock_service.create_knowledge_graph = AsyncMock(return_value=fake_kg)

        response = client.post(
            "/knowledge-graphs?workspace_id=ws-1",
            json={"name": "Test KG", "description": "A test knowledge graph"},
        )

        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "Test KG"
        assert data["workspace_id"] == "ws-1"

    def test_create_returns_500_on_error(self, client, mock_service):
        """POST should return 500 on unexpected error."""
        mock_service.create_knowledge_graph = AsyncMock(
            side_effect=RuntimeError("DB error")
        )

        response = client.post(
            "/knowledge-graphs?workspace_id=ws-1",
            json={"name": "Test KG"},
        )

        assert response.status_code == 500


class TestGetKnowledgeGraph:
    """Tests for GET /knowledge-graphs/{kg_id}."""

    def test_get_returns_200(self, client, mock_service, fake_kg):
        """GET should return 200 with KG details."""
        mock_service.get_knowledge_graph = AsyncMock(return_value=fake_kg)

        response = client.get(f"/knowledge-graphs/{fake_kg.id.value}")

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == fake_kg.id.value

    def test_get_returns_404_when_not_found(self, client, mock_service):
        """GET should return 404 when KG not found."""
        mock_service.get_knowledge_graph = AsyncMock(return_value=None)

        response = client.get("/knowledge-graphs/nonexistent-id")

        assert response.status_code == 404

    def test_get_returns_403_when_unauthorized(self, client, mock_service):
        """GET should return 403 when user lacks VIEW permission."""
        mock_service.get_knowledge_graph = AsyncMock(
            side_effect=UnauthorizedError("no permission")
        )

        response = client.get("/knowledge-graphs/some-id")

        assert response.status_code == 403


class TestListKnowledgeGraphs:
    """Tests for GET /knowledge-graphs."""

    def test_list_returns_200_with_kgs(self, client, mock_service, fake_kg):
        """GET /knowledge-graphs should return 200 with list of KGs."""
        mock_service.list_knowledge_graphs = AsyncMock(return_value=[fake_kg])

        response = client.get("/knowledge-graphs?workspace_id=ws-1")

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["name"] == "Test KG"

    def test_list_returns_empty_list(self, client, mock_service):
        """GET /knowledge-graphs should return 200 with empty list when no KGs."""
        mock_service.list_knowledge_graphs = AsyncMock(return_value=[])

        response = client.get("/knowledge-graphs?workspace_id=ws-1")

        assert response.status_code == 200
        assert response.json() == []


class TestDeleteKnowledgeGraph:
    """Tests for DELETE /knowledge-graphs/{kg_id}."""

    def test_delete_returns_204(self, client, mock_service):
        """DELETE should return 204 on successful deletion."""
        mock_service.delete_knowledge_graph = AsyncMock(return_value=True)

        response = client.delete("/knowledge-graphs/some-id")

        assert response.status_code == 204

    def test_delete_returns_404_when_not_found(self, client, mock_service):
        """DELETE should return 404 when KG not found."""
        mock_service.delete_knowledge_graph = AsyncMock(return_value=None)

        response = client.delete("/knowledge-graphs/nonexistent-id")

        assert response.status_code == 404

    def test_delete_returns_403_when_unauthorized(self, client, mock_service):
        """DELETE should return 403 when user lacks MANAGE permission."""
        mock_service.delete_knowledge_graph = AsyncMock(
            side_effect=UnauthorizedError("no permission")
        )

        response = client.delete("/knowledge-graphs/some-id")

        assert response.status_code == 403
