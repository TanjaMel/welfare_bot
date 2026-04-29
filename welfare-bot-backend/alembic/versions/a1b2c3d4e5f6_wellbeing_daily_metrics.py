"""create wellbeing_daily_metrics table

Revision ID: a1b2c3d4e5f6
Revises: 20260413_risk_events
Create Date: 2026-04-24
"""
from alembic import op
import sqlalchemy as sa

revision = "a1b2c3d4e5f6"
down_revision = "20260413_risk_events"
branch_labels = None
depends_on = None


def _table_exists(table_name: str) -> bool:
    import sqlalchemy as sa
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return table_name in inspector.get_table_names()


def upgrade() -> None:
    if _table_exists("wellbeing_daily_metrics"):
        return
    op.create_table(
        "wellbeing_daily_metrics",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("mood_score", sa.Float(), nullable=True),
        sa.Column("sleep_score", sa.Float(), nullable=True),
        sa.Column("food_score", sa.Float(), nullable=True),
        sa.Column("hydration_score", sa.Float(), nullable=True),
        sa.Column("medication_score", sa.Float(), nullable=True),
        sa.Column("social_activity_score", sa.Float(), nullable=True),
        sa.Column("risk_score", sa.Float(), nullable=True),
        sa.Column("overall_wellbeing_score", sa.Float(), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="stable"),
        sa.Column("soft_message", sa.Text(), nullable=True),
        sa.Column("data_completeness", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )

    op.create_index(
        "ix_wellbeing_user_date",
        "wellbeing_daily_metrics",
        ["user_id", "date"],
    )

    op.create_index(
        "uq_wellbeing_user_date",
        "wellbeing_daily_metrics",
        ["user_id", "date"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("uq_wellbeing_user_date")
    op.drop_index("ix_wellbeing_user_date")
    op.drop_table("wellbeing_daily_metrics")
