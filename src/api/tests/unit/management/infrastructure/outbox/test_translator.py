"""Unit tests for ManagementEventTranslator (TDD - tests first).

These tests verify that Management domain events are correctly translated
to SpiceDB relationship operations. Pattern follows IAM translator tests.

SpiceDB schema for Management:
- knowledge_graph#workspace@workspace
- knowledge_graph#tenant@tenant
- data_source#knowledge_graph@knowledge_graph
- data_source#tenant@tenant
"""

from __future__ import annotations


import pytest

from management.infrastructure.outbox.translator import ManagementEventTranslator
from shared_kernel.authorization.types import RelationType, ResourceType
from shared_kernel.outbox.operations import (
    DeleteRelationship,
    DeleteRelationshipsByFilter,
    WriteRelationship,
)


TENANT_ID = "01ARZCX0P0HZGQP3MZXQQ0NNYY"
WORKSPACE_ID = "01ARZCX0P0HZGQP3MZXQQ0NNXX"
CREATOR_ID = "01ARZCX0P0HZGQP3MZXQQ0NNCC"
KG_ID = "01ARZCX0P0HZGQP3MZXQQ0NNZZ"
DS_ID = "01ARZCX0P0HZGQP3MZXQQ0NNWW"
OCCURRED_AT_ISO = "2026-01-08T12:00:00+00:00"


class TestManagementEventTranslatorInit:
    """Tests for translator initialization and validation."""

    def test_instantiates_successfully(self) -> None:
        """Translator should instantiate without error."""
        translator = ManagementEventTranslator()
        assert translator is not None

    def test_supported_event_types_covers_all_management_events(self) -> None:
        """Translator must handle all management domain events."""
        translator = ManagementEventTranslator()
        supported = translator.supported_event_types()

        assert "KnowledgeGraphCreated" in supported
        assert "KnowledgeGraphUpdated" in supported
        assert "KnowledgeGraphDeleted" in supported
        assert "DataSourceCreated" in supported
        assert "DataSourceUpdated" in supported
        assert "DataSourceDeleted" in supported
        assert "DataSourceSyncRequested" in supported

    def test_raises_for_unknown_event_type(self) -> None:
        translator = ManagementEventTranslator()

        with pytest.raises(ValueError, match="Unknown event type"):
            translator.translate("UnknownEvent", {})


class TestKnowledgeGraphCreatedTranslation:
    """Tests for KnowledgeGraphCreated → SpiceDB operations."""

    def test_writes_workspace_and_tenant_relationships(self) -> None:
        """KnowledgeGraphCreated should write workspace and tenant relationships."""
        translator = ManagementEventTranslator()
        payload = {
            "knowledge_graph_id": KG_ID,
            "tenant_id": TENANT_ID,
            "workspace_id": WORKSPACE_ID,
            "name": "My Graph",
            "description": "Test",
            "occurred_at": OCCURRED_AT_ISO,
        }

        ops = translator.translate("KnowledgeGraphCreated", payload)

        assert len(ops) == 2
        writes = [op for op in ops if isinstance(op, WriteRelationship)]
        assert len(writes) == 2

    def test_writes_workspace_relation(self) -> None:
        translator = ManagementEventTranslator()
        payload = {
            "knowledge_graph_id": KG_ID,
            "tenant_id": TENANT_ID,
            "workspace_id": WORKSPACE_ID,
            "name": "Graph",
            "description": "",
            "occurred_at": OCCURRED_AT_ISO,
        }

        ops = translator.translate("KnowledgeGraphCreated", payload)

        workspace_op = next(
            op
            for op in ops
            if isinstance(op, WriteRelationship)
            and op.relation == RelationType.WORKSPACE
        )
        assert workspace_op.resource_type == ResourceType.KNOWLEDGE_GRAPH
        assert workspace_op.resource_id == KG_ID
        assert workspace_op.subject_type == ResourceType.WORKSPACE
        assert workspace_op.subject_id == WORKSPACE_ID

    def test_writes_tenant_relation(self) -> None:
        translator = ManagementEventTranslator()
        payload = {
            "knowledge_graph_id": KG_ID,
            "tenant_id": TENANT_ID,
            "workspace_id": WORKSPACE_ID,
            "name": "Graph",
            "description": "",
            "occurred_at": OCCURRED_AT_ISO,
        }

        ops = translator.translate("KnowledgeGraphCreated", payload)

        tenant_op = next(
            op
            for op in ops
            if isinstance(op, WriteRelationship) and op.relation == RelationType.TENANT
        )
        assert tenant_op.resource_type == ResourceType.KNOWLEDGE_GRAPH
        assert tenant_op.resource_id == KG_ID
        assert tenant_op.subject_type == ResourceType.TENANT
        assert tenant_op.subject_id == TENANT_ID

    def test_writes_creator_admin_relationship_when_created_by_set(self) -> None:
        """KnowledgeGraphCreated with created_by should write ADMIN relationship for creator."""
        translator = ManagementEventTranslator()
        payload = {
            "knowledge_graph_id": KG_ID,
            "tenant_id": TENANT_ID,
            "workspace_id": WORKSPACE_ID,
            "name": "Graph",
            "description": "",
            "occurred_at": OCCURRED_AT_ISO,
            "created_by": CREATOR_ID,
        }

        ops = translator.translate("KnowledgeGraphCreated", payload)

        admin_op = next(
            (
                op
                for op in ops
                if isinstance(op, WriteRelationship)
                and op.relation == RelationType.ADMIN
            ),
            None,
        )
        assert admin_op is not None
        assert admin_op.resource_type == ResourceType.KNOWLEDGE_GRAPH
        assert admin_op.resource_id == KG_ID
        assert admin_op.subject_type == ResourceType.USER
        assert admin_op.subject_id == CREATOR_ID

    def test_writes_three_ops_when_created_by_set(self) -> None:
        """Should produce workspace + tenant + creator-admin when created_by is present."""
        translator = ManagementEventTranslator()
        payload = {
            "knowledge_graph_id": KG_ID,
            "tenant_id": TENANT_ID,
            "workspace_id": WORKSPACE_ID,
            "name": "Graph",
            "description": "",
            "occurred_at": OCCURRED_AT_ISO,
            "created_by": CREATOR_ID,
        }

        ops = translator.translate("KnowledgeGraphCreated", payload)

        assert len(ops) == 3

    def test_omits_admin_when_created_by_absent(self) -> None:
        """Should only write workspace + tenant when created_by is not in payload."""
        translator = ManagementEventTranslator()
        payload = {
            "knowledge_graph_id": KG_ID,
            "tenant_id": TENANT_ID,
            "workspace_id": WORKSPACE_ID,
            "name": "Graph",
            "description": "",
            "occurred_at": OCCURRED_AT_ISO,
        }

        ops = translator.translate("KnowledgeGraphCreated", payload)

        assert len(ops) == 2
        assert not any(
            isinstance(op, WriteRelationship) and op.relation == RelationType.ADMIN
            for op in ops
        )

    def test_omits_admin_when_created_by_is_none(self) -> None:
        """Should only write workspace + tenant when created_by is explicitly None."""
        translator = ManagementEventTranslator()
        payload = {
            "knowledge_graph_id": KG_ID,
            "tenant_id": TENANT_ID,
            "workspace_id": WORKSPACE_ID,
            "name": "Graph",
            "description": "",
            "occurred_at": OCCURRED_AT_ISO,
            "created_by": None,
        }

        ops = translator.translate("KnowledgeGraphCreated", payload)

        assert len(ops) == 2
        assert not any(
            isinstance(op, WriteRelationship) and op.relation == RelationType.ADMIN
            for op in ops
        )


class TestKnowledgeGraphUpdatedTranslation:
    """Tests for KnowledgeGraphUpdated → SpiceDB operations."""

    def test_returns_no_spicedb_operations(self) -> None:
        """KnowledgeGraphUpdated is a metadata-only change; no SpiceDB ops needed."""
        translator = ManagementEventTranslator()
        payload = {
            "knowledge_graph_id": KG_ID,
            "tenant_id": TENANT_ID,
            "name": "New Name",
            "description": "New desc",
            "occurred_at": OCCURRED_AT_ISO,
        }

        ops = translator.translate("KnowledgeGraphUpdated", payload)

        assert ops == []


class TestKnowledgeGraphDeletedTranslation:
    """Tests for KnowledgeGraphDeleted → SpiceDB operations."""

    def test_deletes_workspace_and_tenant_relationships(self) -> None:
        translator = ManagementEventTranslator()
        payload = {
            "knowledge_graph_id": KG_ID,
            "tenant_id": TENANT_ID,
            "workspace_id": WORKSPACE_ID,
            "occurred_at": OCCURRED_AT_ISO,
        }

        ops = translator.translate("KnowledgeGraphDeleted", payload)

        assert len(ops) == 3
        deletes = [op for op in ops if isinstance(op, DeleteRelationship)]
        assert len(deletes) == 2

    def test_deletes_admin_relationships_by_filter(self) -> None:
        """KnowledgeGraphDeleted should clean up all admin grants via filter."""
        translator = ManagementEventTranslator()
        payload = {
            "knowledge_graph_id": KG_ID,
            "tenant_id": TENANT_ID,
            "workspace_id": WORKSPACE_ID,
            "occurred_at": OCCURRED_AT_ISO,
        }

        ops = translator.translate("KnowledgeGraphDeleted", payload)

        admin_filter = next(
            (
                op
                for op in ops
                if isinstance(op, DeleteRelationshipsByFilter)
                and op.relation == RelationType.ADMIN
            ),
            None,
        )
        assert admin_filter is not None
        assert admin_filter.resource_type == ResourceType.KNOWLEDGE_GRAPH
        assert admin_filter.resource_id == KG_ID

    def test_deletes_workspace_relation(self) -> None:
        translator = ManagementEventTranslator()
        payload = {
            "knowledge_graph_id": KG_ID,
            "tenant_id": TENANT_ID,
            "workspace_id": WORKSPACE_ID,
            "occurred_at": OCCURRED_AT_ISO,
        }

        ops = translator.translate("KnowledgeGraphDeleted", payload)

        workspace_op = next(
            op
            for op in ops
            if isinstance(op, DeleteRelationship)
            and op.relation == RelationType.WORKSPACE
        )
        assert workspace_op.resource_type == ResourceType.KNOWLEDGE_GRAPH
        assert workspace_op.resource_id == KG_ID
        assert workspace_op.subject_type == ResourceType.WORKSPACE
        assert workspace_op.subject_id == WORKSPACE_ID

    def test_deletes_tenant_relation(self) -> None:
        translator = ManagementEventTranslator()
        payload = {
            "knowledge_graph_id": KG_ID,
            "tenant_id": TENANT_ID,
            "workspace_id": WORKSPACE_ID,
            "occurred_at": OCCURRED_AT_ISO,
        }

        ops = translator.translate("KnowledgeGraphDeleted", payload)

        tenant_op = next(
            op
            for op in ops
            if isinstance(op, DeleteRelationship) and op.relation == RelationType.TENANT
        )
        assert tenant_op.resource_type == ResourceType.KNOWLEDGE_GRAPH
        assert tenant_op.resource_id == KG_ID
        assert tenant_op.subject_type == ResourceType.TENANT
        assert tenant_op.subject_id == TENANT_ID


class TestDataSourceCreatedTranslation:
    """Tests for DataSourceCreated → SpiceDB operations."""

    def test_writes_knowledge_graph_and_tenant_relationships(self) -> None:
        translator = ManagementEventTranslator()
        payload = {
            "data_source_id": DS_ID,
            "knowledge_graph_id": KG_ID,
            "tenant_id": TENANT_ID,
            "name": "GitHub Source",
            "adapter_type": "github",
            "occurred_at": OCCURRED_AT_ISO,
        }

        ops = translator.translate("DataSourceCreated", payload)

        assert len(ops) == 2
        writes = [op for op in ops if isinstance(op, WriteRelationship)]
        assert len(writes) == 2

    def test_writes_knowledge_graph_relation(self) -> None:
        translator = ManagementEventTranslator()
        payload = {
            "data_source_id": DS_ID,
            "knowledge_graph_id": KG_ID,
            "tenant_id": TENANT_ID,
            "name": "GitHub Source",
            "adapter_type": "github",
            "occurred_at": OCCURRED_AT_ISO,
        }

        ops = translator.translate("DataSourceCreated", payload)

        kg_op = next(
            op
            for op in ops
            if isinstance(op, WriteRelationship)
            and op.relation == RelationType.KNOWLEDGE_GRAPH
        )
        assert kg_op.resource_type == ResourceType.DATA_SOURCE
        assert kg_op.resource_id == DS_ID
        assert kg_op.subject_type == ResourceType.KNOWLEDGE_GRAPH
        assert kg_op.subject_id == KG_ID

    def test_writes_tenant_relation(self) -> None:
        translator = ManagementEventTranslator()
        payload = {
            "data_source_id": DS_ID,
            "knowledge_graph_id": KG_ID,
            "tenant_id": TENANT_ID,
            "name": "GitHub Source",
            "adapter_type": "github",
            "occurred_at": OCCURRED_AT_ISO,
        }

        ops = translator.translate("DataSourceCreated", payload)

        tenant_op = next(
            op
            for op in ops
            if isinstance(op, WriteRelationship) and op.relation == RelationType.TENANT
        )
        assert tenant_op.resource_type == ResourceType.DATA_SOURCE
        assert tenant_op.resource_id == DS_ID
        assert tenant_op.subject_type == ResourceType.TENANT
        assert tenant_op.subject_id == TENANT_ID


class TestDataSourceUpdatedTranslation:
    """Tests for DataSourceUpdated → SpiceDB operations."""

    def test_returns_no_spicedb_operations(self) -> None:
        """DataSourceUpdated is metadata-only; no SpiceDB relationship changes."""
        translator = ManagementEventTranslator()
        payload = {
            "data_source_id": DS_ID,
            "knowledge_graph_id": KG_ID,
            "tenant_id": TENANT_ID,
            "name": "Updated Name",
            "occurred_at": OCCURRED_AT_ISO,
        }

        ops = translator.translate("DataSourceUpdated", payload)

        assert ops == []


class TestDataSourceDeletedTranslation:
    """Tests for DataSourceDeleted → SpiceDB operations."""

    def test_deletes_knowledge_graph_and_tenant_relationships(self) -> None:
        translator = ManagementEventTranslator()
        payload = {
            "data_source_id": DS_ID,
            "knowledge_graph_id": KG_ID,
            "tenant_id": TENANT_ID,
            "occurred_at": OCCURRED_AT_ISO,
        }

        ops = translator.translate("DataSourceDeleted", payload)

        assert len(ops) == 2
        deletes = [op for op in ops if isinstance(op, DeleteRelationship)]
        assert len(deletes) == 2

    def test_deletes_knowledge_graph_relation(self) -> None:
        translator = ManagementEventTranslator()
        payload = {
            "data_source_id": DS_ID,
            "knowledge_graph_id": KG_ID,
            "tenant_id": TENANT_ID,
            "occurred_at": OCCURRED_AT_ISO,
        }

        ops = translator.translate("DataSourceDeleted", payload)

        kg_op = next(
            op
            for op in ops
            if isinstance(op, DeleteRelationship)
            and op.relation == RelationType.KNOWLEDGE_GRAPH
        )
        assert kg_op.resource_type == ResourceType.DATA_SOURCE
        assert kg_op.resource_id == DS_ID
        assert kg_op.subject_type == ResourceType.KNOWLEDGE_GRAPH
        assert kg_op.subject_id == KG_ID

    def test_deletes_tenant_relation(self) -> None:
        translator = ManagementEventTranslator()
        payload = {
            "data_source_id": DS_ID,
            "knowledge_graph_id": KG_ID,
            "tenant_id": TENANT_ID,
            "occurred_at": OCCURRED_AT_ISO,
        }

        ops = translator.translate("DataSourceDeleted", payload)

        tenant_op = next(
            op
            for op in ops
            if isinstance(op, DeleteRelationship) and op.relation == RelationType.TENANT
        )
        assert tenant_op.resource_type == ResourceType.DATA_SOURCE
        assert tenant_op.resource_id == DS_ID
        assert tenant_op.subject_type == ResourceType.TENANT
        assert tenant_op.subject_id == TENANT_ID


class TestDataSourceSyncRequestedTranslation:
    """Tests for DataSourceSyncRequested → SpiceDB operations."""

    def test_returns_no_spicedb_operations(self) -> None:
        """DataSourceSyncRequested triggers ingestion; no SpiceDB changes."""
        translator = ManagementEventTranslator()
        payload = {
            "data_source_id": DS_ID,
            "knowledge_graph_id": KG_ID,
            "tenant_id": TENANT_ID,
            "occurred_at": OCCURRED_AT_ISO,
            "requested_by": None,
        }

        ops = translator.translate("DataSourceSyncRequested", payload)

        assert ops == []
