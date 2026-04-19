from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from app.dependencies import DatabaseSession
from app.models import Category
from app.schemas import CategoryCreate, CategoryResponse

router = APIRouter(prefix="/categories", tags=["Categories"])


@router.get("/", response_model=list[CategoryResponse])
async def list_categories(session: DatabaseSession):
    result = await session.execute(select(Category))
    return list(result.scalars().all())


@router.post(
    "/",
    response_model=CategoryResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_category(data: CategoryCreate, session: DatabaseSession):
    category = Category(
        name=data.name,
        color=data.color,
        icon=data.icon,
    )
    session.add(category)
    await session.flush()
    await session.refresh(category)
    return category


@router.patch("/{category_id}", response_model=CategoryResponse)
async def update_category(category_id: str, data: CategoryCreate, session: DatabaseSession):
    result = await session.execute(select(Category).where(Category.id == category_id))
    category = result.scalar_one_or_none()
    if not category:
        raise HTTPException(status_code=404, detail="Category not found")
    category.name = data.name
    category.color = data.color
    category.icon = data.icon
    await session.flush()
    await session.refresh(category)
    return category


@router.delete("/{category_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_category(category_id: str, session: DatabaseSession):
    result = await session.execute(
        select(Category).where(Category.id == category_id)
    )
    category = result.scalar_one_or_none()
    if not category:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Category not found",
        )
    await session.delete(category)
    await session.flush()
