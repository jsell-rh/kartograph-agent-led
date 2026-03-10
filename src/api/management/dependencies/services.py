"""Dependency injection factories for Management bounded context.

Provides FastAPI dependencies for KnowledgeGraphService and DataSourceService.
Follows the IAM context pattern: session-scoped, per-tenant services.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from iam.application.value_objects import CurrentUser
from iam.dependencies.user import get_current_user
from infrastructure.authorization_dependencies import get_spicedb_client
from infrastructure.database.dependencies import get_write_session
from infrastructure.outbox.repository import OutboxRepository
from infrastructure.settings import get_management_settings
from management.application.services.data_source_service import DataSourceService
from management.application.services.knowledge_graph_service import (
    KnowledgeGraphService,
)
from management.infrastructure.data_source_repository import DataSourceRepository
from management.infrastructure.fernet_credential_store import FernetCredentialStore
from management.infrastructure.knowledge_graph_repository import (
    KnowledgeGraphRepository,
)
from shared_kernel.authorization.protocols import AuthorizationProvider


def get_outbox_repository(
    session: Annotated[AsyncSession, Depends(get_write_session)],
) -> OutboxRepository:
    """Get OutboxRepository instance for Management context.

    Args:
        session: Async write session

    Returns:
        OutboxRepository backed by the write session
    """
    from infrastructure.outbox.repository import OutboxRepository

    return OutboxRepository(session=session)


def get_kg_repository(
    session: Annotated[AsyncSession, Depends(get_write_session)],
    outbox: Annotated[OutboxRepository, Depends(get_outbox_repository)],
) -> KnowledgeGraphRepository:
    """Get KnowledgeGraphRepository instance.

    Args:
        session: Async write session
        outbox: Outbox repository for transactional outbox pattern

    Returns:
        KnowledgeGraphRepository instance
    """
    return KnowledgeGraphRepository(session=session, outbox=outbox)


def get_ds_repository(
    session: Annotated[AsyncSession, Depends(get_write_session)],
    outbox: Annotated[OutboxRepository, Depends(get_outbox_repository)],
) -> DataSourceRepository:
    """Get DataSourceRepository instance.

    Args:
        session: Async write session
        outbox: Outbox repository for transactional outbox pattern

    Returns:
        DataSourceRepository instance
    """
    return DataSourceRepository(session=session, outbox=outbox)


def get_fernet_credential_store(
    session: Annotated[AsyncSession, Depends(get_write_session)],
) -> FernetCredentialStore:
    """Get FernetCredentialStore instance configured from settings.

    Args:
        session: Async write session

    Returns:
        FernetCredentialStore instance

    Raises:
        ValueError: If KARTOGRAPH_MANAGEMENT_FERNET_KEY is not configured.
    """
    settings = get_management_settings()
    return FernetCredentialStore(
        session=session,
        fernet_key=settings.fernet_key.get_secret_value(),
    )


def get_kg_service(
    session: Annotated[AsyncSession, Depends(get_write_session)],
    kg_repo: Annotated[KnowledgeGraphRepository, Depends(get_kg_repository)],
    ds_repo: Annotated[DataSourceRepository, Depends(get_ds_repository)],
    credential_store: Annotated[
        FernetCredentialStore, Depends(get_fernet_credential_store)
    ],
    authz: Annotated[AuthorizationProvider, Depends(get_spicedb_client)],
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
) -> KnowledgeGraphService:
    """Get KnowledgeGraphService scoped to the current user's tenant.

    Args:
        session: Async write session
        kg_repo: KnowledgeGraph repository
        ds_repo: DataSource repository for cascade deletion
        credential_store: Fernet credential store for cascade credential cleanup
        authz: SpiceDB authorization provider
        current_user: Authenticated user with tenant context

    Returns:
        KnowledgeGraphService scoped to current_user.tenant_id
    """
    return KnowledgeGraphService(
        session=session,
        kg_repository=kg_repo,
        authz=authz,
        tenant_id=current_user.tenant_id.value,
        ds_repository=ds_repo,
        credential_store=credential_store,
    )


def get_ds_service(
    session: Annotated[AsyncSession, Depends(get_write_session)],
    ds_repo: Annotated[DataSourceRepository, Depends(get_ds_repository)],
    authz: Annotated[AuthorizationProvider, Depends(get_spicedb_client)],
    credential_store: Annotated[
        FernetCredentialStore, Depends(get_fernet_credential_store)
    ],
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
) -> DataSourceService:
    """Get DataSourceService scoped to the current user's tenant.

    Args:
        session: Async write session
        ds_repo: DataSource repository
        authz: SpiceDB authorization provider
        credential_store: Fernet credential store
        current_user: Authenticated user with tenant context

    Returns:
        DataSourceService scoped to current_user.tenant_id
    """
    return DataSourceService(
        session=session,
        ds_repository=ds_repo,
        authz=authz,
        credential_store=credential_store,
        tenant_id=current_user.tenant_id.value,
    )
