"""Value objects for the Ingestion bounded context (AIHCM-176).

Value objects are immutable descriptors that provide type safety and
domain semantics for identifiers and domain concepts in Ingestion.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import TypeVar

from ulid import ULID

T = TypeVar("T", bound="SyncJobId")


@dataclass(frozen=True)
class SyncJobId:
    """Identifier for a SyncJob aggregate.

    Uses ULID for sortability and distribution-friendly generation.
    """

    value: str

    def __str__(self) -> str:
        return self.value

    @classmethod
    def generate(cls: type[T]) -> T:
        """Generate a new SyncJobId using ULID."""
        return cls(value=str(ULID()))

    @classmethod
    def from_string(cls: type[T], value: str) -> T:
        """Create a SyncJobId from a string.

        Args:
            value: ULID string

        Raises:
            ValueError: If value is not a valid ULID
        """
        try:
            ULID.from_str(value)
        except ValueError as e:
            raise ValueError(f"Invalid {cls.__name__}: {value}") from e
        return cls(value=value)


class SyncJobStatus(StrEnum):
    """Lifecycle status of a SyncJob aggregate.

    Transitions:
        PENDING → RUNNING → COMPLETED
        PENDING → RUNNING → FAILED
    """

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
