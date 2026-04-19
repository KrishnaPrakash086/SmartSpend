# Budget CRUD and recalculation service — keeps spent_amount in sync with expense records
from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Budget, Expense


async def list_budgets(session: AsyncSession) -> list[Budget]:
    result = await session.execute(select(Budget))
    return list(result.scalars().all())


async def update_budget_limit(
    session: AsyncSession, budget_id: str, new_limit: float
) -> Budget:
    result = await session.execute(
        select(Budget).where(Budget.id == budget_id)
    )
    budget = result.scalar_one_or_none()
    if not budget:
        raise HTTPException(status_code=404, detail="Budget not found")

    budget.limit_amount = new_limit
    await session.flush()
    await session.refresh(budget)
    return budget


async def recalculate_spent_amounts(session: AsyncSession) -> None:
    budgets_result = await session.execute(select(Budget))
    budgets = budgets_result.scalars().all()

    for budget in budgets:
        total_result = await session.execute(
            select(func.coalesce(func.sum(Expense.amount), 0)).where(
                Expense.category == budget.category,
                Expense.date >= budget.period_start,
                Expense.date <= budget.period_end,
            )
        )
        budget.spent_amount = float(total_result.scalar())

    await session.flush()
