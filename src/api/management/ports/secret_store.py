"""Secret store port for the Management bounded context.

Defines ISecretStoreRepository — the full read/write port for storing,
retrieving, and deleting encrypted credentials. Implementations live in
the Management infrastructure layer (e.g. FernetCredentialStore).

The read-only subset (retrieve only) is exposed as ICredentialReader in
shared_kernel/credential_reader.py for cross-context consumption by the
Ingestion context without creating a hard dependency on Management internals.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable


def credential_path_for(data_source_id: str) -> str:
    """Return the canonical credential path for a DataSource.

    Centralised here (in the port layer) so both the application layer and
    infrastructure implementations agree on path structure without creating
    an upward dependency.

    Args:
        data_source_id: The DataSource ID (ULID string).

    Returns:
        Path string: ``datasource/{data_source_id}/credentials``
    """
    return f"datasource/{data_source_id}/credentials"


@runtime_checkable
class ISecretStoreRepository(Protocol):
    """Full read/write port for encrypted credential storage.

    Implementations encrypt credentials at rest and scope them by
    (path, tenant_id) for multi-tenant isolation. The path convention
    is: ``datasource/{data_source_id}/credentials``.

    Both store() and retrieve() operate on a dict[str, str] — the
    schema is adapter-specific (e.g. GitHub uses {"token": "ghp_..."}).
    """

    async def store(
        self, path: str, tenant_id: str, credentials: dict[str, str]
    ) -> None:
        """Encrypt and persist credentials at the given path for the tenant.

        Creates a new entry if the path/tenant combination does not exist,
        or updates the encrypted data if it does (upsert semantics).

        Args:
            path: The credential path (e.g. "datasource/{id}/credentials").
            tenant_id: The tenant ID for multi-tenant isolation.
            credentials: Key-value pairs to encrypt and store.

        Raises:
            ValueError: If path or tenant_id is empty or whitespace-only.
        """
        ...

    async def retrieve(self, path: str, tenant_id: str) -> dict[str, str]:
        """Decrypt and return credentials stored at the given path for the tenant.

        Args:
            path: The credential path (e.g. "datasource/{id}/credentials").
            tenant_id: The tenant ID for multi-tenant isolation.

        Returns:
            A dict of decrypted credential key-value pairs.

        Raises:
            ValueError: If path or tenant_id is empty or whitespace-only.
            KeyError: If no credentials exist at the given path for the tenant.
        """
        ...

    async def delete(self, path: str, tenant_id: str) -> bool:
        """Delete credentials stored at the given path for the tenant.

        Args:
            path: The credential path (e.g. "datasource/{id}/credentials").
            tenant_id: The tenant ID for multi-tenant isolation.

        Returns:
            True if credentials were found and deleted, False if not found.

        Raises:
            ValueError: If path or tenant_id is empty or whitespace-only.
        """
        ...
