"""FastAPI routes for KnowledgeGraph management."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from iam.application.value_objects import CurrentUser
from iam.dependencies.user import get_current_user
from management.application.services.knowledge_graph_service import (
    KnowledgeGraphService,
)
from management.dependencies.services import get_kg_service
from management.ports.exceptions import UnauthorizedError
from management.presentation.knowledge_graphs.models import (
    CreateKnowledgeGraphRequest,
    KnowledgeGraphResponse,
)

router = APIRouter(
    prefix="/knowledge-graphs",
    tags=["knowledge-graphs"],
)


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    response_model=KnowledgeGraphResponse,
)
async def create_knowledge_graph(
    workspace_id: str,
    request: CreateKnowledgeGraphRequest,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    service: Annotated[KnowledgeGraphService, Depends(get_kg_service)],
) -> KnowledgeGraphResponse:
    """Create a new KnowledgeGraph within a workspace.

    Args:
        workspace_id: The workspace to create the KG in (query param).
        request: KG creation request (name, description).
        current_user: Authenticated user with tenant context.
        service: KnowledgeGraphService for orchestration.

    Returns:
        KnowledgeGraphResponse with created KG details.

    Raises:
        HTTPException: 500 for unexpected errors.
    """
    try:
        kg = await service.create_knowledge_graph(
            name=request.name,
            workspace_id=workspace_id,
            description=request.description,
            created_by=current_user.user_id.value,
        )
        return KnowledgeGraphResponse.from_domain(kg)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create knowledge graph",
        )


@router.get(
    "/{kg_id}",
    response_model=KnowledgeGraphResponse,
)
async def get_knowledge_graph(
    kg_id: str,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    service: Annotated[KnowledgeGraphService, Depends(get_kg_service)],
) -> KnowledgeGraphResponse:
    """Get a KnowledgeGraph by ID.

    Args:
        kg_id: The KnowledgeGraph ID (ULID).
        current_user: Authenticated user with tenant context.
        service: KnowledgeGraphService for orchestration.

    Returns:
        KnowledgeGraphResponse with KG details.

    Raises:
        HTTPException: 403 if user lacks VIEW permission.
        HTTPException: 404 if KG not found.
    """
    try:
        kg = await service.get_knowledge_graph(
            kg_id=kg_id,
            user_id=current_user.user_id.value,
        )
    except UnauthorizedError:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions to view this knowledge graph",
        )

    if kg is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Knowledge graph not found",
        )
    return KnowledgeGraphResponse.from_domain(kg)


@router.get(
    "",
    response_model=list[KnowledgeGraphResponse],
)
async def list_knowledge_graphs(
    workspace_id: str,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    service: Annotated[KnowledgeGraphService, Depends(get_kg_service)],
) -> list[KnowledgeGraphResponse]:
    """List all KnowledgeGraphs in a workspace.

    Args:
        workspace_id: The workspace to list KGs for (query param).
        current_user: Authenticated user with tenant context.
        service: KnowledgeGraphService for orchestration.

    Returns:
        List of KnowledgeGraphResponse.
    """
    kgs = await service.list_knowledge_graphs(workspace_id=workspace_id)
    return [KnowledgeGraphResponse.from_domain(kg) for kg in kgs]


@router.delete(
    "/{kg_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_knowledge_graph(
    kg_id: str,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    service: Annotated[KnowledgeGraphService, Depends(get_kg_service)],
) -> None:
    """Delete a KnowledgeGraph by ID.

    Args:
        kg_id: The KnowledgeGraph ID (ULID).
        current_user: Authenticated user with tenant context.
        service: KnowledgeGraphService for orchestration.

    Raises:
        HTTPException: 403 if user lacks MANAGE permission.
        HTTPException: 404 if KG not found.
    """
    try:
        result = await service.delete_knowledge_graph(
            kg_id=kg_id,
            user_id=current_user.user_id.value,
        )
    except UnauthorizedError:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions to delete this knowledge graph",
        )

    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Knowledge graph not found",
        )
