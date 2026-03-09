"""Unit tests for FernetCredentialStore infrastructure implementation."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from cryptography.fernet import Fernet

from management.infrastructure.fernet_credential_store import FernetCredentialStore
from management.ports.secret_store import ISecretStoreRepository
from shared_kernel.credential_reader import ICredentialReader


@pytest.fixture
def fernet_key() -> str:
    """Generate a valid Fernet key for testing."""
    return Fernet.generate_key().decode()


@pytest.fixture
def mock_session():
    """Create a mock async SQLAlchemy session."""
    session = AsyncMock()
    return session


@pytest.fixture
def store(fernet_key, mock_session):
    """Create a FernetCredentialStore with a test key and mock session."""
    return FernetCredentialStore(session=mock_session, fernet_key=fernet_key)


class TestFernetCredentialStoreProtocolConformance:
    """FernetCredentialStore must satisfy both port protocols."""

    def test_satisfies_secret_store_repository(self, store):
        """FernetCredentialStore should satisfy ISecretStoreRepository."""
        assert isinstance(store, ISecretStoreRepository)

    def test_satisfies_credential_reader(self, store):
        """FernetCredentialStore should satisfy ICredentialReader."""
        assert isinstance(store, ICredentialReader)


class TestFernetCredentialStoreEncryption:
    """Tests for encryption/decryption correctness."""

    def test_encrypt_produces_bytes(self, fernet_key):
        """_encrypt should return bytes."""
        store = FernetCredentialStore(session=MagicMock(), fernet_key=fernet_key)
        result = store._encrypt({"token": "secret"})
        assert isinstance(result, bytes)
        assert len(result) > 0

    def test_encrypt_decrypt_round_trip(self, fernet_key):
        """_encrypt followed by _decrypt should return the original credentials."""
        store = FernetCredentialStore(session=MagicMock(), fernet_key=fernet_key)
        original = {"token": "ghp_abc123", "username": "octocat"}
        encrypted = store._encrypt(original)
        decrypted = store._decrypt(encrypted)
        assert decrypted == original

    def test_encrypt_produces_different_ciphertext_each_time(self, fernet_key):
        """Fernet uses random IV — same plaintext produces different ciphertext."""
        store = FernetCredentialStore(session=MagicMock(), fernet_key=fernet_key)
        creds = {"token": "secret"}
        cipher1 = store._encrypt(creds)
        cipher2 = store._encrypt(creds)
        assert cipher1 != cipher2  # Random IV guarantees this

    def test_wrong_key_cannot_decrypt(self, fernet_key):
        """Credentials encrypted with one key cannot be decrypted with another."""
        from cryptography.fernet import InvalidToken

        store1 = FernetCredentialStore(session=MagicMock(), fernet_key=fernet_key)
        different_key = Fernet.generate_key().decode()
        store2 = FernetCredentialStore(session=MagicMock(), fernet_key=different_key)

        encrypted = store1._encrypt({"token": "secret"})
        with pytest.raises(InvalidToken):
            store2._decrypt(encrypted)

    def test_invalid_fernet_key_raises_on_init(self):
        """Invalid Fernet key should raise ValueError during construction."""
        with pytest.raises(ValueError, match="Invalid Fernet key"):
            FernetCredentialStore(
                session=MagicMock(), fernet_key="not-a-valid-fernet-key"
            )

    def test_empty_credentials_round_trip(self, fernet_key):
        """Empty credentials dict should round-trip correctly."""
        store = FernetCredentialStore(session=MagicMock(), fernet_key=fernet_key)
        original: dict[str, str] = {}
        encrypted = store._encrypt(original)
        decrypted = store._decrypt(encrypted)
        assert decrypted == original


class TestFernetCredentialStorePath:
    """Tests for credential path generation."""

    def test_credential_path_for_datasource(self, store):
        """credential_path_for() should return a consistent path string."""
        path = FernetCredentialStore.credential_path_for("ds-123")
        assert path == "datasource/ds-123/credentials"

    def test_credential_path_includes_datasource_id(self, store):
        """credential_path_for() should include the data source ID."""
        ds_id = "01ABCD12345"
        path = FernetCredentialStore.credential_path_for(ds_id)
        assert ds_id in path


class TestFernetCredentialStoreStore:
    """Tests for store() method."""

    @pytest.mark.asyncio
    async def test_store_upserts_credential_model(self, store, mock_session):
        """store() should upsert a CredentialModel with encrypted data."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute = AsyncMock(return_value=mock_result)

        await store.store(
            path="datasource/ds-1/credentials",
            tenant_id="tenant-1",
            credentials={"token": "ghp_abc"},
        )

        # Session.add should have been called (insert new)
        mock_session.add.assert_called_once()
        added_model = mock_session.add.call_args[0][0]
        assert added_model.path == "datasource/ds-1/credentials"
        assert added_model.tenant_id == "tenant-1"
        assert isinstance(added_model.encrypted_data, bytes)

    @pytest.mark.asyncio
    async def test_store_updates_existing_credential(self, store, mock_session):
        """store() should update encrypted_data when a model already exists."""
        from management.infrastructure.models.credential import CredentialModel

        existing_model = MagicMock(spec=CredentialModel)
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = existing_model
        mock_session.execute = AsyncMock(return_value=mock_result)

        await store.store(
            path="datasource/ds-1/credentials",
            tenant_id="tenant-1",
            credentials={"token": "new_token"},
        )

        # Should update encrypted_data on existing model (not add new)
        mock_session.add.assert_not_called()
        assert existing_model.encrypted_data is not None

    @pytest.mark.asyncio
    async def test_store_raises_on_empty_path(self, store):
        """store() should raise ValueError for empty path."""
        with pytest.raises(ValueError, match="path"):
            await store.store(path="", tenant_id="tenant-1", credentials={"token": "x"})

    @pytest.mark.asyncio
    async def test_store_raises_on_empty_tenant_id(self, store):
        """store() should raise ValueError for empty tenant_id."""
        with pytest.raises(ValueError, match="tenant_id"):
            await store.store(
                path="datasource/ds-1/credentials",
                tenant_id="",
                credentials={"token": "x"},
            )


class TestFernetCredentialStoreRetrieve:
    """Tests for retrieve() method."""

    @pytest.mark.asyncio
    async def test_retrieve_returns_decrypted_credentials(
        self, store, mock_session, fernet_key
    ):
        """retrieve() should return decrypted credentials from DB."""
        from management.infrastructure.models.credential import CredentialModel

        original_creds = {"token": "ghp_secret", "username": "user"}
        encrypted = store._encrypt(original_creds)

        existing_model = MagicMock(spec=CredentialModel)
        existing_model.encrypted_data = encrypted

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = existing_model
        mock_session.execute = AsyncMock(return_value=mock_result)

        result = await store.retrieve(
            path="datasource/ds-1/credentials", tenant_id="tenant-1"
        )
        assert result == original_creds

    @pytest.mark.asyncio
    async def test_retrieve_raises_keyerror_when_not_found(self, store, mock_session):
        """retrieve() should raise KeyError when credentials do not exist."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute = AsyncMock(return_value=mock_result)

        with pytest.raises(KeyError, match="datasource/missing"):
            await store.retrieve(
                path="datasource/missing/credentials", tenant_id="tenant-1"
            )

    @pytest.mark.asyncio
    async def test_retrieve_raises_on_empty_path(self, store):
        """retrieve() should raise ValueError for empty path."""
        with pytest.raises(ValueError, match="path"):
            await store.retrieve(path="", tenant_id="tenant-1")

    @pytest.mark.asyncio
    async def test_retrieve_raises_on_empty_tenant_id(self, store):
        """retrieve() should raise ValueError for empty tenant_id."""
        with pytest.raises(ValueError, match="tenant_id"):
            await store.retrieve(path="datasource/ds-1/credentials", tenant_id="")


class TestFernetCredentialStoreDelete:
    """Tests for delete() method."""

    @pytest.mark.asyncio
    async def test_delete_returns_true_when_found(self, store, mock_session):
        """delete() should return True when the credential existed."""
        from management.infrastructure.models.credential import CredentialModel

        existing_model = MagicMock(spec=CredentialModel)
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = existing_model
        mock_session.execute = AsyncMock(return_value=mock_result)

        result = await store.delete(
            path="datasource/ds-1/credentials", tenant_id="tenant-1"
        )
        assert result is True
        mock_session.delete.assert_called_once_with(existing_model)

    @pytest.mark.asyncio
    async def test_delete_returns_false_when_not_found(self, store, mock_session):
        """delete() should return False when credential does not exist."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute = AsyncMock(return_value=mock_result)

        result = await store.delete(
            path="datasource/missing/credentials", tenant_id="tenant-1"
        )
        assert result is False
        mock_session.delete.assert_not_called()

    @pytest.mark.asyncio
    async def test_delete_raises_on_empty_path(self, store):
        """delete() should raise ValueError for empty path."""
        with pytest.raises(ValueError, match="path"):
            await store.delete(path="", tenant_id="tenant-1")
