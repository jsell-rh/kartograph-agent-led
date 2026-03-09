"""Unit tests for KnowledgeGraph scoping in graph mutation routes."""

from __future__ import annotations

from unittest.mock import Mock

import pytest
from fastapi import status
from fastapi.testclient import TestClient

from graph.domain.value_objects import MutationResult
from iam.application.value_objects import CurrentUser
from iam.domain.value_objects import TenantId, UserId


@pytest.fixture
def mock_mutation_service():
    svc = Mock()
    svc.apply_mutations_from_jsonl.return_value = MutationResult(
        success=True, operations_applied=1
    )
    return svc


@pytest.fixture
def mock_query_service():
    return Mock()


@pytest.fixture
def mock_current_user():
    return CurrentUser(
        user_id=UserId(value="test-user-123"),
        username="testuser",
        tenant_id=TenantId.generate(),
    )


@pytest.fixture
def test_client(mock_mutation_service, mock_query_service, mock_current_user):
    from fastapi import FastAPI

    from graph import dependencies
    from graph.presentation import routes
    from iam.dependencies.user import get_current_user

    app = FastAPI()
    app.dependency_overrides[dependencies.get_graph_mutation_service] = (
        lambda: mock_mutation_service
    )
    app.dependency_overrides[dependencies.get_graph_query_service] = (
        lambda: mock_query_service
    )
    app.dependency_overrides[get_current_user] = lambda: mock_current_user
    app.include_router(routes.router)
    return TestClient(app)


SAMPLE_JSONL = '{"op": "CREATE", "type": "node", "id": "person:abc123", "label": "person", "set_properties": {"slug": "alice", "name": "Alice", "data_source_id": "ds-1", "source_path": "a.md"}}'


class TestMutationsKGScopingHeader:
    """Ensure knowledge_graph_id query param is accepted on /graph/mutations."""

    def test_accepts_knowledge_graph_id_query_param(
        self, test_client, mock_mutation_service
    ):
        """Should accept and process request with knowledge_graph_id query param."""
        response = test_client.post(
            "/graph/mutations?knowledge_graph_id=01KGID00000000000000000001",
            content=SAMPLE_JSONL,
            headers={"Content-Type": "application/jsonlines"},
        )
        assert response.status_code == status.HTTP_200_OK

    def test_works_without_knowledge_graph_id(self, test_client, mock_mutation_service):
        """Should work without knowledge_graph_id (uses default graph)."""
        response = test_client.post(
            "/graph/mutations",
            content=SAMPLE_JSONL,
            headers={"Content-Type": "application/jsonlines"},
        )
        assert response.status_code == status.HTTP_200_OK
