"""DataSource application service for Management bounded context.

Orchestrates DataSource CRUD with SpiceDB authorization and Fernet
credential encryption. Follows the IAM context pattern.
"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from management.domain.aggregates import DataSource
from management.domain.value_objects import DataSourceId
from management.ports.exceptions import UnauthorizedError
from management.ports.repositories import IDataSourceRepository
from management.ports.secret_store import ISecretStoreRepository, credential_path_for
from shared_kernel.authorization.protocols import AuthorizationProvider
from shared_kernel.authorization.types import (
    Permission,
    ResourceType,
    format_resource,
    format_subject,
)
from shared_kernel.datasource_types import DataSourceAdapterType


class DataSourceService:
    """Application service for DataSource management.

    Scoped to a single tenant. Manages DataSource CRUD with:
    - SpiceDB authorization for access control
    - Fernet credential encryption via ISecretStoreRepository
    """

    def __init__(
        self,
        session: AsyncSession,
        ds_repository: IDataSourceRepository,
        authz: AuthorizationProvider,
        credential_store: ISecretStoreRepository,
        tenant_id: str,
    ) -> None:
        """Initialize DataSourceService.

        Args:
            session: Async database session for transaction management.
            ds_repository: Repository for DataSource persistence.
            authz: Authorization provider for SpiceDB permission checks.
            credential_store: Secret store for encrypted credential management.
            tenant_id: The tenant this service is scoped to.
        """
        self._session = session
        self._ds_repository = ds_repository
        self._authz = authz
        self._credential_store = credential_store
        self._tenant_id = tenant_id

    async def _check_ds_permission(
        self,
        ds_id: str,
        user_id: str,
        permission: Permission,
    ) -> bool:
        """Check if user has the given permission on a DataSource resource.

        Args:
            ds_id: The DataSource ID.
            user_id: The user requesting access.
            permission: The permission to check.

        Returns:
            True if authorized, False otherwise.
        """
        resource = format_resource(ResourceType.DATA_SOURCE, ds_id)
        subject = format_subject(ResourceType.USER, user_id)
        return await self._authz.check_permission(
            resource=resource,
            permission=permission,
            subject=subject,
        )

    async def create_data_source(
        self,
        knowledge_graph_id: str,
        name: str,
        adapter_type: DataSourceAdapterType,
        connection_config: dict[str, str],
        created_by: str,
        credentials: dict[str, str] | None = None,
    ) -> DataSource:
        """Create a new DataSource, optionally storing encrypted credentials.

        If credentials are provided, they are encrypted with Fernet and stored
        in the management_credentials table. The resulting path is recorded on
        the DataSource aggregate.

        Args:
            knowledge_graph_id: The KG this DataSource belongs to.
            name: The DataSource name (1-100 characters).
            adapter_type: The adapter type (e.g., GITHUB).
            connection_config: Adapter-specific connection config (no secrets).
            created_by: The user creating the DataSource.
            credentials: Optional dict of credentials to encrypt and store.

        Returns:
            The newly created DataSource aggregate.
        """
        async with self._session.begin():
            ds = DataSource.create(
                knowledge_graph_id=knowledge_graph_id,
                tenant_id=self._tenant_id,
                name=name,
                adapter_type=adapter_type,
                connection_config=connection_config,
                created_by=created_by,
            )

            if credentials:
                path = credential_path_for(ds.id.value)
                await self._credential_store.store(
                    path=path,
                    tenant_id=self._tenant_id,
                    credentials=credentials,
                )
                ds.update_connection(
                    name=ds.name,
                    connection_config=ds.connection_config,
                    credentials_path=path,
                    updated_by=created_by,
                )
                # Collect and discard the update event — create event is sufficient
                ds.collect_events()
                # Re-record only the create event for outbox
                # (the update_connection above cleared events — re-create)
                ds2 = DataSource.create(
                    knowledge_graph_id=knowledge_graph_id,
                    tenant_id=self._tenant_id,
                    name=name,
                    adapter_type=adapter_type,
                    connection_config=connection_config,
                    credentials_path=path,
                    created_by=created_by,
                )
                await self._ds_repository.save(ds2)
                return ds2

            await self._ds_repository.save(ds)
        return ds

    async def get_data_source(self, ds_id: str, user_id: str) -> DataSource | None:
        """Retrieve a DataSource by ID with VIEW permission check.

        Args:
            ds_id: The DataSource ID.
            user_id: The user requesting access.

        Returns:
            The DataSource aggregate, or None if not found.

        Raises:
            UnauthorizedError: If user lacks VIEW permission.
        """
        ds = await self._ds_repository.get_by_id(DataSourceId(value=ds_id))
        if ds is None:
            return None

        authorized = await self._check_ds_permission(ds_id, user_id, Permission.VIEW)
        if not authorized:
            raise UnauthorizedError(
                f"User {user_id!r} lacks VIEW permission on data_source {ds_id!r}"
            )
        return ds

    async def list_data_sources(self, knowledge_graph_id: str) -> list[DataSource]:
        """List all DataSources in a KnowledgeGraph for this service's tenant.

        No per-DataSource authorization check — KG-level access is assumed
        to have been verified by the presentation layer.

        Args:
            knowledge_graph_id: The KG to list data sources for.

        Returns:
            List of DataSource aggregates.
        """
        return await self._ds_repository.list_by_knowledge_graph(
            knowledge_graph_id=knowledge_graph_id,
            tenant_id=self._tenant_id,
        )

    async def delete_data_source(self, ds_id: str, user_id: str) -> bool:
        """Delete a DataSource and its encrypted credentials.

        Checks MANAGE permission, deletes credentials from the secret store
        (if any), marks the aggregate for deletion, and persists via repository
        (which writes the domain event to outbox for SpiceDB cleanup).

        Args:
            ds_id: The DataSource ID.
            user_id: The user requesting deletion.

        Returns:
            True if the DataSource was deleted, False if it was not found.

        Raises:
            UnauthorizedError: If user lacks MANAGE permission.
        """
        async with self._session.begin():
            ds = await self._ds_repository.get_by_id(DataSourceId(value=ds_id))
            if ds is None:
                return False

            authorized = await self._check_ds_permission(
                ds_id, user_id, Permission.MANAGE
            )
            if not authorized:
                raise UnauthorizedError(
                    f"User {user_id!r} lacks MANAGE permission on data_source {ds_id!r}"
                )

            # Delete credentials first (before marking aggregate deleted)
            if ds.credentials_path:
                await self._credential_store.delete(
                    path=ds.credentials_path,
                    tenant_id=self._tenant_id,
                )

            ds.mark_for_deletion(deleted_by=user_id)
            await self._ds_repository.delete(ds)
        return True
