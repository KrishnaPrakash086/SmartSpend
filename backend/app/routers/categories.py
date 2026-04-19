from datetime import date, timedelta

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from app.dependencies import DatabaseSession, RequiredUserId
from app.models import Budget, Category
from app.schemas import CategoryCreate, CategoryResponse

router = APIRouter(prefix="/categories", tags=["Categories"])


@router.get("/", response_model=list[CategoryResponse])
async def list_categories(session: DatabaseSession, user_id: RequiredUserId):
    result = await session.execute(
        select(Category).where(Category.user_id == user_id)
    )
    return list(result.scalars().all())


@router.post(
    "/",
    response_model=CategoryResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_category(data: CategoryCreate, session: DatabaseSession, user_id: RequiredUserId):
    category = Category(
        name=data.name,
        color=data.color,
        icon=data.icon,
        user_id=user_id,
    )
    session.add(category)

    existing_budget = await session.execute(
        select(Budget).where(Budget.category == data.name, Budget.user_id == user_id)
    )
    if not existing_budget.scalar_one_or_none():
        today = date.today()
        period_start = today.replace(day=1)
        if today.month == 12:
            period_end = today.replace(year=today.year + 1, month=1, day=1) - timedelta(days=1)
        else:
            period_end = today.replace(month=today.month + 1, day=1) - timedelta(days=1)
        session.add(Budget(
            category=data.name,
            limit_amount=0,
            spent_amount=0,
            period_start=period_start,
            period_end=period_end,
            user_id=user_id,
        ))

    await session.flush()
    await session.refresh(category)
    return category


@router.patch("/{category_id}", response_model=CategoryResponse)
async def update_category(category_id: str, data: CategoryCreate, session: DatabaseSession, user_id: RequiredUserId):
    result = await session.execute(
        select(Category).where(Category.id == category_id, Category.user_id == user_id)
    )
    category = result.scalar_one_or_none()
    if not category:
        raise HTTPException(status_code=404, detail="Category not found")

    old_name = category.name
    category.name = data.name
    category.color = data.color
    category.icon = data.icon

    if old_name != data.name:
        budget_result = await session.execute(
            select(Budget).where(Budget.category == old_name, Budget.user_id == user_id)
        )
        budget = budget_result.scalar_one_or_none()
        if budget:
            budget.category = data.name

    await session.flush()
    await session.refresh(category)
    return category


@router.delete("/{category_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_category(category_id: str, session: DatabaseSession, user_id: RequiredUserId):
    result = await session.execute(
        select(Category).where(Category.id == category_id, Category.user_id == user_id)
    )
    category = result.scalar_one_or_none()
    if not category:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Category not found",
        )

    budget_result = await session.execute(
        select(Budget).where(Budget.category == category.name, Budget.user_id == user_id)
    )
    orphaned_budget = budget_result.scalar_one_or_none()
    if orphaned_budget:
        await session.delete(orphaned_budget)

    await session.delete(category)
    await session.flush()