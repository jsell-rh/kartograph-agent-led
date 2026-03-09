"""Unit tests for ManagementEventSerializer (TDD - tests first).

These tests verify that Management domain events are correctly serialized
and deserialized for outbox storage. Pattern follows IAM serializer tests.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime

import pytest

from management.domain.events import (
    DataSourceCreated,
    DataSourceDeleted,
    DataSourceSyncRequested,
    DataSourceUpdated,
    DomainEvent,
    KnowledgeGraphCreated,
    KnowledgeGraphDeleted,
    KnowledgeGraphUpdated,
)
from management.infrastructure.outbox.serializer import ManagementEventSerializer


TENANT_ID = "01ARZCX0P0HZGQP3MZXQQ0NNYY"
WORKSPACE_ID = "01ARZCX0P0HZGQP3MZXQQ0NNXX"
KG_ID = "01ARZCX0P0HZGQP3MZXQQ0NNZZ"
DS_ID = "01ARZCX0P0HZGQP3MZXQQ0NNWW"
OCCURRED_AT = datetime(2026, 1, 8, 12, 0, 0, tzinfo=UTC)
OCCURRED_AT_ISO = "2026-01-08T12:00:00+00:00"


class TestManagementEventSerializerSupportedEvents:
    """Tests for supported_event_types()."""

    def test_supports_all_management_domain_events(self) -> None:
        """Serializer should support all Management domain event types."""
        serializer = ManagementEventSerializer()
        supported = serializer.supported_event_types()

        assert "KnowledgeGraphCreated" in supported
        assert "KnowledgeGraphUpdated" in supported
        assert "KnowledgeGraphDeleted" in supported
        assert "DataSourceCreated" in supported
        assert "DataSourceUpdated" in supported
        assert "DataSourceDeleted" in supported
        assert "DataSourceSyncRequested" in supported

    def test_supported_event_types_returns_frozenset(self) -> None:
        serializer = ManagementEventSerializer()
        assert isinstance(serializer.supported_event_types(), frozenset)


class TestManagementEventSerializerSerialize:
    """Tests for serialize()."""

    def test_serializes_knowledge_graph_created(self) -> None:
        serializer = ManagementEventSerializer()
        event = KnowledgeGraphCreated(
            knowledge_graph_id=KG_ID,
            tenant_id=TENANT_ID,
            workspace_id=WORKSPACE_ID,
            name="My Graph",
            description="A test graph",
            occurred_at=OCCURRED_AT,
            created_by="user-abc",
        )

        payload = serializer.serialize(event)

        assert payload["knowledge_graph_id"] == KG_ID
        assert payload["tenant_id"] == TENANT_ID
        assert payload["workspace_id"] == WORKSPACE_ID
        assert payload["name"] == "My Graph"
        assert payload["description"] == "A test graph"
        assert payload["occurred_at"] == OCCURRED_AT_ISO
        assert payload["created_by"] == "user-abc"

    def test_serializes_knowledge_graph_created_without_created_by(self) -> None:
        serializer = ManagementEventSerializer()
        event = KnowledgeGraphCreated(
            knowledge_graph_id=KG_ID,
            tenant_id=TENANT_ID,
            workspace_id=WORKSPACE_ID,
            name="My Graph",
            description="A test graph",
            occurred_at=OCCURRED_AT,
        )

        payload = serializer.serialize(event)

        assert payload["created_by"] is None

    def test_serializes_knowledge_graph_updated(self) -> None:
        serializer = ManagementEventSerializer()
        event = KnowledgeGraphUpdated(
            knowledge_graph_id=KG_ID,
            tenant_id=TENANT_ID,
            name="Updated Graph",
            description="New description",
            occurred_at=OCCURRED_AT,
            updated_by="user-xyz",
        )

        payload = serializer.serialize(event)

        assert payload["knowledge_graph_id"] == KG_ID
        assert payload["tenant_id"] == TENANT_ID
        assert payload["name"] == "Updated Graph"
        assert payload["description"] == "New description"
        assert payload["occurred_at"] == OCCURRED_AT_ISO
        assert payload["updated_by"] == "user-xyz"

    def test_serializes_knowledge_graph_deleted(self) -> None:
        serializer = ManagementEventSerializer()
        event = KnowledgeGraphDeleted(
            knowledge_graph_id=KG_ID,
            tenant_id=TENANT_ID,
            workspace_id=WORKSPACE_ID,
            occurred_at=OCCURRED_AT,
            deleted_by="user-del",
        )

        payload = serializer.serialize(event)

        assert payload["knowledge_graph_id"] == KG_ID
        assert payload["tenant_id"] == TENANT_ID
        assert payload["workspace_id"] == WORKSPACE_ID
        assert payload["occurred_at"] == OCCURRED_AT_ISO
        assert payload["deleted_by"] == "user-del"

    def test_serializes_data_source_created(self) -> None:
        serializer = ManagementEventSerializer()
        event = DataSourceCreated(
            data_source_id=DS_ID,
            knowledge_graph_id=KG_ID,
            tenant_id=TENANT_ID,
            name="GitHub Source",
            adapter_type="github",
            occurred_at=OCCURRED_AT,
            created_by="user-abc",
        )

        payload = serializer.serialize(event)

        assert payload["data_source_id"] == DS_ID
        assert payload["knowledge_graph_id"] == KG_ID
        assert payload["tenant_id"] == TENANT_ID
        assert payload["name"] == "GitHub Source"
        assert payload["adapter_type"] == "github"
        assert payload["occurred_at"] == OCCURRED_AT_ISO
        assert payload["created_by"] == "user-abc"

    def test_serializes_data_source_updated(self) -> None:
        serializer = ManagementEventSerializer()
        event = DataSourceUpdated(
            data_source_id=DS_ID,
            knowledge_graph_id=KG_ID,
            tenant_id=TENANT_ID,
            name="Updated Source",
            occurred_at=OCCURRED_AT,
        )

        payload = serializer.serialize(event)

        assert payload["data_source_id"] == DS_ID
        assert payload["knowledge_graph_id"] == KG_ID
        assert payload["name"] == "Updated Source"
        assert payload["occurred_at"] == OCCURRED_AT_ISO

    def test_serializes_data_source_deleted(self) -> None:
        serializer = ManagementEventSerializer()
        event = DataSourceDeleted(
            data_source_id=DS_ID,
            knowledge_graph_id=KG_ID,
            tenant_id=TENANT_ID,
            occurred_at=OCCURRED_AT,
        )

        payload = serializer.serialize(event)

        assert payload["data_source_id"] == DS_ID
        assert payload["knowledge_graph_id"] == KG_ID
        assert payload["tenant_id"] == TENANT_ID
        assert payload["occurred_at"] == OCCURRED_AT_ISO

    def test_serializes_data_source_sync_requested(self) -> None:
        serializer = ManagementEventSerializer()
        event = DataSourceSyncRequested(
            data_source_id=DS_ID,
            knowledge_graph_id=KG_ID,
            tenant_id=TENANT_ID,
            occurred_at=OCCURRED_AT,
            requested_by="user-req",
        )

        payload = serializer.serialize(event)

        assert payload["data_source_id"] == DS_ID
        assert payload["knowledge_graph_id"] == KG_ID
        assert payload["tenant_id"] == TENANT_ID
        assert payload["occurred_at"] == OCCURRED_AT_ISO
        assert payload["requested_by"] == "user-req"

    def test_payload_is_json_serializable(self) -> None:
        serializer = ManagementEventSerializer()
        event = KnowledgeGraphCreated(
            knowledge_graph_id=KG_ID,
            tenant_id=TENANT_ID,
            workspace_id=WORKSPACE_ID,
            name="My Graph",
            description="Test",
            occurred_at=OCCURRED_AT,
        )

        payload = serializer.serialize(event)
        json_str = json.dumps(payload)

        assert isinstance(json_str, str)

    def test_raises_for_unsupported_event(self) -> None:
        from dataclasses import dataclass

        serializer = ManagementEventSerializer()

        @dataclass(frozen=True)
        class UnknownEvent:
            data: str

        with pytest.raises(ValueError, match="Unsupported event type"):
            serializer.serialize(UnknownEvent(data="test"))


class TestManagementEventSerializerDeserialize:
    """Tests for deserialize()."""

    def test_deserializes_knowledge_graph_created(self) -> None:
        serializer = ManagementEventSerializer()
        payload = {
            "knowledge_graph_id": KG_ID,
            "tenant_id": TENANT_ID,
            "workspace_id": WORKSPACE_ID,
            "name": "My Graph",
            "description": "A test graph",
            "occurred_at": OCCURRED_AT_ISO,
            "created_by": "user-abc",
        }

        event = serializer.deserialize("KnowledgeGraphCreated", payload)

        assert isinstance(event, KnowledgeGraphCreated)
        assert event.knowledge_graph_id == KG_ID
        assert event.tenant_id == TENANT_ID
        assert event.workspace_id == WORKSPACE_ID
        assert event.name == "My Graph"
        assert event.occurred_at == OCCURRED_AT
        assert event.created_by == "user-abc"

    def test_deserializes_knowledge_graph_updated(self) -> None:
        serializer = ManagementEventSerializer()
        payload = {
            "knowledge_graph_id": KG_ID,
            "tenant_id": TENANT_ID,
            "name": "Updated",
            "description": "Desc",
            "occurred_at": OCCURRED_AT_ISO,
            "updated_by": None,
        }

        event = serializer.deserialize("KnowledgeGraphUpdated", payload)

        assert isinstance(event, KnowledgeGraphUpdated)
        assert event.occurred_at == OCCURRED_AT

    def test_deserializes_knowledge_graph_deleted(self) -> None:
        serializer = ManagementEventSerializer()
        payload = {
            "knowledge_graph_id": KG_ID,
            "tenant_id": TENANT_ID,
            "workspace_id": WORKSPACE_ID,
            "occurred_at": OCCURRED_AT_ISO,
            "deleted_by": None,
        }

        event = serializer.deserialize("KnowledgeGraphDeleted", payload)

        assert isinstance(event, KnowledgeGraphDeleted)
        assert event.workspace_id == WORKSPACE_ID

    def test_deserializes_data_source_created(self) -> None:
        serializer = ManagementEventSerializer()
        payload = {
            "data_source_id": DS_ID,
            "knowledge_graph_id": KG_ID,
            "tenant_id": TENANT_ID,
            "name": "GitHub Source",
            "adapter_type": "github",
            "occurred_at": OCCURRED_AT_ISO,
            "created_by": None,
        }

        event = serializer.deserialize("DataSourceCreated", payload)

        assert isinstance(event, DataSourceCreated)
        assert event.data_source_id == DS_ID
        assert event.adapter_type == "github"
        assert event.occurred_at == OCCURRED_AT

    def test_deserializes_data_source_sync_requested(self) -> None:
        serializer = ManagementEventSerializer()
        payload = {
            "data_source_id": DS_ID,
            "knowledge_graph_id": KG_ID,
            "tenant_id": TENANT_ID,
            "occurred_at": OCCURRED_AT_ISO,
            "requested_by": "user-req",
        }

        event = serializer.deserialize("DataSourceSyncRequested", payload)

        assert isinstance(event, DataSourceSyncRequested)
        assert event.requested_by == "user-req"

    def test_raises_for_unknown_event_type(self) -> None:
        serializer = ManagementEventSerializer()

        with pytest.raises(ValueError, match="Unsupported event type"):
            serializer.deserialize("UnknownEvent", {})


class TestManagementEventSerializerRoundTrip:
    """Test serialize -> deserialize round trip for all events."""

    def test_round_trip_knowledge_graph_created(self) -> None:
        serializer = ManagementEventSerializer()
        original = KnowledgeGraphCreated(
            knowledge_graph_id=KG_ID,
            tenant_id=TENANT_ID,
            workspace_id=WORKSPACE_ID,
            name="My Graph",
            description="Desc",
            occurred_at=OCCURRED_AT,
            created_by="user-abc",
        )

        payload = serializer.serialize(original)
        restored = serializer.deserialize("KnowledgeGraphCreated", payload)

        assert restored == original

    def test_round_trip_knowledge_graph_updated(self) -> None:
        serializer = ManagementEventSerializer()
        original = KnowledgeGraphUpdated(
            knowledge_graph_id=KG_ID,
            tenant_id=TENANT_ID,
            name="Updated",
            description="New desc",
            occurred_at=OCCURRED_AT,
        )

        payload = serializer.serialize(original)
        restored = serializer.deserialize("KnowledgeGraphUpdated", payload)

        assert restored == original

    def test_round_trip_knowledge_graph_deleted(self) -> None:
        serializer = ManagementEventSerializer()
        original = KnowledgeGraphDeleted(
            knowledge_graph_id=KG_ID,
            tenant_id=TENANT_ID,
            workspace_id=WORKSPACE_ID,
            occurred_at=OCCURRED_AT,
        )

        payload = serializer.serialize(original)
        restored = serializer.deserialize("KnowledgeGraphDeleted", payload)

        assert restored == original

    def test_round_trip_data_source_created(self) -> None:
        serializer = ManagementEventSerializer()
        original = DataSourceCreated(
            data_source_id=DS_ID,
            knowledge_graph_id=KG_ID,
            tenant_id=TENANT_ID,
            name="GitHub Source",
            adapter_type="github",
            occurred_at=OCCURRED_AT,
        )

        payload = serializer.serialize(original)
        restored = serializer.deserialize("DataSourceCreated", payload)

        assert restored == original

    def test_round_trip_data_source_updated(self) -> None:
        serializer = ManagementEventSerializer()
        original = DataSourceUpdated(
            data_source_id=DS_ID,
            knowledge_graph_id=KG_ID,
            tenant_id=TENANT_ID,
            name="Updated Source",
            occurred_at=OCCURRED_AT,
        )

        payload = serializer.serialize(original)
        restored = serializer.deserialize("DataSourceUpdated", payload)

        assert restored == original

    def test_round_trip_data_source_deleted(self) -> None:
        serializer = ManagementEventSerializer()
        original = DataSourceDeleted(
            data_source_id=DS_ID,
            knowledge_graph_id=KG_ID,
            tenant_id=TENANT_ID,
            occurred_at=OCCURRED_AT,
        )

        payload = serializer.serialize(original)
        restored = serializer.deserialize("DataSourceDeleted", payload)

        assert restored == original

    def test_round_trip_data_source_sync_requested(self) -> None:
        serializer = ManagementEventSerializer()
        original = DataSourceSyncRequested(
            data_source_id=DS_ID,
            knowledge_graph_id=KG_ID,
            tenant_id=TENANT_ID,
            occurred_at=OCCURRED_AT,
            requested_by="user-req",
        )

        payload = serializer.serialize(original)
        restored = serializer.deserialize("DataSourceSyncRequested", payload)

        assert restored == original

    def test_round_trip_all_events(self) -> None:
        """All event types should round trip correctly."""
        serializer = ManagementEventSerializer()
        events: list[DomainEvent] = [
            KnowledgeGraphCreated(
                knowledge_graph_id=KG_ID,
                tenant_id=TENANT_ID,
                workspace_id=WORKSPACE_ID,
                name="Graph",
                description="Desc",
                occurred_at=OCCURRED_AT,
            ),
            KnowledgeGraphUpdated(
                knowledge_graph_id=KG_ID,
                tenant_id=TENANT_ID,
                name="Graph",
                description="Desc",
                occurred_at=OCCURRED_AT,
            ),
            KnowledgeGraphDeleted(
                knowledge_graph_id=KG_ID,
                tenant_id=TENANT_ID,
                workspace_id=WORKSPACE_ID,
                occurred_at=OCCURRED_AT,
            ),
            DataSourceCreated(
                data_source_id=DS_ID,
                knowledge_graph_id=KG_ID,
                tenant_id=TENANT_ID,
                name="Source",
                adapter_type="github",
                occurred_at=OCCURRED_AT,
            ),
            DataSourceUpdated(
                data_source_id=DS_ID,
                knowledge_graph_id=KG_ID,
                tenant_id=TENANT_ID,
                name="Source",
                occurred_at=OCCURRED_AT,
            ),
            DataSourceDeleted(
                data_source_id=DS_ID,
                knowledge_graph_id=KG_ID,
                tenant_id=TENANT_ID,
                occurred_at=OCCURRED_AT,
            ),
            DataSourceSyncRequested(
                data_source_id=DS_ID,
                knowledge_graph_id=KG_ID,
                tenant_id=TENANT_ID,
                occurred_at=OCCURRED_AT,
            ),
        ]

        for original in events:
            event_type = type(original).__name__
            payload = serializer.serialize(original)
            restored = serializer.deserialize(event_type, payload)
            assert restored == original, f"Round trip failed for {event_type}"
