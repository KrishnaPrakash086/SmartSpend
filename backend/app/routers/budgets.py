from fastapi import APIRouter

from app.dependencies import DatabaseSession
from app.models import Budget
from app.schemas import BudgetResponse, BudgetUpdate
from app.services import budget_service

router = APIRouter(prefix="/budgets", tags=["Budgets"])


def _serialize_budget(budget: Budget) -> BudgetResponse:
    return BudgetResponse(
        id=budget.id,
        category=budget.category,
        limit_amount=float(budget.limit_amount),
        spent_amount=float(budget.spent_amount),
        period_start=budget.period_start.isoformat(),
        period_end=budget.period_end.isoformat(),
    )


@router.get("/", response_model=list[BudgetResponse])
async def list_budgets(session: DatabaseSession):
    budget_records = await budget_service.list_budgets(session)
    return [_serialize_budget(budget) for budget in budget_records]


@router.patch("/{budget_id}", response_model=BudgetResponse)
async def update_budget(
    budget_id: str, data: BudgetUpdate, session: DatabaseSession
):
    budget = await budget_service.update_budget_limit(
        session, budget_id, data.limit_amount
    )
    return _serialize_budget(budget)
