"""Unit tests for graph quality metrics port (AIHCM-71 / TASK-089).

The IGraphQualityMetrics port and GraphQualityReport provide measurable
indicators for extraction quality:
  - node_count, edge_count
  - nodes_per_file (coverage proxy)
  - edge_density (connectedness proxy)
  - label_distribution (type diversity)
  - upsert/delete breakdown
"""

from __future__ import annotations

import pytest

from extraction.ports.quality import (
    IGraphQualityMetrics,
    QualityThresholds,
)
from extraction.application.quality_validator import ExtractionQualityValidator
from shared_kernel.datasource_types import DataSourceAdapterType
from shared_kernel.job_package import (
    ChangeOperation,
    JobPackage,
    ManifestEntry,
    SyncManifest,
)
from shared_kernel.mutation_log import (
    EdgeMutation,
    MutationLog,
    MutationOperation,
    MutationRecord,
    NodeMutation,
)


def _make_pkg(paths: list[str]) -> JobPackage:
    entries = [
        ManifestEntry(path=p, operation=ChangeOperation.ADD, content_hash="abc")
        for p in paths
    ]
    return JobPackage.create(
        knowledge_graph_id="kg-1",
        data_source_id="ds-1",
        tenant_id="t-1",
        adapter_type=DataSourceAdapterType.GITHUB,
        manifest=SyncManifest(entries=entries),
        raw_files={p: b"content" for p in paths},
    )


def _make_log_with_nodes_and_edges(
    node_specs: list[tuple[str, str]],  # (label, node_id)
    edge_specs: list[tuple[str, str, str]],  # (relation, source_id, target_id)
) -> MutationLog:
    records = []
    for label, node_id in node_specs:
        records.append(
            MutationRecord(
                mutation=NodeMutation(
                    operation=MutationOperation.UPSERT,
                    label=label,
                    node_id=node_id,
                    properties={},
                )
            )
        )
    for relation, src, tgt in edge_specs:
        records.append(
            MutationRecord(
                mutation=EdgeMutation(
                    operation=MutationOperation.UPSERT,
                    relation=relation,
                    source_id=src,
                    target_id=tgt,
                    properties={},
                )
            )
        )
    return MutationLog.create(
        job_package_id="pkg-001",
        knowledge_graph_id="kg-1",
        tenant_id="t-1",
        records=records,
    )


class TestGraphQualityReportComputation:
    def test_node_count(self):
        pkg = _make_pkg(["a.py", "b.py"])
        log = _make_log_with_nodes_and_edges(
            [("Module", "mod:a"), ("Module", "mod:b"), ("Function", "fn:x")],
            [],
        )
        validator = ExtractionQualityValidator()
        report = validator.compute(log, pkg)
        assert report.node_count == 3

    def test_edge_count(self):
        pkg = _make_pkg(["a.py"])
        log = _make_log_with_nodes_and_edges(
            [("Module", "mod:a"), ("Function", "fn:x")],
            [("DEFINES", "mod:a", "fn:x")],
        )
        validator = ExtractionQualityValidator()
        report = validator.compute(log, pkg)
        assert report.edge_count == 1

    def test_nodes_per_file(self):
        pkg = _make_pkg(["a.py", "b.py"])
        log = _make_log_with_nodes_and_edges(
            [
                ("Module", "mod:a"),
                ("Module", "mod:b"),
                ("Function", "fn:x"),
                ("Function", "fn:y"),
            ],
            [],
        )
        validator = ExtractionQualityValidator()
        report = validator.compute(log, pkg)
        assert report.nodes_per_file == pytest.approx(2.0)

    def test_edge_density_with_no_nodes(self):
        pkg = _make_pkg([])
        log = _make_log_with_nodes_and_edges([], [])
        validator = ExtractionQualityValidator()
        report = validator.compute(log, pkg)
        assert report.edge_density == pytest.approx(0.0)

    def test_edge_density_with_nodes_and_edges(self):
        pkg = _make_pkg(["a.py"])
        log = _make_log_with_nodes_and_edges(
            [("Module", "mod:a"), ("Function", "fn:x"), ("Function", "fn:y")],
            [("DEFINES", "mod:a", "fn:x"), ("DEFINES", "mod:a", "fn:y")],
        )
        validator = ExtractionQualityValidator()
        report = validator.compute(log, pkg)
        # edge_density = edges / nodes = 2 / 3
        assert report.edge_density == pytest.approx(2 / 3)

    def test_label_distribution(self):
        pkg = _make_pkg(["a.py", "b.py"])
        log = _make_log_with_nodes_and_edges(
            [
                ("Module", "mod:a"),
                ("Module", "mod:b"),
                ("Function", "fn:x"),
                ("Function", "fn:y"),
                ("Function", "fn:z"),
                ("Class", "cls:A"),
            ],
            [],
        )
        validator = ExtractionQualityValidator()
        report = validator.compute(log, pkg)
        assert report.label_distribution["Module"] == 2
        assert report.label_distribution["Function"] == 3
        assert report.label_distribution["Class"] == 1

    def test_upsert_count(self):
        pkg = _make_pkg(["a.py"])
        records = [
            MutationRecord(
                mutation=NodeMutation(MutationOperation.UPSERT, "Module", "mod:a", {})
            ),
            MutationRecord(
                mutation=NodeMutation(MutationOperation.DELETE, "Module", "mod:b", {})
            ),
        ]
        log = MutationLog.create("pkg-001", "kg-1", "t-1", records)
        validator = ExtractionQualityValidator()
        report = validator.compute(log, pkg)
        assert report.upsert_node_count == 1
        assert report.delete_node_count == 1


class TestQualityValidatorThresholds:
    def test_no_violations_when_above_thresholds(self):
        pkg = _make_pkg(["a.py", "b.py"])
        log = _make_log_with_nodes_and_edges(
            [("Module", "mod:a"), ("Module", "mod:b"), ("Function", "fn:x")],
            [("DEFINES", "mod:a", "fn:x")],
        )
        validator = ExtractionQualityValidator()
        report = validator.compute(log, pkg)
        thresholds = QualityThresholds(min_nodes_per_file=1.0)
        violations = validator.validate(report, thresholds)
        assert violations == []

    def test_violation_when_nodes_per_file_too_low(self):
        pkg = _make_pkg(["a.py", "b.py", "c.py"])
        log = _make_log_with_nodes_and_edges(
            [("Module", "mod:a")],  # only 1 node for 3 files
            [],
        )
        validator = ExtractionQualityValidator()
        report = validator.compute(log, pkg)
        thresholds = QualityThresholds(min_nodes_per_file=1.0)
        violations = validator.validate(report, thresholds)
        assert len(violations) >= 1
        assert any(v.metric == "nodes_per_file" for v in violations)

    def test_violation_when_empty_log_with_non_empty_package(self):
        pkg = _make_pkg(["a.py", "b.py"])
        log = _make_log_with_nodes_and_edges([], [])
        validator = ExtractionQualityValidator()
        report = validator.compute(log, pkg)
        thresholds = QualityThresholds(min_nodes_per_file=0.5)
        violations = validator.validate(report, thresholds)
        assert len(violations) >= 1

    def test_empty_package_has_no_violations(self):
        pkg = _make_pkg([])
        log = _make_log_with_nodes_and_edges([], [])
        validator = ExtractionQualityValidator()
        report = validator.compute(log, pkg)
        thresholds = QualityThresholds(min_nodes_per_file=1.0)
        violations = validator.validate(report, thresholds)
        assert violations == []

    def test_default_thresholds_are_permissive(self):
        """Default thresholds should not block reasonable extractions."""
        pkg = _make_pkg(["a.py"])
        log = _make_log_with_nodes_and_edges(
            [("Module", "mod:a")],
            [],
        )
        validator = ExtractionQualityValidator()
        report = validator.compute(log, pkg)
        violations = validator.validate(report, QualityThresholds())
        assert violations == []


class TestIGraphQualityMetricsProtocol:
    def test_validator_implements_protocol(self):
        validator = ExtractionQualityValidator()
        assert isinstance(validator, IGraphQualityMetrics)
