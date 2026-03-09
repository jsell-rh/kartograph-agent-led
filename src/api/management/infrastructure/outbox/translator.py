"""Management-specific event translator for SpiceDB operations.

Translates Management domain events to SpiceDB relationship operations.
Uses type-safe enums from shared_kernel to avoid magic strings.

SpiceDB relationships managed by Management context:
  knowledge_graph#workspace@workspace  — which workspace owns this KG
  knowledge_graph#tenant@tenant        — tenant isolation
  data_source#knowledge_graph@knowledge_graph  — which KG owns this DS
  data_source#tenant@tenant            — tenant isolation

Events that carry no authorization implications (metadata-only updates
and sync triggers) return an empty operation list.
"""

from __future__ import annotations

from typing import Any, Callable, get_args

from management.domain.events import DomainEvent
from shared_kernel.authorization.types import RelationType, ResourceType
from shared_kernel.outbox.operations import (
    DeleteRelationship,
    SpiceDBOperation,
    WriteRelationship,
)

# Build registry mapping event class name → class
_EVENT_REGISTRY: dict[str, type] = {cls.__name__: cls for cls in get_args(DomainEvent)}


class ManagementEventTranslator:
    """Translates Management domain events to SpiceDB operations.

    Handlers are validated at initialization to ensure all domain events
    have a registered handler — Kartograph will fail fast if one is missing.
    """

    def __init__(self) -> None:
        self._handlers: dict[
            str, Callable[[dict[str, Any]], list[SpiceDBOperation]]
        ] = {
            "KnowledgeGraphCreated": self._translate_knowledge_graph_created,
            "KnowledgeGraphUpdated": self._translate_knowledge_graph_updated,
            "KnowledgeGraphDeleted": self._translate_knowledge_graph_deleted,
            "DataSourceCreated": self._translate_data_source_created,
            "DataSourceUpdated": self._translate_data_source_updated,
            "DataSourceDeleted": self._translate_data_source_deleted,
            "DataSourceSyncRequested": self._translate_data_source_sync_requested,
        }
        self._validate_handlers()

    def _validate_handlers(self) -> None:
        """Ensure all domain events have handler methods.

        Raises:
            ValueError: If any domain events are missing handlers
        """
        all_event_names = frozenset(cls.__name__ for cls in get_args(DomainEvent))
        missing = all_event_names - frozenset(self._handlers.keys())
        if missing:
            raise ValueError(
                f"Missing translation handlers for events: {sorted(missing)}"
            )

    def supported_event_types(self) -> frozenset[str]:
        """Return the event type names this translator handles."""
        return frozenset(self._handlers.keys())

    def translate(
        self,
        event_type: str,
        payload: dict[str, Any],
    ) -> list[SpiceDBOperation]:
        """Convert an event payload to SpiceDB operations.

        Args:
            event_type: The name of the event type
            payload: The serialized event data

        Returns:
            List of SpiceDB operations to execute

        Raises:
            ValueError: If the event type is not supported
        """
        handler = self._handlers.get(event_type)
        if handler is None:
            raise ValueError(f"Unknown event type: {event_type}")
        return handler(payload)

    def _translate_knowledge_graph_created(
        self, payload: dict[str, Any]
    ) -> list[SpiceDBOperation]:
        """KnowledgeGraphCreated → write workspace + tenant relationships."""
        return [
            WriteRelationship(
                resource_type=ResourceType.KNOWLEDGE_GRAPH,
                resource_id=payload["knowledge_graph_id"],
                relation=RelationType.WORKSPACE,
                subject_type=ResourceType.WORKSPACE,
                subject_id=payload["workspace_id"],
            ),
            WriteRelationship(
                resource_type=ResourceType.KNOWLEDGE_GRAPH,
                resource_id=payload["knowledge_graph_id"],
                relation=RelationType.TENANT,
                subject_type=ResourceType.TENANT,
                subject_id=payload["tenant_id"],
            ),
        ]

    def _translate_knowledge_graph_updated(
        self, payload: dict[str, Any]
    ) -> list[SpiceDBOperation]:
        """KnowledgeGraphUpdated — metadata only, no SpiceDB changes."""
        return []

    def _translate_knowledge_graph_deleted(
        self, payload: dict[str, Any]
    ) -> list[SpiceDBOperation]:
        """KnowledgeGraphDeleted → delete workspace + tenant relationships."""
        return [
            DeleteRelationship(
                resource_type=ResourceType.KNOWLEDGE_GRAPH,
                resource_id=payload["knowledge_graph_id"],
                relation=RelationType.WORKSPACE,
                subject_type=ResourceType.WORKSPACE,
                subject_id=payload["workspace_id"],
            ),
            DeleteRelationship(
                resource_type=ResourceType.KNOWLEDGE_GRAPH,
                resource_id=payload["knowledge_graph_id"],
                relation=RelationType.TENANT,
                subject_type=ResourceType.TENANT,
                subject_id=payload["tenant_id"],
            ),
        ]

    def _translate_data_source_created(
        self, payload: dict[str, Any]
    ) -> list[SpiceDBOperation]:
        """DataSourceCreated → write knowledge_graph + tenant relationships."""
        return [
            WriteRelationship(
                resource_type=ResourceType.DATA_SOURCE,
                resource_id=payload["data_source_id"],
                relation=RelationType.KNOWLEDGE_GRAPH,
                subject_type=ResourceType.KNOWLEDGE_GRAPH,
                subject_id=payload["knowledge_graph_id"],
            ),
            WriteRelationship(
                resource_type=ResourceType.DATA_SOURCE,
                resource_id=payload["data_source_id"],
                relation=RelationType.TENANT,
                subject_type=ResourceType.TENANT,
                subject_id=payload["tenant_id"],
            ),
        ]

    def _translate_data_source_updated(
        self, payload: dict[str, Any]
    ) -> list[SpiceDBOperation]:
        """DataSourceUpdated — metadata only, no SpiceDB changes."""
        return []

    def _translate_data_source_deleted(
        self, payload: dict[str, Any]
    ) -> list[SpiceDBOperation]:
        """DataSourceDeleted → delete knowledge_graph + tenant relationships."""
        return [
            DeleteRelationship(
                resource_type=ResourceType.DATA_SOURCE,
                resource_id=payload["data_source_id"],
                relation=RelationType.KNOWLEDGE_GRAPH,
                subject_type=ResourceType.KNOWLEDGE_GRAPH,
                subject_id=payload["knowledge_graph_id"],
            ),
            DeleteRelationship(
                resource_type=ResourceType.DATA_SOURCE,
                resource_id=payload["data_source_id"],
                relation=RelationType.TENANT,
                subject_type=ResourceType.TENANT,
                subject_id=payload["tenant_id"],
            ),
        ]

    def _translate_data_source_sync_requested(
        self, payload: dict[str, Any]
    ) -> list[SpiceDBOperation]:
        """DataSourceSyncRequested — triggers ingestion pipeline, no SpiceDB changes."""
        return []
