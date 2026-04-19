"""Drop global unique constraints on budgets.category and categories.name,
replace with per-user composite uniqueness.

Revision ID: 005_per_user_unique
Revises: 004_users
Create Date: 2026-04-19
"""
from typing import Sequence, Union

from alembic import op
from sqlalchemy import text

revision: str = "005_per_user_unique"
down_revision: Union[str, None] = "004_users"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _drop_constraint_if_exists(constraint_name: str, table_name: str) -> None:
    op.execute(text(
        f"ALTER TABLE {table_name} DROP CONSTRAINT IF EXISTS {constraint_name}"
    ))


def upgrade() -> None:
    _drop_constraint_if_exists("budgets_category_key", "budgets")
    _drop_constraint_if_exists("categories_name_key", "categories")

    op.execute(text(
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_budgets_user_category "
        "ON budgets (user_id, category)"
    ))
    op.execute(text(
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_categories_user_name "
        "ON categories (user_id, name)"
    ))


def downgrade() -> None:
    op.execute(text("DROP INDEX IF EXISTS uq_categories_user_name"))
    op.execute(text("DROP INDEX IF EXISTS uq_budgets_user_category"))
