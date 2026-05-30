# alembic/versions/0001_initial.py
"""initial auth+rbac schema

Revision ID: 0001
Revises:
Create Date: 2026-05-30
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("email", sa.String(255), nullable=False, unique=True),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        "roles",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("name", sa.String(64), nullable=False, unique=True),
    )

    op.create_table(
        "user_roles",
        sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("role_id", sa.Integer, sa.ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True),
    )

    op.create_table(
        "data_sources",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("key", sa.String(64), nullable=False, unique=True),
        sa.Column("type", sa.String(16), nullable=False),
        sa.Column("config", postgresql.JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.CheckConstraint("type IN ('mcp', 'sql')", name="ck_data_sources_type"),
    )

    op.create_table(
        "role_sources",
        sa.Column("role_id", sa.Integer, sa.ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("source_id", sa.Integer, sa.ForeignKey("data_sources.id", ondelete="CASCADE"), primary_key=True),
    )

    op.create_table(
        "report_perms",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("report_id", sa.Integer, nullable=False),
        sa.Column("role_id", sa.Integer, sa.ForeignKey("roles.id", ondelete="CASCADE"), nullable=False),
        sa.Column("access", sa.String(8), nullable=False),
        sa.UniqueConstraint("report_id", "role_id", name="uq_report_perms_report_role"),
        sa.CheckConstraint("access IN ('view', 'edit')", name="ck_report_perms_access"),
    )
    op.create_index("ix_report_perms_report_id", "report_perms", ["report_id"])
    op.create_index("ix_report_perms_role_id", "report_perms", ["role_id"])


def downgrade() -> None:
    # индексы и constraints удаляются вместе со своими таблицами
    op.drop_table("report_perms")
    op.drop_table("role_sources")
    op.drop_table("data_sources")
    op.drop_table("user_roles")
    op.drop_table("roles")
    op.drop_table("users")
