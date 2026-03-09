"""AGE graph provisioning handler for knowledge graph lifecycle events.

When a KnowledgeGraphCreated event is processed from the outbox, this
handler provisions a dedicated Apache AGE graph for that tenant's
knowledge graph. Each KnowledgeGraph gets its own AGE graph container,
named kg_<knowledge_graph_id_lowercase>.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from sqlalchemy import text

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker


_SUPPORTED: frozenset[str] = frozenset({"KnowledgeGraphCreated"})


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
    """EventHandler that provisions an AGE graph for each new KnowledgeGraph.

    Listens for KnowledgeGraphCreated events from the outbox and creates
    a dedicated AGE graph for that knowledge graph. Each KnowledgeGraph
    gets its own AGE graph named kg_<knowledge_graph_id>.

    Idempotent: if the AGE graph already exists the call is a no-op.
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
        """Provision an AGE graph when a KnowledgeGraph is created.

        Args:
            event_type: The event type name
            payload: The serialized event payload

        Notes:
            - Only acts on KnowledgeGraphCreated; other types are ignored.
            - Idempotent: re-entrant if the graph already exists.
        """
        if event_type != "KnowledgeGraphCreated":
            return

        kg_id = payload["knowledge_graph_id"]
        graph_name = graph_name_for_kg(kg_id)
        await self._provision_graph(graph_name)

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
