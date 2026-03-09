"""Fernet-encrypted credential store for the Management bounded context.

Implements both ISecretStoreRepository (full read/write port) and
ICredentialReader (shared kernel read-only port). Credentials are
encrypted at rest using Fernet symmetric encryption (AES-128-CBC with
HMAC-SHA256 authentication) via the ``cryptography`` library.

Encryption key is provided at construction time from
ManagementSettings.fernet_key (env: KARTOGRAPH_MANAGEMENT_FERNET_KEY).
Keys must be URL-safe base64-encoded 32-byte values (use
``Fernet.generate_key()`` to create a key).
"""

from __future__ import annotations

import json

from cryptography.fernet import Fernet
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from management.infrastructure.models.credential import CredentialModel
from management.ports.secret_store import ISecretStoreRepository
from shared_kernel.credential_reader import ICredentialReader


class FernetCredentialStore(ISecretStoreRepository, ICredentialReader):
    """Fernet-encrypted PostgreSQL credential store.

    Credentials are stored as Fernet ciphertext in the
    ``management_credentials`` table, scoped by (path, tenant_id).

    Path convention: ``datasource/{data_source_id}/credentials``
    Use the class method :meth:`credential_path_for` to generate
    consistent paths.

    This class satisfies both ISecretStoreRepository (management internal)
    and ICredentialReader (shared kernel, consumed by Ingestion context).
    """

    def __init__(self, session: AsyncSession, fernet_key: str) -> None:
        """Initialize FernetCredentialStore.

        Args:
            session: AsyncSQLAlchemy session for database operations.
            fernet_key: URL-safe base64-encoded 32-byte Fernet key.
                        Generate with: ``Fernet.generate_key().decode()``.

        Raises:
            ValueError: If fernet_key is not a valid Fernet key.
        """
        try:
            self._fernet = Fernet(
                fernet_key.encode() if isinstance(fernet_key, str) else fernet_key
            )
        except Exception as exc:
            raise ValueError(f"Invalid Fernet key: {exc}") from exc
        self._session = session

    # ------------------------------------------------------------------
    # Path helpers
    # ------------------------------------------------------------------

    @staticmethod
    def credential_path_for(data_source_id: str) -> str:
        """Return the canonical credential path for a DataSource.

        Delegates to the port-layer helper to keep path logic in one place.

        Args:
            data_source_id: The DataSource ID (ULID string).

        Returns:
            Path string: ``datasource/{data_source_id}/credentials``
        """
        from management.ports.secret_store import credential_path_for

        return credential_path_for(data_source_id)

    # ------------------------------------------------------------------
    # Internal encryption helpers
    # ------------------------------------------------------------------

    def _encrypt(self, credentials: dict[str, str]) -> bytes:
        """Serialize and Fernet-encrypt a credentials dict.

        Args:
            credentials: Key-value credential pairs to encrypt.

        Returns:
            Fernet ciphertext as bytes.
        """
        plaintext = json.dumps(credentials, separators=(",", ":")).encode()
        return self._fernet.encrypt(plaintext)

    def _decrypt(self, encrypted_data: bytes) -> dict[str, str]:
        """Fernet-decrypt and deserialize a credentials dict.

        Args:
            encrypted_data: Fernet ciphertext bytes from storage.

        Returns:
            Decrypted credential key-value pairs.

        Raises:
            cryptography.fernet.InvalidToken: If the key is wrong or
                the ciphertext has been tampered with.
        """
        plaintext = self._fernet.decrypt(encrypted_data)
        return json.loads(plaintext)

    # ------------------------------------------------------------------
    # Validation helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _validate_args(path: str, tenant_id: str) -> None:
        """Validate that path and tenant_id are non-empty.

        Args:
            path: Credential path.
            tenant_id: Tenant ID.

        Raises:
            ValueError: If path or tenant_id is empty or whitespace-only.
        """
        if not path or not path.strip():
            raise ValueError("path must not be empty or whitespace-only")
        if not tenant_id or not tenant_id.strip():
            raise ValueError("tenant_id must not be empty or whitespace-only")

    # ------------------------------------------------------------------
    # ISecretStoreRepository implementation
    # ------------------------------------------------------------------

    async def store(
        self, path: str, tenant_id: str, credentials: dict[str, str]
    ) -> None:
        """Encrypt and persist credentials at the given path for the tenant.

        Upsert semantics: creates a new row if (path, tenant_id) does not
        exist, otherwise updates the encrypted_data in-place.

        Args:
            path: Credential path (e.g. "datasource/{id}/credentials").
            tenant_id: Tenant ID for multi-tenant isolation.
            credentials: Key-value pairs to encrypt and store.

        Raises:
            ValueError: If path or tenant_id is empty.
        """
        self._validate_args(path, tenant_id)
        encrypted = self._encrypt(credentials)

        stmt = select(CredentialModel).where(
            CredentialModel.path == path,
            CredentialModel.tenant_id == tenant_id,
        )
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()

        if model is not None:
            model.encrypted_data = encrypted
        else:
            model = CredentialModel(
                path=path,
                tenant_id=tenant_id,
                encrypted_data=encrypted,
            )
            self._session.add(model)

    async def retrieve(self, path: str, tenant_id: str) -> dict[str, str]:
        """Decrypt and return credentials stored at the given path for the tenant.

        Args:
            path: Credential path (e.g. "datasource/{id}/credentials").
            tenant_id: Tenant ID for multi-tenant isolation.

        Returns:
            Decrypted credential key-value pairs.

        Raises:
            ValueError: If path or tenant_id is empty.
            KeyError: If no credentials exist at the given path for the tenant.
        """
        self._validate_args(path, tenant_id)

        stmt = select(CredentialModel).where(
            CredentialModel.path == path,
            CredentialModel.tenant_id == tenant_id,
        )
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()

        if model is None:
            raise KeyError(f"No credentials at {path!r} for tenant {tenant_id!r}")

        return self._decrypt(model.encrypted_data)

    async def delete(self, path: str, tenant_id: str) -> bool:
        """Delete credentials stored at the given path for the tenant.

        Args:
            path: Credential path (e.g. "datasource/{id}/credentials").
            tenant_id: Tenant ID for multi-tenant isolation.

        Returns:
            True if credentials were found and deleted, False if not found.

        Raises:
            ValueError: If path or tenant_id is empty.
        """
        self._validate_args(path, tenant_id)

        stmt = select(CredentialModel).where(
            CredentialModel.path == path,
            CredentialModel.tenant_id == tenant_id,
        )
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()

        if model is None:
            return False

        await self._session.delete(model)
        return True
