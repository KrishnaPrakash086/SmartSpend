# Report data aggregation service — monthly summaries, category breakdowns, and spending trends
from collections import defaultdict
from datetime import date

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Category, Expense, UserSettings
from app.schemas import CategoryBreakdown, MonthlySummary


# Rolling 6-month window anchored to the 1st of the target month for consistent trend charts
def _compute_six_months_start() -> date:
    today = date.today()
    target_month = today.month - 5
    target_year = today.year
    if target_month <= 0:
        target_month += 12
        target_year -= 1
    return date(target_year, target_month, 1)


async def generate_report_data(
    session: AsyncSession, settings_row: UserSettings | None
) -> dict:
    monthly_income = float(settings_row.monthly_income) if settings_row else 0
    six_months_start = _compute_six_months_start()

    # PostgreSQL-specific to_char used for month formatting; not portable to SQLite
    month_key_expression = func.to_char(Expense.date, "YYYY-MM")
    month_label_expression = func.to_char(Expense.date, "Mon")

    monthly_query = (
        select(
            month_key_expression.label("month_key"),
            month_label_expression.label("month_label"),
            func.coalesce(func.sum(Expense.amount), 0).label("total_amount"),
        )
        .where(Expense.date >= six_months_start)
        .group_by(month_key_expression, month_label_expression)
        .order_by(month_key_expression)
    )
    monthly_result = await session.execute(monthly_query)
    monthly_rows = monthly_result.all()

    monthly_summaries = []
    for row in monthly_rows:
        expenses_total = float(row.total_amount)
        monthly_summaries.append(
            MonthlySummary(
                month=row.month_label.strip(),
                income=monthly_income,
                expenses=round(expenses_total, 2),
                savings=round(monthly_income - expenses_total, 2),
            )
        )

    trends_query = (
        select(
            month_key_expression.label("month_key"),
            month_label_expression.label("month_label"),
            Expense.category,
            func.coalesce(func.sum(Expense.amount), 0).label("total_amount"),
        )
        .where(Expense.date >= six_months_start)
        .group_by(month_key_expression, month_label_expression, Expense.category)
        .order_by(month_key_expression)
    )
    trends_result = await session.execute(trends_query)
    trends_rows = trends_result.all()

    ordered_months: list[str] = []
    trends_by_month: dict[str, dict[str, float]] = defaultdict(dict)
    for row in trends_rows:
        month_label = row.month_label.strip()
        if month_label not in ordered_months:
            ordered_months.append(month_label)
        trends_by_month[month_label][row.category] = round(float(row.total_amount), 2)

    trends = [
        {"month": month, **trends_by_month[month]} for month in ordered_months
    ]

    current_month_start = date.today().replace(day=1)
    categories_query = (
        select(
            Expense.category,
            func.coalesce(func.sum(Expense.amount), 0).label("total_amount"),
        )
        .where(Expense.date >= current_month_start)
        .group_by(Expense.category)
    )
    categories_result = await session.execute(categories_query)
    categories_rows = categories_result.all()

    color_result = await session.execute(select(Category.name, Category.color))
    color_map = {row.name: row.color for row in color_result.all()}

    category_breakdowns = [
        CategoryBreakdown(
            name=row.category,
            value=round(float(row.total_amount), 2),
            color=color_map.get(row.category, "#64748b"),
        )
        for row in categories_rows
    ]

    return {
        "monthly": monthly_summaries,
        "trends": trends,
        "categories": category_breakdowns,
    }
