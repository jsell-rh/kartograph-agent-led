"""Unit tests for DataSourceService application service."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from management.application.services.data_source_service import DataSourceService
from management.domain.aggregates import DataSource
from management.domain.value_objects import DataSourceId
from management.ports.exceptions import UnauthorizedError
from shared_kernel.datasource_types import DataSourceAdapterType


@pytest.fixture
def mock_session():
    return AsyncMock()


@pytest.fixture
def mock_ds_repository():
    return AsyncMock()


@pytest.fixture
def mock_authz():
    authz = AsyncMock()
    authz.check_permission = AsyncMock(return_value=True)
    return authz


@pytest.fixture
def mock_credential_store():
    store = AsyncMock()
    store.store = AsyncMock()
    store.retrieve = AsyncMock(return_value={"token": "ghp_abc"})
    store.delete = AsyncMock(return_value=True)
    return store


@pytest.fixture
def tenant_id():
    return "tenant-abc"


@pytest.fixture
def service(
    mock_session, mock_ds_repository, mock_authz, mock_credential_store, tenant_id
):
    return DataSourceService(
        session=mock_session,
        ds_repository=mock_ds_repository,
        authz=mock_authz,
        credential_store=mock_credential_store,
        tenant_id=tenant_id,
    )


class TestDataSourceServiceCreate:
    """Tests for create_data_source()."""

    @pytest.mark.asyncio
    async def test_create_without_credentials_returns_datasource(
        self, service, mock_ds_repository
    ):
        """create_data_source() without credentials should return a DataSource."""
        mock_session_ctx = AsyncMock()
        mock_session_ctx.__aenter__ = AsyncMock(return_value=None)
        mock_session_ctx.__aexit__ = AsyncMock(return_value=None)
        service._session.begin = MagicMock(return_value=mock_session_ctx)
        mock_ds_repository.save = AsyncMock()

        ds = await service.create_data_source(
            knowledge_graph_id="kg-1",
            name="GitHub Source",
            adapter_type=DataSourceAdapterType.GITHUB,
            connection_config={"repo": "org/repo"},
            created_by="user-xyz",
        )

        assert isinstance(ds, DataSource)
        assert ds.name == "GitHub Source"
        assert ds.knowledge_graph_id == "kg-1"
        assert ds.tenant_id == "tenant-abc"
        assert ds.credentials_path is None

    @pytest.mark.asyncio
    async def test_create_with_credentials_stores_and_sets_path(
        self, service, mock_ds_repository, mock_credential_store
    ):
        """create_data_source() with credentials should encrypt-store them and set credentials_path."""
        mock_session_ctx = AsyncMock()
        mock_session_ctx.__aenter__ = AsyncMock(return_value=None)
        mock_session_ctx.__aexit__ = AsyncMock(return_value=None)
        service._session.begin = MagicMock(return_value=mock_session_ctx)
        mock_ds_repository.save = AsyncMock()

        ds = await service.create_data_source(
            knowledge_graph_id="kg-1",
            name="GitHub Source",
            adapter_type=DataSourceAdapterType.GITHUB,
            connection_config={"repo": "org/repo"},
            credentials={"token": "ghp_secret"},
            created_by="user-xyz",
        )

        # Credentials should be stored
        mock_credential_store.store.assert_called_once()
        # credentials_path should be set on the aggregate
        assert ds.credentials_path is not None

    @pytest.mark.asyncio
    async def test_create_calls_repository_save(self, service, mock_ds_repository):
        """create_data_source() should call ds_repository.save()."""
        mock_session_ctx = AsyncMock()
        mock_session_ctx.__aenter__ = AsyncMock(return_value=None)
        mock_session_ctx.__aexit__ = AsyncMock(return_value=None)
        service._session.begin = MagicMock(return_value=mock_session_ctx)
        mock_ds_repository.save = AsyncMock()

        await service.create_data_source(
            knowledge_graph_id="kg-1",
            name="GitHub Source",
            adapter_type=DataSourceAdapterType.GITHUB,
            connection_config={"repo": "org/repo"},
            created_by="user-xyz",
        )

        mock_ds_repository.save.assert_called_once()


class TestDataSourceServiceGet:
    """Tests for get_data_source()."""

    @pytest.mark.asyncio
    async def test_get_returns_datasource(
        self, service, mock_ds_repository, mock_authz
    ):
        """get_data_source() should return the DataSource when found and authorized."""
        ds_id = DataSourceId.generate()
        fake_ds = MagicMock(spec=DataSource)
        fake_ds.id = ds_id
        fake_ds.tenant_id = "tenant-abc"
        fake_ds.knowledge_graph_id = "kg-1"
        mock_ds_repository.get_by_id = AsyncMock(return_value=fake_ds)
        mock_authz.check_permission = AsyncMock(return_value=True)

        result = await service.get_data_source(ds_id=ds_id.value, user_id="user-xyz")
        assert result == fake_ds

    @pytest.mark.asyncio
    async def test_get_returns_none_when_not_found(self, service, mock_ds_repository):
        """get_data_source() should return None when DataSource does not exist."""
        mock_ds_repository.get_by_id = AsyncMock(return_value=None)

        result = await service.get_data_source(ds_id="nonexistent", user_id="user-xyz")
        assert result is None

    @pytest.mark.asyncio
    async def test_get_raises_unauthorized(
        self, service, mock_ds_repository, mock_authz
    ):
        """get_data_source() should raise UnauthorizedError if user lacks permission."""
        ds_id = DataSourceId.generate()
        fake_ds = MagicMock(spec=DataSource)
        fake_ds.id = ds_id
        fake_ds.tenant_id = "tenant-abc"
        fake_ds.knowledge_graph_id = "kg-1"
        mock_ds_repository.get_by_id = AsyncMock(return_value=fake_ds)
        mock_authz.check_permission = AsyncMock(return_value=False)

        with pytest.raises(UnauthorizedError):
            await service.get_data_source(ds_id=ds_id.value, user_id="user-xyz")


class TestDataSourceServiceList:
    """Tests for list_data_sources()."""

    @pytest.mark.asyncio
    async def test_list_returns_data_sources(self, service, mock_ds_repository):
        """list_data_sources() should return all data sources for the KG."""
        fake_sources = [MagicMock(spec=DataSource) for _ in range(2)]
        mock_ds_repository.list_by_knowledge_graph = AsyncMock(
            return_value=fake_sources
        )

        result = await service.list_data_sources(knowledge_graph_id="kg-1")
        assert result == fake_sources
        mock_ds_repository.list_by_knowledge_graph.assert_called_once_with(
            knowledge_graph_id="kg-1", tenant_id="tenant-abc"
        )


class TestDataSourceServiceDelete:
    """Tests for delete_data_source()."""

    @pytest.mark.asyncio
    async def test_delete_removes_credentials_and_aggregate(
        self, service, mock_ds_repository, mock_authz, mock_credential_store
    ):
        """delete_data_source() should delete credentials and the aggregate."""
        ds_id = DataSourceId.generate()
        fake_ds = MagicMock(spec=DataSource)
        fake_ds.id = ds_id
        fake_ds.tenant_id = "tenant-abc"
        fake_ds.knowledge_graph_id = "kg-1"
        fake_ds.credentials_path = f"datasource/{ds_id.value}/credentials"
        fake_ds.collect_events = MagicMock(return_value=[])
        mock_ds_repository.get_by_id = AsyncMock(return_value=fake_ds)
        mock_ds_repository.delete = AsyncMock(return_value=True)
        mock_authz.check_permission = AsyncMock(return_value=True)

        mock_session_ctx = AsyncMock()
        mock_session_ctx.__aenter__ = AsyncMock(return_value=None)
        mock_session_ctx.__aexit__ = AsyncMock(return_value=None)
        service._session.begin = MagicMock(return_value=mock_session_ctx)

        await service.delete_data_source(ds_id=ds_id.value, user_id="user-xyz")

        # Credentials should be deleted
        mock_credential_store.delete.assert_called_once()
        # Aggregate should be deleted
        mock_ds_repository.delete.assert_called_once()

    @pytest.mark.asyncio
    async def test_delete_skips_credentials_when_none(
        self, service, mock_ds_repository, mock_authz, mock_credential_store
    ):
        """delete_data_source() should not call credential_store.delete() when credentials_path is None."""
        ds_id = DataSourceId.generate()
        fake_ds = MagicMock(spec=DataSource)
        fake_ds.id = ds_id
        fake_ds.tenant_id = "tenant-abc"
        fake_ds.knowledge_graph_id = "kg-1"
        fake_ds.credentials_path = None
        fake_ds.collect_events = MagicMock(return_value=[])
        mock_ds_repository.get_by_id = AsyncMock(return_value=fake_ds)
        mock_ds_repository.delete = AsyncMock(return_value=True)
        mock_authz.check_permission = AsyncMock(return_value=True)

        mock_session_ctx = AsyncMock()
        mock_session_ctx.__aenter__ = AsyncMock(return_value=None)
        mock_session_ctx.__aexit__ = AsyncMock(return_value=None)
        service._session.begin = MagicMock(return_value=mock_session_ctx)

        await service.delete_data_source(ds_id=ds_id.value, user_id="user-xyz")

        mock_credential_store.delete.assert_not_called()
        mock_ds_repository.delete.assert_called_once()

    @pytest.mark.asyncio
    async def test_delete_raises_unauthorized(
        self, service, mock_ds_repository, mock_authz
    ):
        """delete_data_source() should raise UnauthorizedError if user lacks permission."""
        ds_id = DataSourceId.generate()
        fake_ds = MagicMock(spec=DataSource)
        fake_ds.id = ds_id
        fake_ds.tenant_id = "tenant-abc"
        mock_ds_repository.get_by_id = AsyncMock(return_value=fake_ds)
        mock_authz.check_permission = AsyncMock(return_value=False)

        mock_session_ctx = AsyncMock()
        mock_session_ctx.__aenter__ = AsyncMock(return_value=None)
        mock_session_ctx.__aexit__ = AsyncMock(return_value=None)
        service._session.begin = MagicMock(return_value=mock_session_ctx)

        with pytest.raises(UnauthorizedError):
            await service.delete_data_source(ds_id=ds_id.value, user_id="user-xyz")
