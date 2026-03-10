"""AST-level synthetic extraction agent (AIHCM-174 / TASK-091).

Extends the basic SyntheticExtractionAgent with Python AST parsing to
produce richer graph output:
  - Module nodes (one per .py file)
  - Function nodes (top-level and methods)
  - Class nodes
  - DEFINES edges (Module → Function, Module → Class, Class → Method)

For non-.py files, falls back to a File node (same as SyntheticExtractionAgent).

No LLM calls are made. Deterministic — same input always produces same output.
Used for E2E pipeline validation in tests and CI (AIHCM-174).
"""

from __future__ import annotations

import ast
import hashlib

from shared_kernel.job_package import ChangeOperation, JobPackage
from shared_kernel.mutation_log import (
    EdgeMutation,
    MutationLog,
    MutationOperation,
    MutationRecord,
    NodeMutation,
)


def _stable_id(prefix: str, *parts: str) -> str:
    """Derive a stable node ID from a prefix and path components."""
    key = ":".join(parts)
    short_hash = hashlib.sha256(key.encode()).hexdigest()[:8]
    return f"{prefix}:{short_hash}:{key.replace('/', ':')}"


def _extract_python_records(path: str, content: bytes) -> list[MutationRecord]:
    """Parse a Python file with ast and return graph mutation records."""
    records: list[MutationRecord] = []

    try:
        tree = ast.parse(content, filename=path)
    except SyntaxError:
        # Unparseable file: emit a File node as fallback
        records.append(
            MutationRecord(
                mutation=NodeMutation(
                    operation=MutationOperation.UPSERT,
                    label="File",
                    node_id=_stable_id("file", path),
                    properties={"path": path, "parse_error": True},
                )
            )
        )
        return records

    module_id = _stable_id("mod", path)
    records.append(
        MutationRecord(
            mutation=NodeMutation(
                operation=MutationOperation.UPSERT,
                label="Module",
                node_id=module_id,
                properties={
                    "path": path,
                    "name": path.rsplit("/", 1)[-1].removesuffix(".py"),
                },
            )
        )
    )

    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            class_id = _stable_id("cls", path, node.name)
            records.append(
                MutationRecord(
                    mutation=NodeMutation(
                        operation=MutationOperation.UPSERT,
                        label="Class",
                        node_id=class_id,
                        properties={
                            "name": node.name,
                            "line": node.lineno,
                            "module": path,
                        },
                    )
                )
            )
            records.append(
                MutationRecord(
                    mutation=EdgeMutation(
                        operation=MutationOperation.UPSERT,
                        relation="DEFINES",
                        source_id=module_id,
                        target_id=class_id,
                        properties={},
                    )
                )
            )
            # Methods within the class
            for item in node.body:
                if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    method_id = _stable_id("fn", path, node.name, item.name)
                    records.append(
                        MutationRecord(
                            mutation=NodeMutation(
                                operation=MutationOperation.UPSERT,
                                label="Function",
                                node_id=method_id,
                                properties={
                                    "name": item.name,
                                    "line": item.lineno,
                                    "module": path,
                                    "class": node.name,
                                },
                            )
                        )
                    )
                    records.append(
                        MutationRecord(
                            mutation=EdgeMutation(
                                operation=MutationOperation.UPSERT,
                                relation="DEFINES",
                                source_id=class_id,
                                target_id=method_id,
                                properties={},
                            )
                        )
                    )

        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            # Top-level functions only (skip methods — handled above)
            if not any(
                isinstance(parent, ast.ClassDef)
                for parent in ast.walk(tree)
                if any(
                    child is node for child in ast.walk(parent) if child is not parent
                )
            ):
                func_id = _stable_id("fn", path, node.name)
                records.append(
                    MutationRecord(
                        mutation=NodeMutation(
                            operation=MutationOperation.UPSERT,
                            label="Function",
                            node_id=func_id,
                            properties={
                                "name": node.name,
                                "line": node.lineno,
                                "module": path,
                            },
                        )
                    )
                )
                records.append(
                    MutationRecord(
                        mutation=EdgeMutation(
                            operation=MutationOperation.UPSERT,
                            relation="DEFINES",
                            source_id=module_id,
                            target_id=func_id,
                            properties={},
                        )
                    )
                )

    return records


class PythonAstSyntheticExtractionAgent:
    """AST-level synthetic extraction agent for testing and CI validation.

    Produces richer graph output than SyntheticExtractionAgent:
    - Module, Function, Class nodes for .py files
    - DEFINES edges linking modules to their members
    - File nodes for non-.py files (same as base agent)

    Deterministic: same input always produces same node IDs and structure.
    No LLM or network calls.

    Satisfies the IExtractionAgent protocol.
    """

    async def extract(self, job_package: JobPackage) -> MutationLog:
        """Extract AST-level graph mutations from a JobPackage."""
        records: list[MutationRecord] = []

        for entry in job_package.manifest.entries:
            if entry.operation == ChangeOperation.DELETE:
                records.append(
                    MutationRecord(
                        mutation=NodeMutation(
                            operation=MutationOperation.DELETE,
                            label="Module",
                            node_id=_stable_id("mod", entry.path),
                            properties={},
                        )
                    )
                )
            else:
                content = job_package.raw_files.get(entry.path, b"")
                if entry.path.endswith(".py"):
                    records.extend(_extract_python_records(entry.path, content))
                else:
                    records.append(
                        MutationRecord(
                            mutation=NodeMutation(
                                operation=MutationOperation.UPSERT,
                                label="File",
                                node_id=_stable_id("file", entry.path),
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
