"""KnowledgeGraph application service for Management bounded context.

Orchestrates KnowledgeGraph CRUD operations with SpiceDB authorization checks.
Follows the IAM context pattern: session-scoped, per-tenant, authz-checked.
"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from management.domain.aggregates import KnowledgeGraph
from management.domain.value_objects import KnowledgeGraphId
from management.ports.exceptions import UnauthorizedError
from management.ports.repositories import (
    IDataSourceRepository,
    IKnowledgeGraphRepository,
)
from management.ports.secret_store import ISecretStoreRepository
from shared_kernel.authorization.protocols import AuthorizationProvider
from shared_kernel.authorization.types import (
    Permission,
    ResourceType,
    format_resource,
    format_subject,
)


class KnowledgeGraphService:
    """Application service for KnowledgeGraph management.

    Scoped to a single tenant. Authorization is checked against SpiceDB
    using the workspace resource (KGs inherit workspace permissions).
    """

    def __init__(
        self,
        session: AsyncSession,
        kg_repository: IKnowledgeGraphRepository,
        authz: AuthorizationProvider,
        tenant_id: str,
        ds_repository: IDataSourceRepository | None = None,
        credential_store: ISecretStoreRepository | None = None,
    ) -> None:
        """Initialize KnowledgeGraphService.

        Args:
            session: Async database session for transaction management.
            kg_repository: Repository for KnowledgeGraph persistence.
            authz: Authorization provider for SpiceDB permission checks.
            tenant_id: The tenant this service is scoped to.
            ds_repository: DataSource repository for cascade deletion on KG delete.
            credential_store: Secret store for credential cleanup on cascade deletion.
        """
        self._session = session
        self._kg_repository = kg_repository
        self._authz = authz
        self._tenant_id = tenant_id
        self._ds_repository = ds_repository
        self._credential_store = credential_store

    async def _check_kg_permission(
        self,
        kg_id: str,
        user_id: str,
        permission: Permission,
    ) -> bool:
        """Check if user has the given permission on a KnowledgeGraph resource.

        Args:
            kg_id: The KnowledgeGraph ID.
            user_id: The user requesting access.
            permission: The permission to check (VIEW, EDIT, MANAGE).

        Returns:
            True if authorized, False otherwise.
        """
        resource = format_resource(ResourceType.KNOWLEDGE_GRAPH, kg_id)
        subject = format_subject(ResourceType.USER, user_id)
        return await self._authz.check_permission(
            resource=resource,
            permission=permission,
            subject=subject,
        )

    async def create_knowledge_graph(
        self,
        name: str,
        workspace_id: str,
        created_by: str,
        description: str = "",
    ) -> KnowledgeGraph:
        """Create a new KnowledgeGraph within a workspace.

        No authorization check on create — workspace membership is assumed
        to have been verified by the caller (presentation layer). The
        KnowledgeGraphCreated event written to the outbox will cause the
        outbox worker to write the SpiceDB relationship.

        Args:
            name: The KnowledgeGraph name (1-100 characters).
            workspace_id: The workspace this KG belongs to.
            created_by: The user creating the KG (for domain event).
            description: Optional description.

        Returns:
            The newly created KnowledgeGraph aggregate.
        """
        async with self._session.begin():
            kg = KnowledgeGraph.create(
                tenant_id=self._tenant_id,
                workspace_id=workspace_id,
                name=name,
                description=description,
                created_by=created_by,
            )
            await self._kg_repository.save(kg)
        return kg

    async def get_knowledge_graph(
        self, kg_id: str, user_id: str
    ) -> KnowledgeGraph | None:
        """Retrieve a KnowledgeGraph by ID with VIEW permission check.

        Args:
            kg_id: The KnowledgeGraph ID.
            user_id: The user requesting access.

        Returns:
            The KnowledgeGraph aggregate, or None if not found.

        Raises:
            UnauthorizedError: If the user lacks VIEW permission.
        """
        kg = await self._kg_repository.get_by_id(KnowledgeGraphId(value=kg_id))
        if kg is None:
            return None

        authorized = await self._check_kg_permission(kg_id, user_id, Permission.VIEW)
        if not authorized:
            raise UnauthorizedError(
                f"User {user_id!r} lacks VIEW permission on knowledge_graph {kg_id!r}"
            )
        return kg

    async def list_knowledge_graphs(self, workspace_id: str) -> list[KnowledgeGraph]:
        """List all KnowledgeGraphs in a workspace scoped to this service's tenant.

        No per-KG authorization check — workspace-level access is assumed
        to have been verified by the presentation layer.

        Args:
            workspace_id: The workspace to list KGs for.

        Returns:
            List of KnowledgeGraph aggregates.
        """
        return await self._kg_repository.list_by_workspace(
            workspace_id=workspace_id,
            tenant_id=self._tenant_id,
        )

    async def delete_knowledge_graph(self, kg_id: str, user_id: str) -> bool:
        """Delete a KnowledgeGraph with MANAGE permission check.

        Retrieves the KG, checks MANAGE permission, cascade-deletes all
        associated DataSources (including their credentials and outbox events),
        then deletes the KG itself — all within a single transaction so the
        database FK constraint on data_sources.knowledge_graph_id is satisfied.

        Args:
            kg_id: The KnowledgeGraph ID.
            user_id: The user requesting deletion.

        Returns:
            True if the KG was deleted, False if it was not found.

        Raises:
            UnauthorizedError: If the user lacks MANAGE permission.
        """
        kg = await self._kg_repository.get_by_id(KnowledgeGraphId(value=kg_id))
        if kg is None:
            return False

        authorized = await self._check_kg_permission(kg_id, user_id, Permission.MANAGE)
        if not authorized:
            raise UnauthorizedError(
                f"User {user_id!r} lacks MANAGE permission on knowledge_graph {kg_id!r}"
            )

        async with self._session.begin():
            # Cascade-delete all DataSources before deleting the KG, so the
            # RESTRICT foreign key constraint on data_sources.knowledge_graph_id
            # is not violated. Each DS deletion emits a DataSourceDeleted outbox
            # event for SpiceDB tuple cleanup.
            if self._ds_repository is not None:
                data_sources = await self._ds_repository.list_by_knowledge_graph(
                    knowledge_graph_id=kg_id,
                    tenant_id=self._tenant_id,
                )
                for ds in data_sources:
                    if self._credential_store is not None and ds.credentials_path:
                        await self._credential_store.delete(
                            path=ds.credentials_path,
                            tenant_id=self._tenant_id,
                        )
                    ds.mark_for_deletion(deleted_by=user_id)
                    await self._ds_repository.delete(ds)

            kg.mark_for_deletion(deleted_by=user_id)
            await self._kg_repository.delete(kg)
        return True
