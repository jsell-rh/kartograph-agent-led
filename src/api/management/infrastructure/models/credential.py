"""SQLAlchemy ORM model for the management_credentials table.

Stores Fernet-encrypted credentials for data sources. Credentials are
scoped by (path, tenant_id) for multi-tenant isolation. The encrypted_data
column stores the Fernet ciphertext as raw bytes — keys are never stored here.

The path convention is: ``datasource/{data_source_id}/credentials``
"""

from sqlalchemy import Index, LargeBinary, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from infrastructure.database.models import Base, TimestampMixin


class CredentialModel(Base, TimestampMixin):
    """ORM model for management_credentials table.

    Stores Fernet-encrypted credentials keyed by (path, tenant_id).
    The path encodes the resource type and ID; tenant_id provides
    multi-tenant isolation (defense-in-depth: even if a path is guessed,
    credentials are only returned for the matching tenant).
    """

    __tablename__ = "management_credentials"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    path: Mapped[str] = mapped_column(String(500), nullable=False)
    tenant_id: Mapped[str] = mapped_column(String(26), nullable=False, index=True)
    encrypted_data: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)

    __table_args__ = (
        UniqueConstraint(
            "path", "tenant_id", name="uq_management_credentials_path_tenant"
        ),
        Index("idx_management_credentials_path_tenant", "path", "tenant_id"),
    )

    def __repr__(self) -> str:
        """Return string representation (never exposes encrypted_data)."""
        return f"<CredentialModel(path={self.path!r}, tenant_id={self.tenant_id!r})>"
