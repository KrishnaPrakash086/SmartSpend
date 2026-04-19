"""Initial schema — all tables

Revision ID: 001_initial
Revises:
Create Date: 2026-04-16

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "001_initial"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "categories",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("name", sa.String(100), nullable=False, unique=True),
        sa.Column("color", sa.String(20), nullable=False, server_default="#64748b"),
        sa.Column("icon", sa.String(50), nullable=False, server_default="MoreHorizontal"),
    )

    op.create_table(
        "expenses",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("description", sa.String(500), nullable=False),
        sa.Column("amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("category", sa.String(100), nullable=False, index=True),
        sa.Column("date", sa.Date, nullable=False, index=True),
        sa.Column("payment_method", sa.String(50), nullable=False),
        sa.Column("added_via", sa.String(20), nullable=False, server_default="manual"),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            index=True,
        ),
    )

    op.create_table(
        "budgets",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("category", sa.String(100), nullable=False, unique=True),
        sa.Column("limit_amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("spent_amount", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("period_start", sa.Date, nullable=False),
        sa.Column("period_end", sa.Date, nullable=False),
    )

    op.create_table(
        "credit_cards",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("bank_name", sa.String(100), nullable=False),
        sa.Column("card_name", sa.String(100), nullable=False),
        sa.Column("card_type", sa.String(20), nullable=False),
        sa.Column("credit_limit", sa.Numeric(12, 2), nullable=False),
        sa.Column("used_amount", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("billing_date", sa.Integer, nullable=False),
        sa.Column("due_date", sa.Integer, nullable=False),
        sa.Column("apr", sa.Numeric(5, 2), nullable=False),
        sa.Column("rewards_rate", sa.Numeric(5, 2), nullable=False, server_default="0"),
        sa.Column("min_payment", sa.Numeric(12, 2), nullable=False, server_default="0"),
    )

    op.create_table(
        "loans",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("loan_type", sa.String(50), nullable=False),
        sa.Column("bank_name", sa.String(100), nullable=False),
        sa.Column("principal_amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("remaining_amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("emi", sa.Numeric(12, 2), nullable=False),
        sa.Column("interest_rate", sa.Numeric(5, 2), nullable=False),
        sa.Column("tenure_months", sa.Integer, nullable=False),
        sa.Column("remaining_months", sa.Integer, nullable=False),
        sa.Column("start_date", sa.String(10), nullable=False),
        sa.Column("payment_method", sa.String(30), nullable=False),
    )

    op.create_table(
        "user_settings",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("currency", sa.String(10), nullable=False, server_default="USD"),
        sa.Column("monthly_income", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("budget_cycle_start", sa.Integer, nullable=False, server_default="1"),
        sa.Column("notify_budget_exceeded", sa.Boolean, server_default=sa.text("true")),
        sa.Column("notify_weekly_summary", sa.Boolean, server_default=sa.text("true")),
        sa.Column("notify_voice_confirmations", sa.Boolean, server_default=sa.text("true")),
        sa.Column("notify_ai_insights", sa.Boolean, server_default=sa.text("false")),
        sa.Column("voice_enabled", sa.Boolean, server_default=sa.text("true")),
        sa.Column("language", sa.String(20), nullable=False, server_default="English"),
    )

    op.create_table(
        "voice_interactions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("transcript", sa.Text, nullable=False),
        sa.Column("parsed_result", postgresql.JSONB, nullable=False, server_default="{}"),
        sa.Column("status", sa.String(20), nullable=False, server_default="processing"),
        sa.Column("result_description", sa.String(500), nullable=False, server_default=""),
        sa.Column("expense_id", sa.String(36), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            index=True,
        ),
    )

    op.create_table(
        "agent_activities",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("agent_name", sa.String(100), nullable=False, index=True),
        sa.Column("agent_type", sa.String(50), nullable=False, index=True),
        sa.Column("action", sa.Text, nullable=False),
        sa.Column("details", postgresql.JSONB, nullable=False, server_default="{}"),
        sa.Column("duration_ms", sa.Integer, nullable=False, server_default="0"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            index=True,
        ),
    )

    op.create_table(
        "webhook_events",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("event_type", sa.String(100), nullable=False, index=True),
        sa.Column("payload", postgresql.JSONB, nullable=False, server_default="{}"),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            index=True,
        ),
    )


def downgrade() -> None:
    op.drop_table("webhook_events")
    op.drop_table("agent_activities")
    op.drop_table("voice_interactions")
    op.drop_table("user_settings")
    op.drop_table("loans")
    op.drop_table("credit_cards")
    op.drop_table("budgets")
    op.drop_table("expenses")
    op.drop_table("categories")
