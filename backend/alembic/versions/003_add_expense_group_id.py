"""Add group_id and group_description for split expenses

Revision ID: 003_group_id
Revises: 002_conversations
Create Date: 2026-04-17
"""
import sqlalchemy as sa
from alembic import op

revision = "003_group_id"
down_revision = "002_conversations"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("expenses", sa.Column("group_id", sa.String(36), nullable=True))
    op.add_column("expenses", sa.Column("group_description", sa.String(500), nullable=True))
    op.create_index("ix_expenses_group_id", "expenses", ["group_id"])


def downgrade() -> None:
    op.drop_index("ix_expenses_group_id", table_name="expenses")
    op.drop_column("expenses", "group_description")
    op.drop_column("expenses", "group_id")
