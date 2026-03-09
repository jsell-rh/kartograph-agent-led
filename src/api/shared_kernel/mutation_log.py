"""MutationLog shared kernel artifact (AIHCM-139).

The MutationLog is the output contract of the Extraction bounded context
and the input contract for the Graph bounded context. It describes a
sequence of graph mutations (node/edge upserts and deletes).

Lives in shared_kernel so Extraction (producer) and Graph (consumer)
can reference it without coupling.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from typing import TypeVar, Union

from ulid import ULID

T = TypeVar("T", bound="MutationLogId")


@dataclass(frozen=True)
class MutationLogId:
    """Identifier for a MutationLog."""

    value: str

    def __str__(self) -> str:
        return self.value

    @classmethod
    def generate(cls: type[T]) -> T:
        return cls(value=str(ULID()))

    @classmethod
    def from_string(cls: type[T], value: str) -> T:
        try:
            ULID.from_str(value)
        except ValueError as e:
            raise ValueError(f"Invalid {cls.__name__}: {value}") from e
        return cls(value=value)


class MutationOperation(StrEnum):
    """The type of graph mutation to apply."""

    UPSERT = "upsert"
    DELETE = "delete"


@dataclass(frozen=True)
class NodeMutation:
    """A single node create/update or delete operation.

    Attributes:
        operation: UPSERT (create or update) or DELETE
        label: The node label / type (e.g. "Function", "Module", "Class")
        node_id: Stable cross-sync identifier for this node (e.g. "func:main")
        properties: Key-value properties for UPSERT; empty for DELETE
    """

    operation: MutationOperation
    label: str
    node_id: str
    properties: dict

    def to_dict(self) -> dict:
        return {
            "type": "node",
            "operation": str(self.operation),
            "label": self.label,
            "node_id": self.node_id,
            "properties": self.properties,
        }

    @classmethod
    def from_dict(cls, data: dict) -> NodeMutation:
        return cls(
            operation=MutationOperation(data["operation"]),
            label=data["label"],
            node_id=data["node_id"],
            properties=data.get("properties", {}),
        )


@dataclass(frozen=True)
class EdgeMutation:
    """A single edge create/update or delete operation.

    Attributes:
        operation: UPSERT or DELETE
        relation: The edge label / relationship type (e.g. "CALLS", "IMPORTS")
        source_id: node_id of the source node
        target_id: node_id of the target node
        properties: Key-value properties for UPSERT; empty for DELETE
    """

    operation: MutationOperation
    relation: str
    source_id: str
    target_id: str
    properties: dict

    def to_dict(self) -> dict:
        return {
            "type": "edge",
            "operation": str(self.operation),
            "relation": self.relation,
            "source_id": self.source_id,
            "target_id": self.target_id,
            "properties": self.properties,
        }

    @classmethod
    def from_dict(cls, data: dict) -> EdgeMutation:
        return cls(
            operation=MutationOperation(data["operation"]),
            relation=data["relation"],
            source_id=data["source_id"],
            target_id=data["target_id"],
            properties=data.get("properties", {}),
        )


_Mutation = Union[NodeMutation, EdgeMutation]


@dataclass(frozen=True)
class MutationRecord:
    """Wraps a single NodeMutation or EdgeMutation.

    Provides a uniform record type for the MutationLog JSONL stream,
    with type-safe accessors.
    """

    mutation: _Mutation

    @property
    def is_node(self) -> bool:
        return isinstance(self.mutation, NodeMutation)

    @property
    def is_edge(self) -> bool:
        return isinstance(self.mutation, EdgeMutation)

    @property
    def as_node(self) -> NodeMutation:
        assert isinstance(self.mutation, NodeMutation)
        return self.mutation

    @property
    def as_edge(self) -> EdgeMutation:
        assert isinstance(self.mutation, EdgeMutation)
        return self.mutation

    def to_dict(self) -> dict:
        return self.mutation.to_dict()

    @classmethod
    def from_dict(cls, data: dict) -> MutationRecord:
        if data["type"] == "node":
            return cls(mutation=NodeMutation.from_dict(data))
        return cls(mutation=EdgeMutation.from_dict(data))


@dataclass
class MutationLog:
    """Sequence of graph mutations produced by the Extraction context.

    A MutationLog is produced for each JobPackage processed. The Graph
    context applies its records transactionally.

    Serialization: JSONL (one JSON object per line) for streaming.

    Attributes:
        id: Unique identifier
        job_package_id: The JobPackage this log was derived from
        knowledge_graph_id: The target knowledge graph
        tenant_id: Tenant isolation boundary
        records: Ordered list of MutationRecord objects
        created_at: When this log was produced
    """

    id: MutationLogId
    job_package_id: str
    knowledge_graph_id: str
    tenant_id: str
    records: list[MutationRecord]
    created_at: datetime

    @classmethod
    def create(
        cls,
        job_package_id: str,
        knowledge_graph_id: str,
        tenant_id: str,
        records: list[MutationRecord],
    ) -> MutationLog:
        return cls(
            id=MutationLogId.generate(),
            job_package_id=job_package_id,
            knowledge_graph_id=knowledge_graph_id,
            tenant_id=tenant_id,
            records=records,
            created_at=datetime.now(UTC),
        )

    @property
    def node_count(self) -> int:
        return sum(1 for r in self.records if r.is_node)

    @property
    def edge_count(self) -> int:
        return sum(1 for r in self.records if r.is_edge)

    def to_jsonl(self) -> str:
        """Serialize to JSONL (one JSON object per line)."""
        if not self.records:
            return ""
        return "\n".join(
            json.dumps(r.to_dict(), ensure_ascii=False) for r in self.records
        )

    @classmethod
    def from_jsonl(
        cls,
        jsonl: str,
        *,
        job_package_id: str,
        knowledge_graph_id: str,
        tenant_id: str,
        log_id: str,
    ) -> MutationLog:
        """Deserialize from JSONL produced by to_jsonl()."""
        records: list[MutationRecord] = []
        for line in jsonl.strip().split("\n"):
            if line.strip():
                records.append(MutationRecord.from_dict(json.loads(line)))
        return cls(
            id=MutationLogId(value=log_id),
            job_package_id=job_package_id,
            knowledge_graph_id=knowledge_graph_id,
            tenant_id=tenant_id,
            records=records,
            created_at=datetime.now(UTC),
        )
