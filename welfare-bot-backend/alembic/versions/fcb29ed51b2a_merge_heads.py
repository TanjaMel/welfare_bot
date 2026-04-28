"""merge heads

Revision ID: fcb29ed51b2a
Revises: a1b2c3d4e5f6, b4f4e669ff45
Create Date: 2026-04-28

"""
from alembic import op
import sqlalchemy as sa

revision = 'fcb29ed51b2a'
down_revision = ('a1b2c3d4e5f6', 'b4f4e669ff45')
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass