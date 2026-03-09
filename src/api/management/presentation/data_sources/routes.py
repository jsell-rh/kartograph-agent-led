"""FastAPI routes for DataSource management."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from iam.application.value_objects import CurrentUser
from iam.dependencies.user import get_current_user
from management.application.services.data_source_service import DataSourceService
from management.dependencies.services import get_ds_service
from management.ports.exceptions import UnauthorizedError
from management.presentation.data_sources.models import (
    CreateDataSourceRequest,
    DataSourceResponse,
)

router = APIRouter(
    prefix="/data-sources",
    tags=["data-sources"],
)


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    response_model=DataSourceResponse,
)
async def create_data_source(
    knowledge_graph_id: str,
    request: CreateDataSourceRequest,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    service: Annotated[DataSourceService, Depends(get_ds_service)],
) -> DataSourceResponse:
    """Create a new DataSource within a KnowledgeGraph.

    If credentials are provided in the request body, they are encrypted
    with Fernet and stored in the management_credentials table.
    Credentials are never returned in any response.

    Args:
        knowledge_graph_id: The KG to create the DataSource in (query param).
        request: DataSource creation request.
        current_user: Authenticated user with tenant context.
        service: DataSourceService for orchestration.

    Returns:
        DataSourceResponse (credentials never included).

    Raises:
        HTTPException: 500 for unexpected errors.
    """
    try:
        ds = await service.create_data_source(
            knowledge_graph_id=knowledge_graph_id,
            name=request.name,
            adapter_type=request.adapter_type,
            connection_config=request.connection_config,
            credentials=request.credentials,
            created_by=current_user.user_id.value,
        )
        return DataSourceResponse.from_domain(ds)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create data source",
        )


@router.get(
    "/{ds_id}",
    response_model=DataSourceResponse,
)
async def get_data_source(
    ds_id: str,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    service: Annotated[DataSourceService, Depends(get_ds_service)],
) -> DataSourceResponse:
    """Get a DataSource by ID.

    Args:
        ds_id: The DataSource ID (ULID).
        current_user: Authenticated user with tenant context.
        service: DataSourceService for orchestration.

    Returns:
        DataSourceResponse.

    Raises:
        HTTPException: 403 if user lacks VIEW permission.
        HTTPException: 404 if DataSource not found.
    """
    try:
        ds = await service.get_data_source(
            ds_id=ds_id,
            user_id=current_user.user_id.value,
        )
    except UnauthorizedError:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions to view this data source",
        )

    if ds is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Data source not found",
        )
    return DataSourceResponse.from_domain(ds)


@router.get(
    "",
    response_model=list[DataSourceResponse],
)
async def list_data_sources(
    knowledge_graph_id: str,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    service: Annotated[DataSourceService, Depends(get_ds_service)],
) -> list[DataSourceResponse]:
    """List all DataSources in a KnowledgeGraph.

    Args:
        knowledge_graph_id: The KG to list data sources for (query param).
        current_user: Authenticated user with tenant context.
        service: DataSourceService for orchestration.

    Returns:
        List of DataSourceResponse.
    """
    sources = await service.list_data_sources(knowledge_graph_id=knowledge_graph_id)
    return [DataSourceResponse.from_domain(ds) for ds in sources]


@router.delete(
    "/{ds_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_data_source(
    ds_id: str,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    service: Annotated[DataSourceService, Depends(get_ds_service)],
) -> None:
    """Delete a DataSource and its encrypted credentials.

    Also deletes any credentials stored in management_credentials.

    Args:
        ds_id: The DataSource ID (ULID).
        current_user: Authenticated user with tenant context.
        service: DataSourceService for orchestration.

    Raises:
        HTTPException: 403 if user lacks MANAGE permission.
        HTTPException: 404 if DataSource not found.
    """
    try:
        result = await service.delete_data_source(
            ds_id=ds_id,
            user_id=current_user.user_id.value,
        )
    except UnauthorizedError:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions to delete this data source",
        )

    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Data source not found",
        )
