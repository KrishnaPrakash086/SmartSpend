# REST endpoints for expense listing, creation, and deletion
from typing import Optional

from fastapi import APIRouter, HTTPException, status

from app.dependencies import DatabaseSession
from app.models import Expense
from app.schemas import ExpenseCreate, ExpenseResponse, ExpenseUpdate
from app.services import expense_service

router = APIRouter(prefix="/expenses", tags=["Expenses"])


# Manual serialization needed because ORM Numeric/Date types require explicit float()/isoformat() conversion
def _serialize_expense(expense: Expense) -> ExpenseResponse:
    return ExpenseResponse(
        id=expense.id,
        description=expense.description,
        amount=float(expense.amount),
        category=expense.category,
        date=expense.date.isoformat(),
        payment_method=expense.payment_method,
        added_via=expense.added_via,
        notes=expense.notes,
        group_id=expense.group_id,
        group_description=expense.group_description,
        created_at=expense.created_at.isoformat(),
    )


@router.get("/", response_model=list[ExpenseResponse])
async def list_expenses(
    session: DatabaseSession,
    search: Optional[str] = None,
    category: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
):
    expense_records = await expense_service.list_expenses(
        session,
        search=search,
        category=category,
        date_from=date_from,
        date_to=date_to,
    )
    return [_serialize_expense(expense) for expense in expense_records]


@router.post(
    "/", response_model=ExpenseResponse, status_code=status.HTTP_201_CREATED
)
async def create_expense(data: ExpenseCreate, session: DatabaseSession):
    expense = await expense_service.create_expense(session, data)
    return _serialize_expense(expense)


@router.post("/split", status_code=status.HTTP_201_CREATED)
async def create_split_expense(body: dict, session: DatabaseSession):
    """Create multiple linked expenses from a split transaction.
    Body: { description, total_amount, date, payment_method, added_via, splits: [{category, amount}] }
    Validates that split amounts sum to total_amount.
    """
    import uuid as _uuid
    description = body.get("description", "")
    total_amount = body.get("total_amount", 0)
    date_str = body.get("date", "")
    payment_method = body.get("payment_method", "Cash")
    added_via = body.get("added_via", "manual")
    splits = body.get("splits", [])

    if not splits or len(splits) < 2:
        raise HTTPException(status_code=422, detail="At least 2 category splits required")

    split_total = sum(s.get("amount", 0) for s in splits)
    if abs(split_total - total_amount) > 0.01:
        raise HTTPException(
            status_code=422,
            detail=f"Split amounts ({split_total:.2f}) don't match total ({total_amount:.2f})"
        )

    group_id = str(_uuid.uuid4())
    created_expenses = []

    for split in splits:
        split_data = ExpenseCreate(
            description=f"{description} ({split.get('category', 'Other')})",
            amount=split["amount"],
            category=split["category"],
            date=date_str,
            payment_method=payment_method,
            added_via=added_via,
            group_id=group_id,
            group_description=description,
        )
        expense = await expense_service.create_expense(session, split_data)
        created_expenses.append(_serialize_expense(expense))

    return {"group_id": group_id, "expenses": created_expenses, "total": total_amount}


@router.patch("/{expense_id}", response_model=ExpenseResponse)
async def update_expense(
    expense_id: str, data: ExpenseUpdate, session: DatabaseSession
):
    from datetime import date as _date

    existing = await expense_service.get_expense_by_id(session, expense_id)
    if not existing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Expense not found"
        )

    old_amount = float(existing.amount)
    old_category = existing.category
    update_fields = data.model_dump(exclude_unset=True)

    if "date" in update_fields and update_fields["date"]:
        try:
            update_fields["date"] = _date.fromisoformat(update_fields["date"])
        except ValueError:
            raise HTTPException(status_code=422, detail="Invalid date format")

    for field, value in update_fields.items():
        setattr(existing, field, value)

    await session.flush()

    # If amount or category changed, adjust the affected budgets
    from sqlalchemy import select as _select
    from app.models import Budget

    if "amount" in update_fields or "category" in update_fields:
        # Subtract old amount from old category budget
        old_budget_result = await session.execute(
            _select(Budget).where(Budget.category == old_category)
        )
        old_budget = old_budget_result.scalar_one_or_none()
        if old_budget:
            old_budget.spent_amount = max(0, float(old_budget.spent_amount) - old_amount)

        # Add new amount to new category budget
        new_budget_result = await session.execute(
            _select(Budget).where(Budget.category == existing.category)
        )
        new_budget = new_budget_result.scalar_one_or_none()
        if new_budget:
            new_budget.spent_amount = float(new_budget.spent_amount) + float(existing.amount)

        await session.flush()

    await session.refresh(existing)
    return _serialize_expense(existing)


@router.delete("/{expense_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_expense(expense_id: str, session: DatabaseSession):
    deleted = await expense_service.delete_expense(session, expense_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Expense not found",
        )
