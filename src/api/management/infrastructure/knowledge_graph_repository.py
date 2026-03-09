"""PostgreSQL implementation of IKnowledgeGraphRepository.

Uses the transactional outbox pattern — domain events are collected from
the aggregate and appended to the outbox table within the same database
transaction as the aggregate changes. The outbox worker processes events
and writes the corresponding SpiceDB relationships.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from management.domain.aggregates import KnowledgeGraph
from management.domain.value_objects import KnowledgeGraphId
from management.infrastructure.models import KnowledgeGraphModel
from management.infrastructure.outbox.serializer import ManagementEventSerializer
from management.ports.repositories import IKnowledgeGraphRepository

if TYPE_CHECKING:
    from infrastructure.outbox.repository import OutboxRepository


class KnowledgeGraphRepository(IKnowledgeGraphRepository):
    """Repository for KnowledgeGraph aggregates backed by PostgreSQL.

    Stores knowledge graph metadata in PostgreSQL and emits domain events
    to the transactional outbox for async SpiceDB updates.
    """

    def __init__(
        self,
        session: AsyncSession,
        outbox: "OutboxRepository",
        serializer: ManagementEventSerializer | None = None,
    ) -> None:
        self._session = session
        self._outbox = outbox
        self._serializer = serializer or ManagementEventSerializer()

    async def save(self, knowledge_graph: KnowledgeGraph) -> None:
        """Persist knowledge graph metadata and emit domain events to outbox.

        Args:
            knowledge_graph: The KnowledgeGraph aggregate to persist
        """
        stmt = select(KnowledgeGraphModel).where(
            KnowledgeGraphModel.id == knowledge_graph.id.value
        )
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()

        if model:
            model.name = knowledge_graph.name
            model.description = knowledge_graph.description
            model.updated_at = knowledge_graph.updated_at
        else:
            model = KnowledgeGraphModel(
                id=knowledge_graph.id.value,
                tenant_id=knowledge_graph.tenant_id,
                workspace_id=knowledge_graph.workspace_id,
                name=knowledge_graph.name,
                description=knowledge_graph.description,
                created_at=knowledge_graph.created_at,
                updated_at=knowledge_graph.updated_at,
            )
            self._session.add(model)

        await self._session.flush()

        events = knowledge_graph.collect_events()
        for event in events:
            payload = self._serializer.serialize(event)
            await self._outbox.append(
                event_type=type(event).__name__,
                payload=payload,
                occurred_at=event.occurred_at,
                aggregate_type="knowledge_graph",
                aggregate_id=knowledge_graph.id.value,
            )

    async def get_by_id(
        self, knowledge_graph_id: KnowledgeGraphId
    ) -> KnowledgeGraph | None:
        """Retrieve a knowledge graph by its ID from PostgreSQL.

        Args:
            knowledge_graph_id: The unique identifier of the knowledge graph

        Returns:
            The KnowledgeGraph aggregate, or None if not found
        """
        stmt = select(KnowledgeGraphModel).where(
            KnowledgeGraphModel.id == knowledge_graph_id.value
        )
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()

        if model is None:
            return None

        return self._to_domain(model)

    async def list_by_workspace(
        self,
        workspace_id: str,
        tenant_id: str,
    ) -> list[KnowledgeGraph]:
        """List all knowledge graphs for a given workspace.

        Args:
            workspace_id: The workspace to list knowledge graphs for
            tenant_id: The tenant for data isolation

        Returns:
            List of KnowledgeGraph aggregates ordered by name
        """
        stmt = (
            select(KnowledgeGraphModel)
            .where(
                KnowledgeGraphModel.workspace_id == workspace_id,
                KnowledgeGraphModel.tenant_id == tenant_id,
            )
            .order_by(KnowledgeGraphModel.name)
        )
        result = await self._session.execute(stmt)
        models = result.scalars().all()
        return [self._to_domain(m) for m in models]

    async def delete(self, knowledge_graph: KnowledgeGraph) -> bool:
        """Delete a knowledge graph from PostgreSQL, appending events to outbox.

        Domain events (KnowledgeGraphDeleted) should already be collected
        from the aggregate via mark_for_deletion() before calling this method.

        Args:
            knowledge_graph: The KnowledgeGraph aggregate to delete

        Returns:
            True if deleted, False if not found
        """
        stmt = select(KnowledgeGraphModel).where(
            KnowledgeGraphModel.id == knowledge_graph.id.value
        )
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()

        if model is None:
            return False

        events = knowledge_graph.collect_events()
        for event in events:
            payload = self._serializer.serialize(event)
            await self._outbox.append(
                event_type=type(event).__name__,
                payload=payload,
                occurred_at=event.occurred_at,
                aggregate_type="knowledge_graph",
                aggregate_id=knowledge_graph.id.value,
            )

        await self._session.delete(model)
        await self._session.flush()
        return True

    def _to_domain(self, model: KnowledgeGraphModel) -> KnowledgeGraph:
        """Reconstitute KnowledgeGraph aggregate from ORM model.

        This is a read operation — no domain events are generated.

        Args:
            model: The SQLAlchemy model to convert

        Returns:
            A KnowledgeGraph aggregate with no pending events
        """
        return KnowledgeGraph(
            id=KnowledgeGraphId(value=model.id),
            tenant_id=model.tenant_id,
            workspace_id=model.workspace_id,
            name=model.name,
            description=model.description,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )
