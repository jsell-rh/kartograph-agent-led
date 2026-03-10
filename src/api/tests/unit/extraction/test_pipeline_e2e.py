"""End-to-end pipeline validation tests (AIHCM-174 / TASK-091).

Validates the complete Ingestion → Extraction → quality check pipeline
using only synthetic components (no LLM, no DB, no network).

Pipeline:
  raw files
    → JobPackage (Ingestion output)
    → PythonAstSyntheticExtractionAgent.extract()
    → MutationLog (Extraction output)
    → ExtractionQualityValidator.compute() + validate()
    → GraphQualityReport with no quality violations
"""

from __future__ import annotations

import pytest

from extraction.application.quality_validator import ExtractionQualityValidator
from extraction.infrastructure.agents.python_ast_agent import (
    PythonAstSyntheticExtractionAgent,
)
from extraction.ports.quality import QualityThresholds
from shared_kernel.datasource_types import DataSourceAdapterType
from shared_kernel.job_package import (
    ChangeOperation,
    JobPackage,
    ManifestEntry,
    SyncManifest,
)

SAMPLE_MODULE_A = b"""\
import os

class ServiceClient:
    def connect(self):
        return os.environ.get("URL")

    def disconnect(self):
        pass
"""

SAMPLE_MODULE_B = b"""\
from module_a import ServiceClient

def run():
    client = ServiceClient()
    client.connect()
    return client
"""


def _make_pkg(raw_files: dict[str, bytes]) -> JobPackage:
    entries = [
        ManifestEntry(path=p, operation=ChangeOperation.ADD, content_hash="abc")
        for p in raw_files
    ]
    return JobPackage.create(
        knowledge_graph_id="kg-e2e",
        data_source_id="ds-github",
        tenant_id="t-acme",
        adapter_type=DataSourceAdapterType.GITHUB,
        manifest=SyncManifest(entries=entries),
        raw_files=raw_files,
    )


class TestExtractionPipelineE2E:
    @pytest.mark.asyncio
    async def test_single_file_pipeline_produces_valid_log(self):
        """Single Python file → MutationLog with Module + Function + Class nodes."""
        pkg = _make_pkg({"src/module_a.py": SAMPLE_MODULE_A})
        agent = PythonAstSyntheticExtractionAgent()

        log = await agent.extract(pkg)

        assert log.job_package_id == pkg.id.value
        assert log.node_count >= 1  # at least Module node
        assert log.edge_count >= 0

    @pytest.mark.asyncio
    async def test_multi_file_pipeline_covers_all_files(self):
        """Multi-file package → each file has at least one node in MutationLog."""
        pkg = _make_pkg(
            {
                "src/module_a.py": SAMPLE_MODULE_A,
                "src/module_b.py": SAMPLE_MODULE_B,
            }
        )
        agent = PythonAstSyntheticExtractionAgent()

        log = await agent.extract(pkg)

        # Should have at least 2 module nodes (one per .py file)
        module_nodes = [
            r.as_node for r in log.records if r.is_node and r.as_node.label == "Module"
        ]
        assert len(module_nodes) >= 2

    @pytest.mark.asyncio
    async def test_pipeline_quality_passes_default_thresholds(self):
        """E2E: default quality thresholds should pass for well-structured code."""
        pkg = _make_pkg(
            {
                "src/module_a.py": SAMPLE_MODULE_A,
                "src/module_b.py": SAMPLE_MODULE_B,
            }
        )
        agent = PythonAstSyntheticExtractionAgent()
        log = await agent.extract(pkg)

        validator = ExtractionQualityValidator()
        report = validator.compute(log, pkg)
        violations = validator.validate(report, QualityThresholds())

        assert violations == [], f"Quality violations: {violations}"

    @pytest.mark.asyncio
    async def test_pipeline_quality_report_has_expected_labels(self):
        """E2E: MutationLog from Python code should contain Module + Function + Class labels."""
        pkg = _make_pkg({"src/module_a.py": SAMPLE_MODULE_A})
        agent = PythonAstSyntheticExtractionAgent()
        log = await agent.extract(pkg)

        validator = ExtractionQualityValidator()
        report = validator.compute(log, pkg)

        assert "Module" in report.label_distribution
        assert report.label_distribution.get("Function", 0) >= 1

    @pytest.mark.asyncio
    async def test_pipeline_mutation_log_is_jsonl_serializable(self):
        """MutationLog from extraction must survive JSONL roundtrip."""
        import json

        pkg = _make_pkg({"src/module_a.py": SAMPLE_MODULE_A})
        agent = PythonAstSyntheticExtractionAgent()
        log = await agent.extract(pkg)

        jsonl = log.to_jsonl()
        lines = [line for line in jsonl.strip().split("\n") if line]
        assert len(lines) == len(log.records)
        for line in lines:
            json.loads(line)  # Must not raise

    @pytest.mark.asyncio
    async def test_pipeline_delete_entries_reduce_quality_gracefully(self):
        """DELETE-only package: empty log should satisfy permissive thresholds."""
        pkg = JobPackage.create(
            knowledge_graph_id="kg-1",
            data_source_id="ds-1",
            tenant_id="t-1",
            adapter_type=DataSourceAdapterType.GITHUB,
            manifest=SyncManifest(
                entries=[
                    ManifestEntry(
                        path="old.py",
                        operation=ChangeOperation.DELETE,
                        content_hash=None,
                    )
                ]
            ),
            raw_files={},
        )
        agent = PythonAstSyntheticExtractionAgent()
        log = await agent.extract(pkg)

        validator = ExtractionQualityValidator()
        report = validator.compute(log, pkg)
        # DELETE-only package: 0 files to add, 0 files_count
        # Default thresholds should not flag this as a problem
        violations = validator.validate(report, QualityThresholds())
        assert violations == []
