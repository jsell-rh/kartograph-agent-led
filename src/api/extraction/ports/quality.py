"""Graph quality metrics port for the Extraction bounded context (AIHCM-71).

The IGraphQualityMetrics protocol defines the plug-in contract for computing
measurable quality indicators from a MutationLog. Quality metrics enable
automated validation that an extraction run meets structural expectations
before the mutations are applied to the graph store.

Metrics defined:
  node_count         — total upsert + delete node mutations
  edge_count         — total upsert + delete edge mutations
  upsert_node_count  — nodes being created/updated
  delete_node_count  — nodes being deleted
  nodes_per_file     — coverage proxy: upsert nodes / non-delete manifest entries
  edge_density       — connectedness proxy: edges / max(nodes, 1)
  label_distribution — counts per node label (upsert only)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable

from shared_kernel.job_package import JobPackage
from shared_kernel.mutation_log import MutationLog


@dataclass(frozen=True)
class GraphQualityReport:
    """Computed quality metrics for a single extraction run.

    All counts refer to the MutationLog records, not the graph store state.
    """

    node_count: int
    edge_count: int
    upsert_node_count: int
    delete_node_count: int
    nodes_per_file: float
    edge_density: float
    label_distribution: dict[str, int]
    file_count: int


@dataclass(frozen=True)
class QualityViolation:
    """A single quality threshold violation."""

    metric: str
    actual: float
    threshold: float
    message: str


@dataclass(frozen=True)
class QualityThresholds:
    """Configurable thresholds for graph quality validation.

    Defaults are permissive — set tighter values for production pipelines.
    """

    min_nodes_per_file: float = 0.0
    min_edge_density: float = 0.0
    required_labels: list[str] = field(default_factory=list)


@runtime_checkable
class IGraphQualityMetrics(Protocol):
    """Protocol for computing and validating graph quality metrics.

    Implementations compute a GraphQualityReport from a MutationLog
    and JobPackage, then validate it against QualityThresholds.
    """

    def compute(
        self, mutation_log: MutationLog, job_package: JobPackage
    ) -> GraphQualityReport:
        """Compute quality metrics from a MutationLog and its source JobPackage."""
        ...

    def validate(
        self,
        report: GraphQualityReport,
        thresholds: QualityThresholds,
    ) -> list[QualityViolation]:
        """Return list of threshold violations (empty = quality passed)."""
        ...
