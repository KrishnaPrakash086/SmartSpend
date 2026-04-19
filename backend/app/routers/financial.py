from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from app.dependencies import DatabaseSession
from app.schemas import (
    CreditCardCreate,
    CreditCardResponse,
    CreditCardUpdate,
    LoanCreate,
    LoanResponse,
    LoanUpdate,
)
from app.services import financial_service

router = APIRouter(prefix="/financial", tags=["Financial"])


@router.get("/credit-cards", response_model=list[CreditCardResponse])
async def list_credit_cards(session: DatabaseSession):
    cards = await financial_service.list_credit_cards(session)
    return [CreditCardResponse.from_orm_model(card) for card in cards]


@router.post(
    "/credit-cards",
    response_model=CreditCardResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_credit_card(
    data: CreditCardCreate, session: DatabaseSession
):
    card = await financial_service.create_credit_card(session, data)
    return CreditCardResponse.from_orm_model(card)


@router.patch("/credit-cards/{card_id}", response_model=CreditCardResponse)
async def update_credit_card(
    card_id: str, data: CreditCardUpdate, session: DatabaseSession
):
    card = await financial_service.update_credit_card(session, card_id, data)
    return CreditCardResponse.from_orm_model(card)


@router.get("/loans", response_model=list[LoanResponse])
async def list_loans(session: DatabaseSession):
    loans = await financial_service.list_loans(session)
    return [LoanResponse.from_orm_model(loan) for loan in loans]


@router.post(
    "/loans",
    response_model=LoanResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_loan(data: LoanCreate, session: DatabaseSession):
    loan = await financial_service.create_loan(session, data)
    return LoanResponse.from_orm_model(loan)


@router.patch("/loans/{loan_id}", response_model=LoanResponse)
async def update_loan(
    loan_id: str, data: LoanUpdate, session: DatabaseSession
):
    loan = await financial_service.update_loan(session, loan_id, data)
    return LoanResponse.from_orm_model(loan)


@router.get("/flags", response_model=list[dict])
async def get_financial_flags(
    session: DatabaseSession, monthly_income: float | None = None
):
    if monthly_income is None:
        from app.models import UserSettings as _UserSettings
        from sqlalchemy import select as _select
        us_result = await session.execute(_select(_UserSettings))
        user_settings = us_result.scalar_one_or_none()
        monthly_income = float(user_settings.monthly_income) if user_settings else 0
    return await financial_service.generate_financial_flags(
        session, monthly_income
    )


@router.delete("/credit-cards/{card_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_credit_card(card_id: str, session: DatabaseSession):
    from app.models import CreditCard

    result = await session.execute(select(CreditCard).where(CreditCard.id == card_id))
    card = result.scalar_one_or_none()
    if not card:
        raise HTTPException(status_code=404, detail="Credit card not found")
    await session.delete(card)
    await session.flush()


@router.delete("/loans/{loan_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_loan(loan_id: str, session: DatabaseSession):
    from app.models import Loan

    result = await session.execute(select(Loan).where(Loan.id == loan_id))
    loan = result.scalar_one_or_none()
    if not loan:
        raise HTTPException(status_code=404, detail="Loan not found")
    await session.delete(loan)
    await session.flush()
