"""Add users table and user_id to all entity tables

Revision ID: 004_users
Revises: 003_group_id
Create Date: 2026-04-19
"""
import sqlalchemy as sa
from alembic import op

revision = "004_users"
down_revision = "003_group_id"
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("username", sa.String(50), unique=True, nullable=False, index=True),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("display_name", sa.String(100), nullable=False, server_default=""),
        sa.Column("preferred_currency", sa.String(10), nullable=False, server_default="INR"),
        sa.Column("monthly_income", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("is_first_login", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    
    for table in ["expenses", "budgets", "categories", "credit_cards", "loans", "user_settings", "conversations", "voice_interactions", "agent_activities"]:
        op.add_column(table, sa.Column("user_id", sa.String(36), nullable=True))
        op.create_index(f"ix_{table}_user_id", table, ["user_id"])

def downgrade() -> None:
    for table in ["expenses", "budgets", "categories", "credit_cards", "loans", "user_settings", "conversations", "voice_interactions", "agent_activities"]:
        op.drop_index(f"ix_{table}_user_id", table_name=table)
        op.drop_column(table, "user_id")
    op.drop_table("users")
