"""Add conversations table for saved chat history

Revision ID: 002_conversations
Revises: 001_initial
Create Date: 2026-04-16
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "002_conversations"
down_revision = "001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "conversations",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("mode", sa.String(length=20), nullable=False, index=True),
        sa.Column("title", sa.String(length=255), nullable=False, server_default="Untitled"),
        sa.Column("messages", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default="[]"),
        sa.Column("message_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    # Indexes auto-created by mapped_column(index=True) on the model — using idempotent CREATE
    op.execute("CREATE INDEX IF NOT EXISTS ix_conversations_mode ON conversations (mode)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_conversations_created_at ON conversations (created_at)")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_conversations_created_at")
    op.execute("DROP INDEX IF EXISTS ix_conversations_mode")
    op.drop_table("conversations")
