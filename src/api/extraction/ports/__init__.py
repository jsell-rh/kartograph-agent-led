"""Port definitions for the Extraction bounded context."""

from extraction.ports.agents import IExtractionAgent
from extraction.ports.quality import (
    GraphQualityReport,
    IGraphQualityMetrics,
    QualityThresholds,
    QualityViolation,
)

__all__ = [
    "IExtractionAgent",
    "IGraphQualityMetrics",
    "GraphQualityReport",
    "QualityThresholds",
    "QualityViolation",
]
