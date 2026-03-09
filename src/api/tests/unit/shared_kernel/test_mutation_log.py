"""Unit tests for MutationLog shared kernel artifact (AIHCM-139).

The MutationLog is the output contract of the Extraction bounded context.
It describes a sequence of graph mutations (node/edge upserts and deletes)
that the Graph context applies transactionally.

It lives in shared_kernel so both Extraction (producer) and Graph (consumer)
can reference it without coupling.
"""

from __future__ import annotations

import json

import pytest

from shared_kernel.mutation_log import (
    EdgeMutation,
    MutationLog,
    MutationLogId,
    MutationOperation,
    MutationRecord,
    NodeMutation,
)


class TestMutationLogId:
    """Tests for MutationLogId value object."""

    def test_generate_creates_unique_ids(self):
        """generate() should produce unique IDs."""
        ids = {MutationLogId.generate().value for _ in range(100)}
        assert len(ids) == 100

    def test_from_string_roundtrips(self):
        """from_string(id.value) should reconstruct the same ID."""
        original = MutationLogId.generate()
        restored = MutationLogId.from_string(original.value)
        assert restored == original

    def test_str_returns_value(self):
        """str() should return the underlying value."""
        log_id = MutationLogId.generate()
        assert str(log_id) == log_id.value


class TestMutationOperation:
    """Tests for MutationOperation enum."""

    def test_has_upsert_and_delete(self):
        """MutationOperation must include UPSERT and DELETE."""
        assert MutationOperation.UPSERT == "upsert"
        assert MutationOperation.DELETE == "delete"


class TestNodeMutation:
    """Tests for NodeMutation value object."""

    def test_create_upsert_node(self):
        """NodeMutation should store label, id, and properties."""
        node = NodeMutation(
            operation=MutationOperation.UPSERT,
            label="Function",
            node_id="func:main",
            properties={"name": "main", "file": "src/app.py", "line": 42},
        )
        assert node.label == "Function"
        assert node.node_id == "func:main"
        assert node.properties["name"] == "main"
        assert node.operation == MutationOperation.UPSERT

    def test_create_delete_node(self):
        """DELETE NodeMutation may have empty properties."""
        node = NodeMutation(
            operation=MutationOperation.DELETE,
            label="Function",
            node_id="func:old",
            properties={},
        )
        assert node.operation == MutationOperation.DELETE

    def test_is_immutable(self):
        """NodeMutation should be immutable."""
        node = NodeMutation(
            operation=MutationOperation.UPSERT,
            label="L",
            node_id="n1",
            properties={},
        )
        with pytest.raises((AttributeError, TypeError)):
            node.label = "Other"  # type: ignore[misc]

    def test_to_dict_roundtrips(self):
        """to_dict() / from_dict() should roundtrip."""
        node = NodeMutation(
            operation=MutationOperation.UPSERT,
            label="Module",
            node_id="mod:utils",
            properties={"path": "src/utils.py"},
        )
        restored = NodeMutation.from_dict(node.to_dict())
        assert restored == node


class TestEdgeMutation:
    """Tests for EdgeMutation value object."""

    def test_create_upsert_edge(self):
        """EdgeMutation should store relation, source, target, properties."""
        edge = EdgeMutation(
            operation=MutationOperation.UPSERT,
            relation="CALLS",
            source_id="func:main",
            target_id="func:helper",
            properties={"weight": 1},
        )
        assert edge.relation == "CALLS"
        assert edge.source_id == "func:main"
        assert edge.target_id == "func:helper"

    def test_to_dict_roundtrips(self):
        """to_dict() / from_dict() should roundtrip."""
        edge = EdgeMutation(
            operation=MutationOperation.UPSERT,
            relation="IMPORTS",
            source_id="mod:a",
            target_id="mod:b",
            properties={},
        )
        restored = EdgeMutation.from_dict(edge.to_dict())
        assert restored == edge


class TestMutationRecord:
    """Tests for MutationRecord (union of node or edge mutation)."""

    def test_node_record(self):
        """MutationRecord wrapping a NodeMutation should expose it correctly."""
        node = NodeMutation(
            operation=MutationOperation.UPSERT,
            label="Class",
            node_id="cls:Foo",
            properties={},
        )
        record = MutationRecord(mutation=node)
        assert record.is_node
        assert not record.is_edge
        assert record.as_node == node

    def test_edge_record(self):
        """MutationRecord wrapping an EdgeMutation should expose it correctly."""
        edge = EdgeMutation(
            operation=MutationOperation.UPSERT,
            relation="INHERITS",
            source_id="cls:Child",
            target_id="cls:Parent",
            properties={},
        )
        record = MutationRecord(mutation=edge)
        assert record.is_edge
        assert not record.is_node

    def test_to_dict_roundtrips_node(self):
        """to_dict() / from_dict() roundtrip for node record."""
        node = NodeMutation(
            operation=MutationOperation.UPSERT,
            label="File",
            node_id="file:main.py",
            properties={"path": "src/main.py"},
        )
        record = MutationRecord(mutation=node)
        restored = MutationRecord.from_dict(record.to_dict())
        assert restored.is_node
        assert restored.as_node == node

    def test_to_dict_roundtrips_edge(self):
        """to_dict() / from_dict() roundtrip for edge record."""
        edge = EdgeMutation(
            operation=MutationOperation.DELETE,
            relation="DEPENDS_ON",
            source_id="pkg:a",
            target_id="pkg:b",
            properties={},
        )
        record = MutationRecord(mutation=edge)
        restored = MutationRecord.from_dict(record.to_dict())
        assert restored.is_edge


class TestMutationLog:
    """Tests for MutationLog aggregate."""

    def _make_log(self) -> MutationLog:
        node = NodeMutation(
            operation=MutationOperation.UPSERT,
            label="Function",
            node_id="func:main",
            properties={"name": "main"},
        )
        edge = EdgeMutation(
            operation=MutationOperation.UPSERT,
            relation="CALLS",
            source_id="func:main",
            target_id="func:helper",
            properties={},
        )
        return MutationLog.create(
            job_package_id="pkg-001",
            knowledge_graph_id="kg-1",
            tenant_id="t-1",
            records=[MutationRecord(mutation=node), MutationRecord(mutation=edge)],
        )

    def test_create_sets_all_fields(self):
        """create() factory should set all fields correctly."""
        log = self._make_log()
        assert isinstance(log.id, MutationLogId)
        assert log.job_package_id == "pkg-001"
        assert log.knowledge_graph_id == "kg-1"
        assert log.tenant_id == "t-1"
        assert len(log.records) == 2

    def test_create_generates_unique_ids(self):
        """Each create() call should generate a unique ID."""
        log1 = self._make_log()
        log2 = self._make_log()
        assert log1.id != log2.id

    def test_node_count(self):
        """node_count() should count only NodeMutation records."""
        log = self._make_log()
        assert log.node_count == 1

    def test_edge_count(self):
        """edge_count() should count only EdgeMutation records."""
        log = self._make_log()
        assert log.edge_count == 1

    def test_to_jsonl_produces_valid_jsonl(self):
        """to_jsonl() should produce one JSON object per line."""
        log = self._make_log()
        jsonl = log.to_jsonl()
        lines = [line for line in jsonl.strip().split("\n") if line]
        assert len(lines) == 2
        for line in lines:
            json.loads(line)  # Should not raise

    def test_from_jsonl_roundtrips(self):
        """from_jsonl(log.to_jsonl()) should reconstruct the log."""
        original = self._make_log()
        jsonl = original.to_jsonl()
        restored = MutationLog.from_jsonl(
            jsonl,
            job_package_id=original.job_package_id,
            knowledge_graph_id=original.knowledge_graph_id,
            tenant_id=original.tenant_id,
            log_id=original.id.value,
        )
        assert restored.id == original.id
        assert len(restored.records) == 2
        assert restored.records[0].is_node
        assert restored.records[1].is_edge

    def test_empty_log_is_valid(self):
        """A MutationLog with no records is valid."""
        log = MutationLog.create(
            job_package_id="pkg-002",
            knowledge_graph_id="kg-1",
            tenant_id="t-1",
            records=[],
        )
        assert log.node_count == 0
        assert log.edge_count == 0
        assert log.to_jsonl() == ""
