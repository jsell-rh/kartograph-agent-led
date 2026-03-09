"""Dependency injection for Graph bounded context.

Composes infrastructure resources (pool) with graph-specific components
(client, repositories, services).
"""

from collections.abc import Generator
from functools import lru_cache
from typing import Annotated

from fastapi import Depends, Query

from graph.infrastructure.graph_provisioning_handler import graph_name_for_kg

from graph.application.observability import (
    DefaultGraphServiceProbe,
    DefaultSchemaServiceProbe,
    GraphServiceProbe,
    SchemaServiceProbe,
)
from graph.application.services import (
    GraphMutationService,
    GraphQueryService,
    GraphSchemaService,
)
from graph.infrastructure.age_bulk_loading import AgeBulkLoadingStrategy
from graph.infrastructure.age_client import AgeGraphClient
from graph.infrastructure.graph_repository import GraphExtractionReadOnlyRepository
from graph.infrastructure.mutation_applier import MutationApplier
from graph.infrastructure.type_definition_repository import (
    InMemoryTypeDefinitionRepository,
)
from graph.ports.repositories import ITypeDefinitionRepository
from infrastructure.database.connection import ConnectionFactory
from infrastructure.database.connection_pool import ConnectionPool
from infrastructure.dependencies import get_age_connection_pool
from infrastructure.settings import get_database_settings


def get_graph_service_probe() -> GraphServiceProbe:
    """Get GraphServiceProbe instance.

    Returns:
        DefaultGraphServiceProbe instance for observability
    """
    return DefaultGraphServiceProbe()


def get_schema_service_probe() -> SchemaServiceProbe:
    """Get SchemaServiceProbe instance.

    Returns:
        DefaultSchemaServiceProbe instance for observability
    """
    return DefaultSchemaServiceProbe()


def get_age_graph_client(
    pool: Annotated[ConnectionPool, Depends(get_age_connection_pool)],
    knowledge_graph_id: str | None = Query(
        None,
        description="KnowledgeGraph ID to scope graph operations to a per-tenant AGE graph",
    ),
) -> Generator[AgeGraphClient, None, None]:
    """Get request-scoped AGE graph client.

    Each request gets its own client with a connection from the pool.
    Connection is automatically returned to pool on cleanup.

    When knowledge_graph_id is provided, the client is scoped to the
    per-tenant AGE graph (kg_<knowledge_graph_id>) instead of the
    default global graph from settings.

    Args:
        pool: Application-scoped connection pool
        knowledge_graph_id: Optional KG ID for per-tenant graph scoping

    Yields:
        Connected AgeGraphClient instance
    """
    settings = get_database_settings()
    factory = ConnectionFactory(settings, pool=pool)
    resolved_graph_name = (
        graph_name_for_kg(knowledge_graph_id)
        if knowledge_graph_id is not None
        else settings.graph_name
    )
    client = AgeGraphClient(
        settings, connection_factory=factory, graph_name=resolved_graph_name
    )
    client.connect()
    try:
        yield client
    finally:
        client.disconnect()


def get_graph_query_service(
    client: Annotated[AgeGraphClient, Depends(get_age_graph_client)],
    probe: Annotated[GraphServiceProbe, Depends(get_graph_service_probe)],
    graph_id: str = get_database_settings().graph_name,
) -> GraphQueryService:
    """Get GraphQueryService for scoped read operations.

    Args:
        client: Request-scoped graph client
        probe: Graph service probe for observability
        graph_id: Data source ID for query scoping

    Returns:
        GraphQueryService instance
    """
    repository = GraphExtractionReadOnlyRepository(
        client=client,
        graph_id=graph_id,
    )
    return GraphQueryService(repository=repository, probe=probe)


def get_mutation_applier(
    client: Annotated[AgeGraphClient, Depends(get_age_graph_client)],
) -> MutationApplier:
    """Get MutationApplier instance.

    Args:
        client: Request-scoped graph client

    Returns:
        MutationApplier instance with AGE bulk loading strategy
    """
    # AgeBulkLoadingStrategy creates its own AgeIndexingStrategy by default
    strategy = AgeBulkLoadingStrategy()
    return MutationApplier(client=client, bulk_loading_strategy=strategy)


@lru_cache
def get_type_definition_repository() -> ITypeDefinitionRepository:
    """Get type definition repository (in-memory for MVP).

    Returns:
        In-memory type definition repository
    """
    return InMemoryTypeDefinitionRepository()


def get_graph_mutation_service(
    applier: Annotated[MutationApplier, Depends(get_mutation_applier)],
    type_def_repo: Annotated[
        ITypeDefinitionRepository, Depends(get_type_definition_repository)
    ],
) -> GraphMutationService:
    """Get GraphMutationService instance.

    Args:
        applier: Mutation applier
        type_def_repo: Type definition repository

    Returns:
        GraphMutationService instance
    """
    return GraphMutationService(
        mutation_applier=applier,
        type_definition_repository=type_def_repo,
    )


def get_schema_service(
    type_def_repo: Annotated[
        ITypeDefinitionRepository, Depends(get_type_definition_repository)
    ],
    probe: Annotated[SchemaServiceProbe, Depends(get_schema_service_probe)],
) -> GraphSchemaService:
    """Get GraphSchemaService instance.

    Args:
        type_def_repo: Type definition repository
        probe: Schema service probe for observability

    Returns:
        GraphSchemaService instance
    """
    return GraphSchemaService(type_definition_repository=type_def_repo, probe=probe)
