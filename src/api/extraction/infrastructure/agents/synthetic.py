"""Synthetic extraction agent for testing (AIHCM-174).

Deterministic implementation of IExtractionAgent that produces
graph mutations without any LLM API calls. Used in unit tests,
integration tests, and CI.

Strategy:
- For each ADD/UPDATE file in the manifest, creates a "File" node
  whose node_id is derived from the file path (stable across runs).
- For each DELETE file, creates a DELETE NodeMutation.
- No edges in the base implementation (keeps it simple for testing).
"""

from __future__ import annotations

import hashlib

from shared_kernel.job_package import ChangeOperation, JobPackage
from shared_kernel.mutation_log import (
    MutationLog,
    MutationOperation,
    MutationRecord,
    NodeMutation,
)


def _stable_node_id(path: str) -> str:
    """Derive a stable node ID from a file path.

    Uses a short SHA256 prefix to keep IDs stable across runs
    while avoiding path separator issues in graph databases.
    """
    short_hash = hashlib.sha256(path.encode()).hexdigest()[:8]
    return f"file:{short_hash}:{path.replace('/', ':')}"


class SyntheticExtractionAgent:
    """Deterministic extraction agent for testing.

    Produces one File node per manifest entry (UPSERT for ADD/UPDATE,
    DELETE for DELETE entries). No LLM calls are made.

    This satisfies the IExtractionAgent protocol and enables full
    end-to-end testing of the Ingestion → Extraction → Graph pipeline
    without requiring Claude API access.
    """

    async def extract(self, job_package: JobPackage) -> MutationLog:
        """Extract graph mutations from a JobPackage deterministically.

        Args:
            job_package: The packaged raw content from the Ingestion context

        Returns:
            MutationLog with one File node mutation per manifest entry
        """
        records: list[MutationRecord] = []

        for entry in job_package.manifest.entries:
            if entry.operation == ChangeOperation.DELETE:
                records.append(
                    MutationRecord(
                        mutation=NodeMutation(
                            operation=MutationOperation.DELETE,
                            label="File",
                            node_id=_stable_node_id(entry.path),
                            properties={},
                        )
                    )
                )
            else:
                content = job_package.raw_files.get(entry.path, b"")
                records.append(
                    MutationRecord(
                        mutation=NodeMutation(
                            operation=MutationOperation.UPSERT,
                            label="File",
                            node_id=_stable_node_id(entry.path),
                            properties={
                                "path": entry.path,
                                "size_bytes": len(content),
                                "content_hash": entry.content_hash or "",
                            },
                        )
                    )
                )

        return MutationLog.create(
            job_package_id=job_package.id.value,
            knowledge_graph_id=job_package.knowledge_graph_id,
            tenant_id=job_package.tenant_id,
            records=records,
        )
