"""Repository protocols (ports) for Management bounded context.

Repository protocols define the interface for persisting and retrieving
aggregates. Implementations coordinate PostgreSQL (metadata) and SpiceDB
(authorization) via the transactional outbox pattern.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from management.domain.aggregates import DataSource, KnowledgeGraph
from management.domain.value_objects import DataSourceId, KnowledgeGraphId


@runtime_checkable
class IKnowledgeGraphRepository(Protocol):
    """Repository for KnowledgeGraph aggregate persistence.

    Implementations use PostgreSQL for metadata and the transactional outbox
    pattern for SpiceDB authorization updates.
    """

    async def save(self, knowledge_graph: KnowledgeGraph) -> None:
        """Persist a knowledge graph aggregate.

        Creates a new knowledge graph or updates an existing one. Persists
        metadata to PostgreSQL and domain events to the outbox (same transaction).

        Args:
            knowledge_graph: The KnowledgeGraph aggregate to persist
        """
        ...

    async def get_by_id(
        self, knowledge_graph_id: KnowledgeGraphId
    ) -> KnowledgeGraph | None:
        """Retrieve a knowledge graph by its ID.

        Args:
            knowledge_graph_id: The unique identifier of the knowledge graph

        Returns:
            The KnowledgeGraph aggregate, or None if not found
        """
        ...

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
            List of KnowledgeGraph aggregates in the workspace
        """
        ...

    async def delete(self, knowledge_graph: KnowledgeGraph) -> bool:
        """Delete a knowledge graph from PostgreSQL.

        Domain events (e.g. KnowledgeGraphDeleted) must already be collected
        from the aggregate before calling this method, so they can be appended
        to the outbox in the same transaction.

        Args:
            knowledge_graph: The KnowledgeGraph aggregate to delete

        Returns:
            True if the knowledge graph was deleted, False if not found
        """
        ...


@runtime_checkable
class IDataSourceRepository(Protocol):
    """Repository for DataSource aggregate persistence.

    Implementations use PostgreSQL for metadata and the transactional outbox
    pattern for SpiceDB authorization updates.
    """

    async def save(self, data_source: DataSource) -> None:
        """Persist a data source aggregate.

        Creates a new data source or updates an existing one.

        Args:
            data_source: The DataSource aggregate to persist
        """
        ...

    async def get_by_id(self, data_source_id: DataSourceId) -> DataSource | None:
        """Retrieve a data source by its ID.

        Args:
            data_source_id: The unique identifier of the data source

        Returns:
            The DataSource aggregate, or None if not found
        """
        ...

    async def list_by_knowledge_graph(
        self,
        knowledge_graph_id: str,
        tenant_id: str,
    ) -> list[DataSource]:
        """List all data sources for a given knowledge graph.

        Args:
            knowledge_graph_id: The knowledge graph to list data sources for
            tenant_id: The tenant for data isolation

        Returns:
            List of DataSource aggregates
        """
        ...

    async def delete(self, data_source: DataSource) -> bool:
        """Delete a data source from PostgreSQL.

        Args:
            data_source: The DataSource aggregate to delete

        Returns:
            True if deleted, False if not found
        """
        ...
