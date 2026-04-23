"""repair users memory columns

Revision ID: REPLACE_WITH_YOUR_NEW_REVISION_ID
Revises: d348e4711fa6
Create Date: 2026-04-14

"""
from __future__ import annotations

from alembic import op


revision = "b4f4e669ff45"
down_revision = "d348e4711fa6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        ALTER TABLE users
        ADD COLUMN IF NOT EXISTS memory_summary TEXT
    """)

    op.execute("""
        ALTER TABLE users
        ADD COLUMN IF NOT EXISTS memory_summary_updated_at TIMESTAMP
    """)

    op.execute("""
        ALTER TABLE users
        ADD COLUMN IF NOT EXISTS memory_summary_message_count INTEGER NOT NULL DEFAULT 0
    """)


def downgrade() -> None:
    op.execute("""
        ALTER TABLE users
        DROP COLUMN IF EXISTS memory_summary_message_count
    """)

    op.execute("""
        ALTER TABLE users
        DROP COLUMN IF EXISTS memory_summary_updated_at
    """)

    op.execute("""
        ALTER TABLE users
        DROP COLUMN IF EXISTS memory_summary
    """)