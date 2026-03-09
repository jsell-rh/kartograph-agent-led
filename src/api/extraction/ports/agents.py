"""Agent protocol (port) for the Extraction bounded context (AIHCM-139).

The IExtractionAgent protocol defines the plug-in contract:
  JobPackage → MutationLog

The external team's AI agent (Claude Agent SDK) will implement this port.
We also provide a SyntheticExtractionAgent for testing without LLM calls.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from shared_kernel.job_package import JobPackage
from shared_kernel.mutation_log import MutationLog


@runtime_checkable
class IExtractionAgent(Protocol):
    """Protocol (port) that all extraction agent implementations must satisfy.

    The AI-driven implementation (Extraction Agent) will use the Claude
    Agent SDK to analyze JobPackage content and produce a MutationLog.

    The SyntheticExtractionAgent satisfies this protocol deterministically
    for unit tests and CI without requiring LLM API calls.
    """

    async def extract(self, job_package: JobPackage) -> MutationLog:
        """Extract knowledge graph mutations from a JobPackage.

        Args:
            job_package: The packaged raw content from the Ingestion context

        Returns:
            MutationLog describing all graph mutations to apply
        """
        ...
