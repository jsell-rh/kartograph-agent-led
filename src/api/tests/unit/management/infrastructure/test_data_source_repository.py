"""Unit tests for DataSourceRepository (TDD - tests first).

Tests verify repository behavior with mocked dependencies.
"""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from management.domain.aggregates import DataSource
from management.domain.value_objects import DataSourceId
from management.infrastructure.data_source_repository import DataSourceRepository
from management.infrastructure.models.data_source import DataSourceModel
from management.ports.repositories import IDataSourceRepository
from shared_kernel.datasource_types import DataSourceAdapterType


TENANT_ID = "01ARZCX0P0HZGQP3MZXQQ0NNYY"
KG_ID = "01ARZCX0P0HZGQP3MZXQQ0NNZZ"
DS_ID = "01ARZCX0P0HZGQP3MZXQQ0NNWW"
NOW = datetime(2026, 1, 8, 12, 0, 0, tzinfo=UTC)


@pytest.fixture
def mock_session() -> AsyncMock:
    return AsyncMock()


@pytest.fixture
def mock_outbox() -> MagicMock:
    outbox = MagicMock()
    outbox.append = AsyncMock()
    return outbox


@pytest.fixture
def mock_serializer() -> MagicMock:
    serializer = MagicMock()
    serializer.serialize.return_value = {"event": "payload"}
    return serializer


@pytest.fixture
def repository(mock_session, mock_outbox, mock_serializer) -> DataSourceRepository:
    return DataSourceRepository(
        session=mock_session,
        outbox=mock_outbox,
        serializer=mock_serializer,
    )


@pytest.fixture
def data_source() -> DataSource:
    return DataSource.create(
        knowledge_graph_id=KG_ID,
        tenant_id=TENANT_ID,
        name="GitHub Source",
        adapter_type=DataSourceAdapterType.GITHUB,
        connection_config={"repo": "org/repo"},
    )


def make_ds_model(ds_id: str = DS_ID) -> DataSourceModel:
    model = DataSourceModel()
    model.id = ds_id
    model.tenant_id = TENANT_ID
    model.knowledge_graph_id = KG_ID
    model.name = "GitHub Source"
    model.adapter_type = "github"
    model.connection_config = {"repo": "org/repo"}
    model.credentials_path = None
    model.schedule_type = "manual"
    model.schedule_value = None
    model.created_at = NOW
    model.updated_at = NOW
    return model


class TestProtocolCompliance:
    def test_implements_protocol(self, repository: DataSourceRepository) -> None:
        assert isinstance(repository, IDataSourceRepository)


class TestSaveNew:
    @pytest.mark.asyncio
    async def test_save_new_adds_model_to_session(
        self,
        repository: DataSourceRepository,
        mock_session: AsyncMock,
        data_source: DataSource,
    ) -> None:
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        await repository.save(data_source)

        mock_session.add.assert_called_once()

    @pytest.mark.asyncio
    async def test_save_new_appends_created_event_to_outbox(
        self,
        repository: DataSourceRepository,
        mock_session: AsyncMock,
        mock_outbox: MagicMock,
        data_source: DataSource,
    ) -> None:
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        await repository.save(data_source)

        mock_outbox.append.assert_called_once()
        call_kwargs = mock_outbox.append.call_args.kwargs
        assert call_kwargs["event_type"] == "DataSourceCreated"
        assert call_kwargs["aggregate_type"] == "data_source"

    @pytest.mark.asyncio
    async def test_save_new_clears_aggregate_events(
        self,
        repository: DataSourceRepository,
        mock_session: AsyncMock,
        data_source: DataSource,
    ) -> None:
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        await repository.save(data_source)

        assert data_source.collect_events() == []


class TestSaveExisting:
    @pytest.mark.asyncio
    async def test_save_existing_updates_model_fields(
        self,
        repository: DataSourceRepository,
        mock_session: AsyncMock,
        data_source: DataSource,
    ) -> None:
        existing_model = make_ds_model(data_source.id.value)
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = existing_model
        mock_session.execute.return_value = mock_result

        data_source.collect_events()
        data_source.update_connection(
            name="Updated Source",
            connection_config={"repo": "org/new-repo"},
            credentials_path=None,
        )

        await repository.save(data_source)

        assert existing_model.name == "Updated Source"
        assert existing_model.connection_config == {"repo": "org/new-repo"}
        mock_session.add.assert_not_called()


class TestGetById:
    @pytest.mark.asyncio
    async def test_returns_data_source_when_found(
        self,
        repository: DataSourceRepository,
        mock_session: AsyncMock,
    ) -> None:
        model = make_ds_model()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = model
        mock_session.execute.return_value = mock_result

        result = await repository.get_by_id(DataSourceId(value=DS_ID))

        assert result is not None
        assert isinstance(result, DataSource)
        assert result.id.value == DS_ID
        assert result.name == "GitHub Source"
        assert result.tenant_id == TENANT_ID
        assert result.knowledge_graph_id == KG_ID
        assert result.adapter_type == DataSourceAdapterType.GITHUB

    @pytest.mark.asyncio
    async def test_returns_none_when_not_found(
        self,
        repository: DataSourceRepository,
        mock_session: AsyncMock,
    ) -> None:
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        result = await repository.get_by_id(DataSourceId(value=DS_ID))

        assert result is None

    @pytest.mark.asyncio
    async def test_returned_aggregate_has_no_pending_events(
        self,
        repository: DataSourceRepository,
        mock_session: AsyncMock,
    ) -> None:
        model = make_ds_model()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = model
        mock_session.execute.return_value = mock_result

        ds = await repository.get_by_id(DataSourceId(value=DS_ID))

        assert ds is not None
        assert ds.collect_events() == []


class TestListByKnowledgeGraph:
    @pytest.mark.asyncio
    async def test_returns_list_of_data_sources(
        self,
        repository: DataSourceRepository,
        mock_session: AsyncMock,
    ) -> None:
        model1 = make_ds_model("01ARZCX0P0HZGQP3MZXQQ0NNA1")
        model2 = make_ds_model("01ARZCX0P0HZGQP3MZXQQ0NNA2")
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = [model1, model2]
        mock_result = MagicMock()
        mock_result.scalars.return_value = mock_scalars
        mock_session.execute.return_value = mock_result

        results = await repository.list_by_knowledge_graph(
            knowledge_graph_id=KG_ID, tenant_id=TENANT_ID
        )

        assert len(results) == 2
        assert all(isinstance(ds, DataSource) for ds in results)

    @pytest.mark.asyncio
    async def test_returns_empty_list_when_none_found(
        self,
        repository: DataSourceRepository,
        mock_session: AsyncMock,
    ) -> None:
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = []
        mock_result = MagicMock()
        mock_result.scalars.return_value = mock_scalars
        mock_session.execute.return_value = mock_result

        results = await repository.list_by_knowledge_graph(
            knowledge_graph_id=KG_ID, tenant_id=TENANT_ID
        )

        assert results == []


class TestDelete:
    @pytest.mark.asyncio
    async def test_delete_returns_true_when_found(
        self,
        repository: DataSourceRepository,
        mock_session: AsyncMock,
        data_source: DataSource,
    ) -> None:
        model = make_ds_model(data_source.id.value)
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = model
        mock_session.execute.return_value = mock_result

        data_source.collect_events()
        data_source.mark_for_deletion()

        result = await repository.delete(data_source)

        assert result is True
        mock_session.delete.assert_called_once_with(model)

    @pytest.mark.asyncio
    async def test_delete_appends_deleted_event_to_outbox(
        self,
        repository: DataSourceRepository,
        mock_session: AsyncMock,
        mock_outbox: MagicMock,
        data_source: DataSource,
    ) -> None:
        model = make_ds_model(data_source.id.value)
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = model
        mock_session.execute.return_value = mock_result

        data_source.collect_events()
        data_source.mark_for_deletion()

        await repository.delete(data_source)

        mock_outbox.append.assert_called_once()
        call_kwargs = mock_outbox.append.call_args.kwargs
        assert call_kwargs["event_type"] == "DataSourceDeleted"

    @pytest.mark.asyncio
    async def test_delete_returns_false_when_not_found(
        self,
        repository: DataSourceRepository,
        mock_session: AsyncMock,
        data_source: DataSource,
    ) -> None:
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        result = await repository.delete(data_source)

        assert result is False
        mock_session.delete.assert_not_called()
