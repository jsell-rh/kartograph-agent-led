"""PostgreSQL implementation of IDataSourceRepository.

Uses the transactional outbox pattern — domain events are appended to
the outbox table within the same database transaction as aggregate changes.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from management.domain.aggregates import DataSource
from management.domain.value_objects import DataSourceId, Schedule, ScheduleType
from management.infrastructure.models import DataSourceModel
from management.infrastructure.outbox.serializer import ManagementEventSerializer
from management.ports.repositories import IDataSourceRepository
from shared_kernel.datasource_types import DataSourceAdapterType

if TYPE_CHECKING:
    from infrastructure.outbox.repository import OutboxRepository


class DataSourceRepository(IDataSourceRepository):
    """Repository for DataSource aggregates backed by PostgreSQL."""

    def __init__(
        self,
        session: AsyncSession,
        outbox: "OutboxRepository",
        serializer: ManagementEventSerializer | None = None,
    ) -> None:
        self._session = session
        self._outbox = outbox
        self._serializer = serializer or ManagementEventSerializer()

    async def save(self, data_source: DataSource) -> None:
        """Persist data source metadata and emit domain events to outbox."""
        stmt = select(DataSourceModel).where(DataSourceModel.id == data_source.id.value)
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()

        if model:
            model.name = data_source.name
            model.connection_config = dict(data_source.connection_config)
            model.credentials_path = data_source.credentials_path
            model.schedule_type = data_source.schedule.schedule_type.value
            model.schedule_value = data_source.schedule.value
            model.updated_at = data_source.updated_at
        else:
            model = DataSourceModel(
                id=data_source.id.value,
                tenant_id=data_source.tenant_id,
                knowledge_graph_id=data_source.knowledge_graph_id,
                name=data_source.name,
                adapter_type=data_source.adapter_type.value,
                connection_config=dict(data_source.connection_config),
                credentials_path=data_source.credentials_path,
                schedule_type=data_source.schedule.schedule_type.value,
                schedule_value=data_source.schedule.value,
                created_at=data_source.created_at,
                updated_at=data_source.updated_at,
            )
            self._session.add(model)

        await self._session.flush()

        events = data_source.collect_events()
        for event in events:
            payload = self._serializer.serialize(event)
            await self._outbox.append(
                event_type=type(event).__name__,
                payload=payload,
                occurred_at=event.occurred_at,
                aggregate_type="data_source",
                aggregate_id=data_source.id.value,
            )

    async def get_by_id(self, data_source_id: DataSourceId) -> DataSource | None:
        """Retrieve a data source by its ID."""
        stmt = select(DataSourceModel).where(DataSourceModel.id == data_source_id.value)
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()

        if model is None:
            return None

        return self._to_domain(model)

    async def list_by_knowledge_graph(
        self,
        knowledge_graph_id: str,
        tenant_id: str,
    ) -> list[DataSource]:
        """List all data sources for a given knowledge graph."""
        stmt = (
            select(DataSourceModel)
            .where(
                DataSourceModel.knowledge_graph_id == knowledge_graph_id,
                DataSourceModel.tenant_id == tenant_id,
            )
            .order_by(DataSourceModel.name)
        )
        result = await self._session.execute(stmt)
        models = result.scalars().all()
        return [self._to_domain(m) for m in models]

    async def delete(self, data_source: DataSource) -> bool:
        """Delete a data source, appending events to outbox."""
        stmt = select(DataSourceModel).where(DataSourceModel.id == data_source.id.value)
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()

        if model is None:
            return False

        events = data_source.collect_events()
        for event in events:
            payload = self._serializer.serialize(event)
            await self._outbox.append(
                event_type=type(event).__name__,
                payload=payload,
                occurred_at=event.occurred_at,
                aggregate_type="data_source",
                aggregate_id=data_source.id.value,
            )

        await self._session.delete(model)
        await self._session.flush()
        return True

    def _to_domain(self, model: DataSourceModel) -> DataSource:
        """Reconstitute DataSource aggregate from ORM model (no events generated)."""
        return DataSource(
            id=DataSourceId(value=model.id),
            knowledge_graph_id=model.knowledge_graph_id,
            tenant_id=model.tenant_id,
            name=model.name,
            adapter_type=DataSourceAdapterType(model.adapter_type),
            connection_config=dict(model.connection_config or {}),
            credentials_path=model.credentials_path,
            schedule=Schedule(
                schedule_type=ScheduleType(model.schedule_type),
                value=model.schedule_value,
            ),
            last_sync_at=None,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )
