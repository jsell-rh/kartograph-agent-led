"""SQLAlchemy ORM model for the data_sources table.

Stores data source configuration in PostgreSQL. Data sources define
connections to external data systems (e.g., GitHub) and belong to
exactly one knowledge graph.
"""

from sqlalchemy import ForeignKey, Index, JSON, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from infrastructure.database.models import Base, TimestampMixin


class DataSourceModel(Base, TimestampMixin):
    """ORM model for data_sources table.

    Stores data source configuration in PostgreSQL. SpiceDB manages
    the knowledge_graph and tenant authorization relationships via the
    transactional outbox pattern.

    The connection_config field stores adapter-specific configuration
    as JSON (e.g., repository URL, branch for GitHub adapter).

    Foreign Key Constraints:
    - knowledge_graph_id references knowledge_graphs.id with RESTRICT delete
    - tenant_id references tenants.id with RESTRICT delete
    """

    __tablename__ = "data_sources"

    id: Mapped[str] = mapped_column(String(26), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(
        String(26),
        ForeignKey("tenants.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    knowledge_graph_id: Mapped[str] = mapped_column(
        String(26),
        ForeignKey("knowledge_graphs.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    adapter_type: Mapped[str] = mapped_column(String(50), nullable=False)
    connection_config: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    credentials_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    schedule_type: Mapped[str] = mapped_column(
        String(20), nullable=False, default="manual"
    )
    schedule_value: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Relationships
    knowledge_graph = relationship("KnowledgeGraphModel", back_populates="data_sources")

    __table_args__ = (
        Index("idx_data_sources_name_kg", "name", "knowledge_graph_id"),
        Index("idx_data_sources_tenant", "tenant_id"),
    )

    def __repr__(self) -> str:
        """Return string representation."""
        return (
            f"<DataSourceModel(id={self.id}, name={self.name}, "
            f"knowledge_graph_id={self.knowledge_graph_id}, "
            f"adapter_type={self.adapter_type})>"
        )
