"""add memory summary fields to users
Revision ID: d348e4711fa6
Revises: 20260413_risk_events
Create Date: 2026-04-13
"""
from __future__ import annotations
from alembic import op
import sqlalchemy as sa

revision = "d348e4711fa6"
down_revision = "20260413_risk_events"
branch_labels = None
depends_on = None


def _column_exists(table_name: str, column_name: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = [c["name"] for c in inspector.get_columns(table_name)]
    return column_name in columns


def upgrade() -> None:
    if not _column_exists("users", "memory_summary"):
        op.add_column("users", sa.Column("memory_summary", sa.Text(), nullable=True))
    if not _column_exists("users", "memory_summary_updated_at"):
        op.add_column("users", sa.Column("memory_summary_updated_at", sa.DateTime(), nullable=True))
    if not _column_exists("users", "memory_summary_message_count"):
        op.add_column(
            "users",
            sa.Column(
                "memory_summary_message_count",
                sa.Integer(),
                nullable=False,
                server_default="0",
            ),
        )


def downgrade() -> None:
    if _column_exists("users", "memory_summary_message_count"):
        op.drop_column("users", "memory_summary_message_count")
    if _column_exists("users", "memory_summary_updated_at"):
        op.drop_column("users", "memory_summary_updated_at")
    if _column_exists("users", "memory_summary"):
        op.drop_column("users", "memory_summary")
