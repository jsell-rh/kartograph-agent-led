"""Pydantic models for DataSource API requests and responses."""

from __future__ import annotations

from pydantic import BaseModel, Field

from management.domain.aggregates import DataSource
from shared_kernel.datasource_types import DataSourceAdapterType


class CreateDataSourceRequest(BaseModel):
    """Request model for creating a DataSource."""

    name: str = Field(..., description="DataSource name", min_length=1, max_length=100)
    adapter_type: DataSourceAdapterType = Field(
        ..., description="Adapter type (e.g. github)"
    )
    connection_config: dict[str, str] = Field(
        default_factory=dict,
        description="Adapter-specific connection config (no secrets)",
    )
    credentials: dict[str, str] | None = Field(
        default=None,
        description="Optional credentials to encrypt and store (e.g. {token: ghp_...})",
    )


class DataSourceResponse(BaseModel):
    """Response model for a DataSource."""

    id: str = Field(..., description="DataSource ID (ULID)")
    tenant_id: str = Field(..., description="Owning tenant ID")
    knowledge_graph_id: str = Field(..., description="Parent KnowledgeGraph ID")
    name: str = Field(..., description="DataSource name")
    adapter_type: str = Field(..., description="Adapter type")
    connection_config: dict[str, str] = Field(..., description="Connection config")
    has_credentials: bool = Field(
        ..., description="Whether encrypted credentials are stored"
    )
    schedule_type: str = Field(..., description="Schedule type (manual/cron/interval)")
    schedule_value: str | None = Field(..., description="Schedule expression or None")

    @classmethod
    def from_domain(cls, ds: DataSource) -> DataSourceResponse:
        """Convert a DataSource domain aggregate to API response.

        Credentials are never exposed in the response — only a boolean
        indicating whether credentials are stored.

        Args:
            ds: DataSource aggregate

        Returns:
            DataSourceResponse
        """
        return cls(
            id=ds.id.value,
            tenant_id=ds.tenant_id,
            knowledge_graph_id=ds.knowledge_graph_id,
            name=ds.name,
            adapter_type=ds.adapter_type.value,
            connection_config=dict(ds.connection_config),
            has_credentials=ds.credentials_path is not None,
            schedule_type=ds.schedule.schedule_type.value,
            schedule_value=ds.schedule.value,
        )
