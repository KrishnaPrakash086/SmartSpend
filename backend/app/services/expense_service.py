from datetime import date as date_type

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Budget, Expense
from app.schemas import ExpenseCreate


def _parse_date_safe(date_string: str) -> date_type | None:
    try:
        return date_type.fromisoformat(date_string)
    except (ValueError, TypeError):
        return None


async def list_expenses(
    session: AsyncSession,
    user_id: str,
    search: str | None = None,
    category: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    page: int = 1,
    per_page: int = 50,
) -> list[Expense]:
    query = select(Expense).where(Expense.user_id == user_id)

    if search:
        query = query.where(Expense.description.ilike(f"%{search}%"))

    if category and category != "All":
        query = query.where(Expense.category == category)

    if date_from:
        parsed = _parse_date_safe(date_from)
        if parsed:
            query = query.where(Expense.date >= parsed)

    if date_to:
        parsed = _parse_date_safe(date_to)
        if parsed:
            query = query.where(Expense.date <= parsed)

    query = query.order_by(Expense.date.desc(), Expense.created_at.desc())
    offset = (page - 1) * per_page
    query = query.offset(offset).limit(per_page)

    result = await session.execute(query)
    return list(result.scalars().all())


async def create_expense(session: AsyncSession, data: ExpenseCreate, user_id: str) -> Expense:
    parsed_date = _parse_date_safe(data.date)
    if not parsed_date:
        raise HTTPException(status_code=422, detail=f"Invalid date format: '{data.date}'. Expected YYYY-MM-DD.")

    expense = Expense(
        description=data.description,
        amount=data.amount,
        category=data.category,
        date=parsed_date,
        payment_method=data.payment_method,
        added_via=data.added_via,
        notes=data.notes,
        group_id=getattr(data, "group_id", None),
        group_description=getattr(data, "group_description", None),
        user_id=user_id,
    )
    session.add(expense)
    await session.flush()

    budget_result = await session.execute(
        select(Budget).where(Budget.category == data.category, Budget.user_id == user_id)
    )
    budget = budget_result.scalar_one_or_none()
    if budget:
        budget.spent_amount = float(budget.spent_amount) + data.amount
        await session.flush()

    await session.refresh(expense)
    return expense


async def delete_expense(session: AsyncSession, expense_id: str, user_id: str) -> bool:
    expense = await get_expense_by_id(session, expense_id)
    if not expense:
        return False
    if expense.user_id and expense.user_id != user_id:
        return False

    budget_result = await session.execute(
        select(Budget).where(Budget.category == expense.category, Budget.user_id == user_id)
    )
    budget = budget_result.scalar_one_or_none()
    if budget:
        budget.spent_amount = max(0, float(budget.spent_amount) - float(expense.amount))

    await session.delete(expense)
    await session.flush()
    return True


async def get_expense_by_id(
    session: AsyncSession, expense_id: str
) -> Expense | None:
    result = await session.execute(
        select(Expense).where(Expense.id == expense_id)
    )
    return result.scalar_one_or_none()
