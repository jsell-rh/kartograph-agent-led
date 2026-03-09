"""Management-specific event serializer for outbox persistence.

This module provides serialization and deserialization of Management domain
events for storage in the outbox table. Events are converted to JSON-compatible
dictionaries and reconstructed when processed by the worker.

Management events contain only primitive types (str, datetime, str|None),
so serialization is straightforward — only datetime conversion is needed.
"""

from __future__ import annotations

from dataclasses import asdict
from datetime import datetime
from typing import Any, get_args

from management.domain.events import DomainEvent

# Derive supported events from the DomainEvent type alias
_SUPPORTED_EVENTS: frozenset[str] = frozenset(
    cls.__name__ for cls in get_args(DomainEvent)
)

# Build registry mapping event type names to classes
_EVENT_REGISTRY: dict[str, type] = {cls.__name__: cls for cls in get_args(DomainEvent)}


class ManagementEventSerializer:
    """Serializes and deserializes Management domain events.

    Handles all events defined in the Management DomainEvent type alias.
    Converts datetime fields to ISO format strings for JSON storage and
    reconstructs them on deserialization.
    """

    def supported_event_types(self) -> frozenset[str]:
        """Return the event type names this serializer handles."""
        return _SUPPORTED_EVENTS

    def serialize(self, event: Any) -> dict[str, Any]:
        """Convert a domain event to a JSON-serializable dictionary.

        Args:
            event: The domain event to serialize

        Returns:
            Dictionary with all event fields, datetime values as ISO strings

        Raises:
            ValueError: If the event type is not supported
        """
        event_type = type(event).__name__
        if event_type not in _SUPPORTED_EVENTS:
            raise ValueError(f"Unsupported event type: {event_type}")

        data = asdict(event)
        self._convert_for_json(data)
        return data

    def deserialize(self, event_type: str, payload: dict[str, Any]) -> Any:
        """Reconstruct a domain event from a payload.

        Args:
            event_type: The name of the event type
            payload: The serialized event data

        Returns:
            The reconstructed domain event

        Raises:
            ValueError: If the event type is not supported
        """
        event_class = _EVENT_REGISTRY.get(event_type)
        if event_class is None:
            raise ValueError(f"Unsupported event type: {event_type}")

        data = payload.copy()
        self._convert_from_json(data)
        return event_class(**data)

    def _convert_for_json(self, data: dict[str, Any]) -> None:
        """Convert non-JSON-serializable types in-place."""
        for key, value in data.items():
            if isinstance(value, datetime):
                data[key] = value.isoformat()

    def _convert_from_json(self, data: dict[str, Any]) -> None:
        """Convert serialized types back to original types in-place."""
        if "occurred_at" in data and isinstance(data["occurred_at"], str):
            data["occurred_at"] = datetime.fromisoformat(data["occurred_at"])
