"""add risk events and message risk fields

Revision ID: 20260413_risk_events
Revises: fbb7ec1fe6e4
Create Date: 2026-04-13
"""

from alembic import op
import sqlalchemy as sa


revision = "20260413_risk_events"
down_revision = "fbb7ec1fe6e4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "conversation_messages",
        sa.Column("risk_level", sa.String(length=20), nullable=True),
    )
    op.add_column(
        "conversation_messages",
        sa.Column("risk_score", sa.Integer(), nullable=True),
    )
    op.add_column(
        "conversation_messages",
        sa.Column("risk_category", sa.String(length=50), nullable=True),
    )

    op.create_table(
        "risk_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("conversation_id", sa.Integer(), nullable=True),
        sa.Column("message_id", sa.Integer(), sa.ForeignKey("conversation_messages.id"), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("risk_level", sa.String(length=20), nullable=False),
        sa.Column("risk_score", sa.Integer(), nullable=False),
        sa.Column("risk_category", sa.String(length=50), nullable=False),
        sa.Column("signals_json", sa.JSON(), nullable=False),
        sa.Column("reasons_json", sa.JSON(), nullable=False),
        sa.Column("suggested_action", sa.Text(), nullable=False),
        sa.Column("should_alert_family", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )

    op.create_index("ix_risk_events_user_id", "risk_events", ["user_id"])
    op.create_index("ix_risk_events_message_id", "risk_events", ["message_id"])
    op.create_index("ix_risk_events_risk_level", "risk_events", ["risk_level"])
    op.create_index("ix_risk_events_risk_category", "risk_events", ["risk_category"])


def downgrade() -> None:
    op.drop_index("ix_risk_events_risk_category", table_name="risk_events")
    op.drop_index("ix_risk_events_risk_level", table_name="risk_events")
    op.drop_index("ix_risk_events_message_id", table_name="risk_events")
    op.drop_index("ix_risk_events_user_id", table_name="risk_events")
    op.drop_table("risk_events")

    op.drop_column("conversation_messages", "risk_category")
    op.drop_column("conversation_messages", "risk_score")
    op.drop_column("conversation_messages", "risk_level")