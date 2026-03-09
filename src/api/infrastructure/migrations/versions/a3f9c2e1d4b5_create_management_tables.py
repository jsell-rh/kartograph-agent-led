"""Create management context tables: knowledge_graphs, data_sources, management_credentials

Revision ID: a3f9c2e1d4b5
Revises: 0c6b5d01f040
Create Date: 2026-03-09 18:00:00.000000

Adds the three tables for the Management bounded context:
- knowledge_graphs: KnowledgeGraph aggregate persistence
- data_sources: DataSource aggregate persistence (FK to knowledge_graphs + tenants)
- management_credentials: Fernet-encrypted credential storage keyed by (path, tenant_id)

AIHCM-181 (KnowledgeGraph + DataSource persistence) and AIHCM-182 (Fernet credentials).
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a3f9c2e1d4b5"
down_revision: Union[str, None] = "0c6b5d01f040"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create knowledge_graphs, data_sources, and management_credentials tables."""
    # ------------------------------------------------------------------
    # knowledge_graphs
    # ------------------------------------------------------------------
    op.create_table(
        "knowledge_graphs",
        sa.Column("id", sa.String(26), primary_key=True),
        sa.Column(
            "tenant_id",
            sa.String(26),
            sa.ForeignKey(
                "tenants.id", ondelete="RESTRICT", name="fk_knowledge_graphs_tenant_id"
            ),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "workspace_id",
            sa.String(26),
            nullable=False,
            index=True,
        ),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "idx_knowledge_graphs_workspace_tenant",
        "knowledge_graphs",
        ["workspace_id", "tenant_id"],
    )
    op.create_index(
        "idx_knowledge_graphs_name_workspace",
        "knowledge_graphs",
        ["name", "workspace_id"],
    )

    # ------------------------------------------------------------------
    # data_sources
    # ------------------------------------------------------------------
    op.create_table(
        "data_sources",
        sa.Column("id", sa.String(26), primary_key=True),
        sa.Column(
            "tenant_id",
            sa.String(26),
            sa.ForeignKey(
                "tenants.id", ondelete="RESTRICT", name="fk_data_sources_tenant_id"
            ),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "knowledge_graph_id",
            sa.String(26),
            sa.ForeignKey(
                "knowledge_graphs.id",
                ondelete="RESTRICT",
                name="fk_data_sources_knowledge_graph_id",
            ),
            nullable=False,
            index=True,
        ),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("adapter_type", sa.String(50), nullable=False),
        sa.Column("connection_config", sa.JSON, nullable=False, server_default="{}"),
        sa.Column("credentials_path", sa.String(500), nullable=True),
        sa.Column(
            "schedule_type", sa.String(20), nullable=False, server_default="manual"
        ),
        sa.Column("schedule_value", sa.String(255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "idx_data_sources_name_kg",
        "data_sources",
        ["name", "knowledge_graph_id"],
    )
    op.create_index(
        "idx_data_sources_tenant",
        "data_sources",
        ["tenant_id"],
    )

    # ------------------------------------------------------------------
    # management_credentials (Fernet-encrypted at-rest)
    # ------------------------------------------------------------------
    op.create_table(
        "management_credentials",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("path", sa.String(500), nullable=False),
        sa.Column("tenant_id", sa.String(26), nullable=False, index=True),
        sa.Column("encrypted_data", sa.LargeBinary, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_unique_constraint(
        "uq_management_credentials_path_tenant",
        "management_credentials",
        ["path", "tenant_id"],
    )
    op.create_index(
        "idx_management_credentials_path_tenant",
        "management_credentials",
        ["path", "tenant_id"],
    )


def downgrade() -> None:
    """Drop management context tables in reverse dependency order."""
    # Credentials has no FKs — safe to drop first
    op.drop_index("idx_management_credentials_path_tenant", "management_credentials")
    op.drop_constraint(
        "uq_management_credentials_path_tenant",
        "management_credentials",
        type_="unique",
    )
    op.drop_table("management_credentials")

    # data_sources depends on knowledge_graphs
    op.drop_index("idx_data_sources_tenant", "data_sources")
    op.drop_index("idx_data_sources_name_kg", "data_sources")
    op.drop_table("data_sources")

    # knowledge_graphs depends on tenants
    op.drop_index("idx_knowledge_graphs_name_workspace", "knowledge_graphs")
    op.drop_index("idx_knowledge_graphs_workspace_tenant", "knowledge_graphs")
    op.drop_table("knowledge_graphs")
