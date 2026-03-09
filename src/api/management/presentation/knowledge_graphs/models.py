"""Pydantic models for KnowledgeGraph API requests and responses."""

from __future__ import annotations

from pydantic import BaseModel, Field

from management.domain.aggregates import KnowledgeGraph


class CreateKnowledgeGraphRequest(BaseModel):
    """Request model for creating a KnowledgeGraph."""

    name: str = Field(
        ..., description="KnowledgeGraph name", min_length=1, max_length=100
    )
    description: str = Field(default="", description="Optional description")


class UpdateKnowledgeGraphRequest(BaseModel):
    """Request model for updating a KnowledgeGraph."""

    name: str = Field(
        ..., description="KnowledgeGraph name", min_length=1, max_length=100
    )
    description: str = Field(default="", description="Optional description")


class KnowledgeGraphResponse(BaseModel):
    """Response model for a KnowledgeGraph."""

    id: str = Field(..., description="KnowledgeGraph ID (ULID)")
    tenant_id: str = Field(..., description="Owning tenant ID")
    workspace_id: str = Field(..., description="Parent workspace ID")
    name: str = Field(..., description="KnowledgeGraph name")
    description: str = Field(..., description="Optional description")

    @classmethod
    def from_domain(cls, kg: KnowledgeGraph) -> KnowledgeGraphResponse:
        """Convert a KnowledgeGraph domain aggregate to API response.

        Args:
            kg: KnowledgeGraph aggregate

        Returns:
            KnowledgeGraphResponse
        """
        return cls(
            id=kg.id.value,
            tenant_id=kg.tenant_id,
            workspace_id=kg.workspace_id,
            name=kg.name,
            description=kg.description,
        )
