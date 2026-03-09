"""SQLAlchemy ORM model for the knowledge_graphs table.

Stores knowledge graph metadata in PostgreSQL. Knowledge graphs are
containers for interconnected data sourced from various data sources.
Each knowledge graph belongs to one workspace and one tenant.
"""

from sqlalchemy import ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from infrastructure.database.models import Base, TimestampMixin


class KnowledgeGraphModel(Base, TimestampMixin):
    """ORM model for knowledge_graphs table.

    Stores knowledge graph configuration in PostgreSQL. SpiceDB manages
    the workspace and tenant authorization relationships (written via
    the transactional outbox pattern when KnowledgeGraphCreated events
    are processed).

    Foreign Key Constraints:
    - workspace_id references workspaces.id with RESTRICT delete
      Application must delete knowledge graphs before workspace deletion
    - tenant_id references tenants.id with RESTRICT delete
    """

    __tablename__ = "knowledge_graphs"

    id: Mapped[str] = mapped_column(String(26), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(
        String(26),
        ForeignKey("tenants.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    workspace_id: Mapped[str] = mapped_column(
        String(26),
        ForeignKey("workspaces.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str] = mapped_column(String(1000), nullable=False, default="")

    # Relationships
    data_sources = relationship(
        "DataSourceModel",
        back_populates="knowledge_graph",
        passive_deletes=True,
    )

    __table_args__ = (
        Index("idx_knowledge_graphs_name_workspace", "name", "workspace_id"),
        Index("idx_knowledge_graphs_tenant", "tenant_id"),
    )

    def __repr__(self) -> str:
        """Return string representation."""
        return (
            f"<KnowledgeGraphModel(id={self.id}, name={self.name}, "
            f"workspace_id={self.workspace_id})>"
        )
