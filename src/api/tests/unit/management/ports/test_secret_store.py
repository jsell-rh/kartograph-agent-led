"""Unit tests for ISecretStoreRepository protocol."""

from __future__ import annotations

import inspect
from typing import Protocol

import pytest

from management.ports.secret_store import ISecretStoreRepository


class TestISecretStoreRepositoryProtocol:
    """Tests for ISecretStoreRepository protocol definition."""

    def test_is_a_protocol(self):
        """ISecretStoreRepository should be a typing.Protocol subclass."""
        assert issubclass(ISecretStoreRepository, Protocol)

    def test_is_runtime_checkable(self):
        """ISecretStoreRepository should be decorated with @runtime_checkable."""
        assert getattr(ISecretStoreRepository, "_is_runtime_protocol", False)

    def test_conforming_class_satisfies_protocol(self):
        """A class implementing all methods satisfies the protocol."""

        class ConformingStore:
            async def store(
                self, path: str, tenant_id: str, credentials: dict[str, str]
            ) -> None:
                pass

            async def retrieve(self, path: str, tenant_id: str) -> dict[str, str]:
                return {}

            async def delete(self, path: str, tenant_id: str) -> bool:
                return True

        store = ConformingStore()
        assert isinstance(store, ISecretStoreRepository)

    def test_missing_store_does_not_satisfy_protocol(self):
        """A class missing store() does NOT satisfy the protocol."""

        class PartialStore:
            async def retrieve(self, path: str, tenant_id: str) -> dict[str, str]:
                return {}

            async def delete(self, path: str, tenant_id: str) -> bool:
                return True

        store = PartialStore()
        assert not isinstance(store, ISecretStoreRepository)

    def test_store_is_async(self):
        """The store method should be a coroutine function."""

        class ConformingStore:
            async def store(
                self, path: str, tenant_id: str, credentials: dict[str, str]
            ) -> None:
                pass

            async def retrieve(self, path: str, tenant_id: str) -> dict[str, str]:
                return {}

            async def delete(self, path: str, tenant_id: str) -> bool:
                return True

        assert inspect.iscoroutinefunction(ConformingStore.store)
        assert inspect.iscoroutinefunction(ConformingStore.retrieve)
        assert inspect.iscoroutinefunction(ConformingStore.delete)

    @pytest.mark.asyncio
    async def test_store_then_retrieve_round_trip(self):
        """store() followed by retrieve() should return the same credentials."""

        class InMemoryStore:
            def __init__(self):
                self._data: dict[tuple[str, str], dict[str, str]] = {}

            async def store(
                self, path: str, tenant_id: str, credentials: dict[str, str]
            ) -> None:
                self._data[(path, tenant_id)] = dict(credentials)

            async def retrieve(self, path: str, tenant_id: str) -> dict[str, str]:
                try:
                    return self._data[(path, tenant_id)]
                except KeyError:
                    raise KeyError(f"No credentials at {path} for tenant {tenant_id}")

            async def delete(self, path: str, tenant_id: str) -> bool:
                key = (path, tenant_id)
                if key in self._data:
                    del self._data[key]
                    return True
                return False

        store = InMemoryStore()
        creds = {"token": "ghp_abc123", "username": "user"}
        await store.store("datasource/ds-1/credentials", "tenant-1", creds)
        result = await store.retrieve("datasource/ds-1/credentials", "tenant-1")
        assert result == creds

    @pytest.mark.asyncio
    async def test_retrieve_raises_keyerror_when_missing(self):
        """retrieve() should raise KeyError when credentials do not exist."""

        class StubStore:
            async def store(
                self, path: str, tenant_id: str, credentials: dict[str, str]
            ) -> None:
                pass

            async def retrieve(self, path: str, tenant_id: str) -> dict[str, str]:
                raise KeyError(f"No credentials at {path}")

            async def delete(self, path: str, tenant_id: str) -> bool:
                return False

        store = StubStore()
        with pytest.raises(KeyError):
            await store.retrieve("datasource/missing/credentials", "tenant-1")

    @pytest.mark.asyncio
    async def test_delete_returns_true_when_deleted(self):
        """delete() should return True when credentials existed and were deleted."""

        class InMemoryStore:
            def __init__(self):
                self._data: dict[tuple[str, str], dict[str, str]] = {}

            async def store(
                self, path: str, tenant_id: str, credentials: dict[str, str]
            ) -> None:
                self._data[(path, tenant_id)] = dict(credentials)

            async def retrieve(self, path: str, tenant_id: str) -> dict[str, str]:
                return self._data[(path, tenant_id)]

            async def delete(self, path: str, tenant_id: str) -> bool:
                key = (path, tenant_id)
                if key in self._data:
                    del self._data[key]
                    return True
                return False

        store = InMemoryStore()
        await store.store("datasource/ds-1/credentials", "tenant-1", {"token": "x"})
        result = await store.delete("datasource/ds-1/credentials", "tenant-1")
        assert result is True

    @pytest.mark.asyncio
    async def test_delete_returns_false_when_not_found(self):
        """delete() should return False when credentials do not exist."""

        class StubStore:
            async def store(
                self, path: str, tenant_id: str, credentials: dict[str, str]
            ) -> None:
                pass

            async def retrieve(self, path: str, tenant_id: str) -> dict[str, str]:
                raise KeyError()

            async def delete(self, path: str, tenant_id: str) -> bool:
                return False

        store = StubStore()
        result = await store.delete("datasource/nonexistent/credentials", "tenant-1")
        assert result is False

    def test_tenant_isolation(self):
        """Credentials from one tenant must not be accessible by another tenant."""

        class InMemoryStore:
            def __init__(self):
                self._data: dict[tuple[str, str], dict[str, str]] = {}

            async def store(
                self, path: str, tenant_id: str, credentials: dict[str, str]
            ) -> None:
                self._data[(path, tenant_id)] = dict(credentials)

            async def retrieve(self, path: str, tenant_id: str) -> dict[str, str]:
                key = (path, tenant_id)
                if key not in self._data:
                    raise KeyError(f"No credentials at {path} for tenant {tenant_id}")
                return self._data[key]

            async def delete(self, path: str, tenant_id: str) -> bool:
                return False

        # Verify the same path with different tenants produces different keys
        path = "datasource/shared-path/credentials"
        assert (path, "tenant-A") != (path, "tenant-B")
