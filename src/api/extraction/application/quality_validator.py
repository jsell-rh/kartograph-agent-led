"""ExtractionQualityValidator application service (AIHCM-71 / TASK-089).

Computes GraphQualityReport from a MutationLog + JobPackage pair,
then validates computed metrics against QualityThresholds.

Implements the IGraphQualityMetrics port.
"""

from __future__ import annotations

from shared_kernel.job_package import ChangeOperation, JobPackage
from shared_kernel.mutation_log import MutationLog, MutationOperation

from extraction.ports.quality import (
    GraphQualityReport,
    IGraphQualityMetrics,
    QualityThresholds,
    QualityViolation,
)


class ExtractionQualityValidator:
    """Computes and validates graph quality metrics from extraction output.

    Satisfies the IGraphQualityMetrics protocol.
    """

    def compute(
        self, mutation_log: MutationLog, job_package: JobPackage
    ) -> GraphQualityReport:
        """Compute quality metrics from a MutationLog and its source JobPackage."""
        node_records = [r for r in mutation_log.records if r.is_node]
        edge_records = [r for r in mutation_log.records if r.is_edge]

        upsert_nodes = [
            r.as_node
            for r in node_records
            if r.as_node.operation == MutationOperation.UPSERT
        ]
        delete_nodes = [
            r.as_node
            for r in node_records
            if r.as_node.operation == MutationOperation.DELETE
        ]

        # File count = non-DELETE manifest entries (files being added/updated)
        file_count = sum(
            1
            for e in job_package.manifest.entries
            if e.operation != ChangeOperation.DELETE
        )

        nodes_per_file = len(upsert_nodes) / file_count if file_count > 0 else 0.0
        edge_density = (
            len(edge_records) / max(len(node_records), 1) if node_records else 0.0
        )

        label_distribution: dict[str, int] = {}
        for node in upsert_nodes:
            label_distribution[node.label] = label_distribution.get(node.label, 0) + 1

        return GraphQualityReport(
            node_count=len(node_records),
            edge_count=len(edge_records),
            upsert_node_count=len(upsert_nodes),
            delete_node_count=len(delete_nodes),
            nodes_per_file=nodes_per_file,
            edge_density=edge_density,
            label_distribution=label_distribution,
            file_count=file_count,
        )

    def validate(
        self,
        report: GraphQualityReport,
        thresholds: QualityThresholds,
    ) -> list[QualityViolation]:
        """Return list of quality violations (empty = quality passed)."""
        violations: list[QualityViolation] = []

        # Only check nodes_per_file if there are files to process
        if (
            report.file_count > 0
            and report.nodes_per_file < thresholds.min_nodes_per_file
        ):
            violations.append(
                QualityViolation(
                    metric="nodes_per_file",
                    actual=report.nodes_per_file,
                    threshold=thresholds.min_nodes_per_file,
                    message=(
                        f"nodes_per_file {report.nodes_per_file:.2f} < "
                        f"threshold {thresholds.min_nodes_per_file:.2f}"
                    ),
                )
            )

        if report.file_count > 0 and report.edge_density < thresholds.min_edge_density:
            violations.append(
                QualityViolation(
                    metric="edge_density",
                    actual=report.edge_density,
                    threshold=thresholds.min_edge_density,
                    message=(
                        f"edge_density {report.edge_density:.2f} < "
                        f"threshold {thresholds.min_edge_density:.2f}"
                    ),
                )
            )

        for label in thresholds.required_labels:
            if label not in report.label_distribution:
                violations.append(
                    QualityViolation(
                        metric="required_label",
                        actual=0.0,
                        threshold=1.0,
                        message=f"Required label '{label}' not found in extraction output",
                    )
                )

        return violations


# Satisfy the IGraphQualityMetrics protocol at import time
_: IGraphQualityMetrics = ExtractionQualityValidator()  # type: ignore[assignment]
