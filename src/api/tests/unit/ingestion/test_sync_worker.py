"""Unit tests for sync worker internals.

Tests cover:
- _stable_id format matches ID_REGEX (regression: was producing non-matching IDs)
- _translate_mutation_log correctly maps shared-kernel mutations to graph operations
- InMemoryJobPackageStore store/load round-trip
"""

from __future__ import annotations

import re

import pytest

from extraction.infrastructure.agents.python_ast_agent import _stable_id
from graph.domain.value_objects import EntityType, ID_REGEX, MutationOperationType
from ingestion.infrastructure.job_package_store import InMemoryJobPackageStore
from ingestion.infrastructure.workers.sync_worker import _translate_mutation_log
from shared_kernel.mutation_log import (
    EdgeMutation,
    MutationLog,
    MutationOperation,
    MutationRecord,
    NodeMutation,
)


ID_PATTERN = re.compile(ID_REGEX)

KG_ID = "01ARZCX0P0HZGQP3MZXQQ0NNZZ"
DS_ID = "01ARZCX0P0HZGQP3MZXQQ0NNWW"
TENANT_ID = "01ARZCX0P0HZGQP3MZXQQ0NNYY"
PKG_ID = "01ARZCX0P0HZGQP3MZXQQ0NNPP"


class TestStableIdFormat:
    """Verify _stable_id output matches graph domain ID_REGEX."""

    def test_simple_prefix_matches_id_regex(self) -> None:
        node_id = _stable_id("mod", "src/main.py")
        assert ID_PATTERN.match(node_id), f"ID {node_id!r} does not match ID_REGEX"

    def test_multiple_parts_match_id_regex(self) -> None:
        node_id = _stable_id("cls", "src/service.py", "MyClass")
        assert ID_PATTERN.match(node_id), f"ID {node_id!r} does not match ID_REGEX"

    def test_fn_prefix_matches_id_regex(self) -> None:
        node_id = _stable_id("fn", "src/service.py", "MyClass", "my_method")
        assert ID_PATTERN.match(node_id), f"ID {node_id!r} does not match ID_REGEX"

    def test_file_prefix_matches_id_regex(self) -> None:
        node_id = _stable_id("file", "README.md")
        assert ID_PATTERN.match(node_id), f"ID {node_id!r} does not match ID_REGEX"

    def test_deterministic_for_same_input(self) -> None:
        id1 = _stable_id("mod", "src/main.py")
        id2 = _stable_id("mod", "src/main.py")
        assert id1 == id2

    def test_different_for_different_input(self) -> None:
        id1 = _stable_id("mod", "src/main.py")
        id2 = _stable_id("mod", "src/other.py")
        assert id1 != id2


class TestTranslateMutationLog:
    """Tests for _translate_mutation_log."""

    def _make_log(self, records: list[MutationRecord]) -> MutationLog:
        return MutationLog.create(
            job_package_id=PKG_ID,
            knowledge_graph_id=KG_ID,
            tenant_id=TENANT_ID,
            records=records,
        )

    def test_empty_log_returns_empty_list(self) -> None:
        log = self._make_log([])
        ops = _translate_mutation_log(log)
        assert ops == []

    def test_node_upsert_becomes_create(self) -> None:
        node_id = _stable_id("mod", "src/main.py")
        log = self._make_log(
            [
                MutationRecord(
                    mutation=NodeMutation(
                        operation=MutationOperation.UPSERT,
                        label="Module",
                        node_id=node_id,
                        properties={"path": "src/main.py"},
                    )
                )
            ]
        )

        ops = _translate_mutation_log(log)

        assert len(ops) == 1
        op = ops[0]
        assert op.op == MutationOperationType.CREATE
        assert op.type == EntityType.NODE
        assert op.id == node_id
        assert op.label == "Module"
        assert op.set_properties == {"path": "src/main.py"}

    def test_node_delete_becomes_delete(self) -> None:
        node_id = _stable_id("mod", "src/main.py")
        log = self._make_log(
            [
                MutationRecord(
                    mutation=NodeMutation(
                        operation=MutationOperation.DELETE,
                        label="Module",
                        node_id=node_id,
                        properties={},
                    )
                )
            ]
        )

        ops = _translate_mutation_log(log)

        assert len(ops) == 1
        op = ops[0]
        assert op.op == MutationOperationType.DELETE
        assert op.type == EntityType.NODE
        assert op.id == node_id

    def test_edge_upsert_becomes_create(self) -> None:
        source_id = _stable_id("mod", "src/main.py")
        target_id = _stable_id("cls", "src/main.py", "MyClass")
        log = self._make_log(
            [
                MutationRecord(
                    mutation=EdgeMutation(
                        operation=MutationOperation.UPSERT,
                        relation="DEFINES",
                        source_id=source_id,
                        target_id=target_id,
                        properties={},
                    )
                )
            ]
        )

        ops = _translate_mutation_log(log)

        assert len(ops) == 1
        op = ops[0]
        assert op.op == MutationOperationType.CREATE
        assert op.type == EntityType.EDGE
        assert op.label == "DEFINES"
        assert op.start_id == source_id
        assert op.end_id == target_id

    def test_edge_delete_becomes_delete(self) -> None:
        source_id = _stable_id("mod", "src/main.py")
        target_id = _stable_id("cls", "src/main.py", "MyClass")
        log = self._make_log(
            [
                MutationRecord(
                    mutation=EdgeMutation(
                        operation=MutationOperation.DELETE,
                        relation="DEFINES",
                        source_id=source_id,
                        target_id=target_id,
                        properties={},
                    )
                )
            ]
        )

        ops = _translate_mutation_log(log)

        assert len(ops) == 1
        op = ops[0]
        assert op.op == MutationOperationType.DELETE
        assert op.type == EntityType.EDGE
        assert op.start_id == source_id
        assert op.end_id == target_id

    def test_empty_properties_becomes_none(self) -> None:
        """Empty properties dict should translate to None (no-op set_properties)."""
        node_id = _stable_id("cls", "src/main.py", "MyClass")
        log = self._make_log(
            [
                MutationRecord(
                    mutation=NodeMutation(
                        operation=MutationOperation.UPSERT,
                        label="Class",
                        node_id=node_id,
                        properties={},
                    )
                )
            ]
        )

        ops = _translate_mutation_log(log)

        assert len(ops) == 1
        assert ops[0].set_properties is None

    def test_all_translated_ids_match_id_regex(self) -> None:
        """All IDs produced by the AST agent must satisfy ID_REGEX after translation."""
        mod_id = _stable_id("mod", "src/main.py")
        cls_id = _stable_id("cls", "src/main.py", "Foo")
        records = [
            MutationRecord(
                mutation=NodeMutation(MutationOperation.UPSERT, "Module", mod_id, {})
            ),
            MutationRecord(
                mutation=NodeMutation(MutationOperation.UPSERT, "Class", cls_id, {})
            ),
            MutationRecord(
                mutation=EdgeMutation(
                    MutationOperation.UPSERT, "DEFINES", mod_id, cls_id, {}
                )
            ),
        ]
        log = self._make_log(records)
        ops = _translate_mutation_log(log)

        for op in ops:
            for field_id in [op.id, op.start_id, op.end_id]:
                if field_id is not None:
                    assert ID_PATTERN.match(field_id), (
                        f"ID {field_id!r} does not match ID_REGEX"
                    )


class TestInMemoryJobPackageStore:
    """Tests for InMemoryJobPackageStore."""

    @pytest.mark.asyncio
    async def test_store_returns_id(self) -> None:
        from shared_kernel.job_package import JobPackage
        from shared_kernel.datasource_types import DataSourceAdapterType

        store = InMemoryJobPackageStore()
        pkg = JobPackage.create(
            knowledge_graph_id=KG_ID,
            data_source_id=DS_ID,
            tenant_id=TENANT_ID,
            adapter_type=DataSourceAdapterType.GITHUB,
            manifest=None,  # type: ignore[arg-type]
            raw_files={},
        )
        pkg_id = await store.store(pkg)
        assert isinstance(pkg_id, str)
        assert len(pkg_id) > 0

    @pytest.mark.asyncio
    async def test_load_returns_stored_package(self) -> None:
        from shared_kernel.job_package import JobPackage, SyncManifest
        from shared_kernel.datasource_types import DataSourceAdapterType

        store = InMemoryJobPackageStore()
        manifest = SyncManifest(entries=[])
        pkg = JobPackage.create(
            knowledge_graph_id=KG_ID,
            data_source_id=DS_ID,
            tenant_id=TENANT_ID,
            adapter_type=DataSourceAdapterType.GITHUB,
            manifest=manifest,
            raw_files={},
        )
        pkg_id = await store.store(pkg)
        loaded = await store.load(pkg_id)
        assert loaded is pkg

    @pytest.mark.asyncio
    async def test_load_returns_none_for_unknown_id(self) -> None:
        store = InMemoryJobPackageStore()
        result = await store.load("nonexistent")
        assert result is None
