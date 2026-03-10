"""AGE graph provisioning handler for knowledge graph lifecycle events.

When a KnowledgeGraphCreated event is processed from the outbox, this
handler provisions a dedicated Apache AGE graph for that tenant's
knowledge graph. Each KnowledgeGraph gets its own AGE graph container,
named kg_<knowledge_graph_id_lowercase>.

When a KnowledgeGraphDeleted event is processed, this handler drops the
corresponding AGE graph and all its data.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from sqlalchemy import text

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker


_SUPPORTED: frozenset[str] = frozenset(
    {"KnowledgeGraphCreated", "KnowledgeGraphDeleted"}
)


def graph_name_for_kg(knowledge_graph_id: str) -> str:
    """Derive AGE graph name from a knowledge_graph_id.

    AGE graph names must be valid PostgreSQL identifiers. ULIDs are
    uppercase alphanumeric, so we lowercase and add a 'kg_' prefix.

    Args:
        knowledge_graph_id: ULID string for the knowledge graph

    Returns:
        AGE-safe graph name, e.g. 'kg_01abcdef...'
    """
    return f"kg_{knowledge_graph_id.lower()}"


class GraphProvisioningHandler:
    """EventHandler that manages AGE graph lifecycle for KnowledgeGraphs.

    Listens for KnowledgeGraphCreated events from the outbox and creates
    a dedicated AGE graph for that knowledge graph. Each KnowledgeGraph
    gets its own AGE graph named kg_<knowledge_graph_id>.

    Listens for KnowledgeGraphDeleted events and drops the corresponding
    AGE graph including all its data.

    Both operations are idempotent.
    """

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
    ) -> None:
        self._session_factory = session_factory

    def supported_event_types(self) -> frozenset[str]:
        """Return the event types this handler processes."""
        return _SUPPORTED

    async def handle(
        self,
        event_type: str,
        payload: dict[str, Any],
    ) -> None:
        """Provision or drop an AGE graph in response to KG lifecycle events.

        Args:
            event_type: The event type name
            payload: The serialized event payload

        Notes:
            - KnowledgeGraphCreated → creates AGE graph (idempotent).
            - KnowledgeGraphDeleted → drops AGE graph (idempotent).
            - Other event types are ignored.
        """
        kg_id = payload["knowledge_graph_id"]
        graph_name = graph_name_for_kg(kg_id)

        if event_type == "KnowledgeGraphCreated":
            await self._provision_graph(graph_name)
        elif event_type == "KnowledgeGraphDeleted":
            await self._drop_graph(graph_name)

    async def _provision_graph(self, graph_name: str) -> None:
        """Create the AGE graph if it does not already exist.

        Args:
            graph_name: The AGE graph name to provision
        """
        async with self._session_factory() as session:
            result = await session.execute(
                text("SELECT 1 FROM ag_catalog.ag_graph WHERE name = :name"),
                {"name": graph_name},
            )
            if result.scalar_one_or_none() is None:
                await session.execute(
                    text("SELECT ag_catalog.create_graph(:name)"),
                    {"name": graph_name},
                )
                await session.commit()

    async def _drop_graph(self, graph_name: str) -> None:
        """Drop the AGE graph if it exists, removing all its data.

        Args:
            graph_name: The AGE graph name to drop
        """
        async with self._session_factory() as session:
            result = await session.execute(
                text("SELECT 1 FROM ag_catalog.ag_graph WHERE name = :name"),
                {"name": graph_name},
            )
            if result.scalar_one_or_none() is not None:
                await session.execute(
                    text("SELECT ag_catalog.drop_graph(:name, true)"),
                    {"name": graph_name},
                )
                await session.commit()
