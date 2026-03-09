"""Unit tests for Extraction context port and synthetic agent (AIHCM-139, AIHCM-174).

The IExtractionAgent protocol defines the plug-in contract:
  JobPackage → MutationLog

The SyntheticExtractionAgent is a deterministic implementation
for testing — no real LLM calls.
"""

from __future__ import annotations

import pytest

from extraction.ports.agents import IExtractionAgent
from extraction.infrastructure.agents.synthetic import SyntheticExtractionAgent
from shared_kernel.datasource_types import DataSourceAdapterType
from shared_kernel.job_package import (
    ChangeOperation,
    JobPackage,
    ManifestEntry,
    SyncManifest,
)
from shared_kernel.mutation_log import MutationLog, MutationOperation


def _make_job_package(raw_files: dict[str, bytes] | None = None) -> JobPackage:
    entries = []
    for path, content in (raw_files or {}).items():
        entries.append(
            ManifestEntry(
                path=path,
                operation=ChangeOperation.ADD,
                content_hash="abc",
            )
        )
    return JobPackage.create(
        knowledge_graph_id="kg-1",
        data_source_id="ds-1",
        tenant_id="t-1",
        adapter_type=DataSourceAdapterType.GITHUB,
        manifest=SyncManifest(entries=entries),
        raw_files=raw_files or {},
    )


class TestIExtractionAgentProtocol:
    """Tests that SyntheticExtractionAgent satisfies IExtractionAgent."""

    def test_synthetic_agent_implements_protocol(self):
        """SyntheticExtractionAgent should satisfy the IExtractionAgent protocol."""
        agent = SyntheticExtractionAgent()
        assert isinstance(agent, IExtractionAgent)


class TestSyntheticExtractionAgent:
    """Tests for SyntheticExtractionAgent deterministic behavior."""

    @pytest.mark.asyncio
    async def test_extract_returns_mutation_log(self):
        """extract() should return a MutationLog."""
        agent = SyntheticExtractionAgent()
        pkg = _make_job_package({"README.md": b"# Hello World"})
        result = await agent.extract(pkg)
        assert isinstance(result, MutationLog)

    @pytest.mark.asyncio
    async def test_extract_links_mutation_log_to_job_package(self):
        """MutationLog should reference the source JobPackage ID."""
        agent = SyntheticExtractionAgent()
        pkg = _make_job_package({"src/app.py": b"def main(): pass"})
        result = await agent.extract(pkg)
        assert result.job_package_id == pkg.id.value

    @pytest.mark.asyncio
    async def test_extract_produces_node_for_each_file(self):
        """Each non-DELETE file in the manifest should produce at least one node."""
        agent = SyntheticExtractionAgent()
        pkg = _make_job_package(
            {
                "src/app.py": b"def main(): pass",
                "src/utils.py": b"def helper(): pass",
            }
        )
        result = await agent.extract(pkg)
        assert result.node_count >= 2

    @pytest.mark.asyncio
    async def test_extract_empty_package_returns_empty_log(self):
        """An empty JobPackage should produce a MutationLog with no records."""
        agent = SyntheticExtractionAgent()
        pkg = _make_job_package({})
        result = await agent.extract(pkg)
        assert result.node_count == 0
        assert result.edge_count == 0

    @pytest.mark.asyncio
    async def test_extract_delete_entries_produce_delete_mutations(self):
        """DELETE manifest entries should produce DELETE node mutations."""
        from shared_kernel.job_package import ManifestEntry, SyncManifest

        pkg = JobPackage.create(
            knowledge_graph_id="kg-1",
            data_source_id="ds-1",
            tenant_id="t-1",
            adapter_type=DataSourceAdapterType.GITHUB,
            manifest=SyncManifest(
                entries=[
                    ManifestEntry(
                        path="old/file.py",
                        operation=ChangeOperation.DELETE,
                        content_hash=None,
                    )
                ]
            ),
            raw_files={},
        )
        agent = SyntheticExtractionAgent()
        result = await agent.extract(pkg)

        delete_mutations = [
            r
            for r in result.records
            if r.is_node and r.as_node.operation == MutationOperation.DELETE
        ]
        assert len(delete_mutations) >= 1

    @pytest.mark.asyncio
    async def test_extract_is_deterministic(self):
        """Same input should always produce the same node IDs."""
        agent = SyntheticExtractionAgent()
        pkg = _make_job_package({"src/app.py": b"def main(): pass"})

        result1 = await agent.extract(pkg)
        result2 = await agent.extract(pkg)

        node_ids_1 = {r.as_node.node_id for r in result1.records if r.is_node}
        node_ids_2 = {r.as_node.node_id for r in result2.records if r.is_node}
        assert node_ids_1 == node_ids_2
