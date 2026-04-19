from datetime import date

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import CreditCard, Expense, Loan
from app.schemas import CreditCardCreate, CreditCardUpdate, LoanCreate, LoanUpdate


async def list_credit_cards(session: AsyncSession, user_id: str) -> list[CreditCard]:
    result = await session.execute(
        select(CreditCard).where(CreditCard.user_id == user_id)
    )
    return list(result.scalars().all())


async def create_credit_card(
    session: AsyncSession, data: CreditCardCreate, user_id: str
) -> CreditCard:
    card = CreditCard(
        bank_name=data.bank_name,
        card_name=data.card_name,
        card_type=data.card_type,
        credit_limit=data.credit_limit,
        used_amount=data.used_amount,
        billing_date=data.billing_date,
        due_date=data.due_date,
        apr=data.apr,
        rewards_rate=data.rewards_rate,
        min_payment=data.min_payment,
        user_id=user_id,
    )
    session.add(card)
    await session.flush()
    await session.refresh(card)
    return card


async def update_credit_card(
    session: AsyncSession, card_id: str, data: CreditCardUpdate, user_id: str
) -> CreditCard:
    result = await session.execute(
        select(CreditCard).where(CreditCard.id == card_id, CreditCard.user_id == user_id)
    )
    card = result.scalar_one_or_none()
    if not card:
        raise HTTPException(status_code=404, detail="Credit card not found")

    update_fields = data.model_dump(exclude_unset=True, by_alias=False)
    for field_name, value in update_fields.items():
        setattr(card, field_name, value)

    await session.flush()
    await session.refresh(card)
    return card


async def list_loans(session: AsyncSession, user_id: str) -> list[Loan]:
    result = await session.execute(
        select(Loan).where(Loan.user_id == user_id)
    )
    return list(result.scalars().all())


async def create_loan(session: AsyncSession, data: LoanCreate, user_id: str) -> Loan:
    loan = Loan(
        loan_type=data.loan_type,
        bank_name=data.bank_name,
        principal_amount=data.principal_amount,
        remaining_amount=data.remaining_amount,
        emi=data.emi,
        interest_rate=data.interest_rate,
        tenure_months=data.tenure_months,
        remaining_months=data.remaining_months,
        start_date=data.start_date,
        payment_method=data.payment_method,
        user_id=user_id,
    )
    session.add(loan)
    await session.flush()
    await session.refresh(loan)
    return loan


async def update_loan(
    session: AsyncSession, loan_id: str, data: LoanUpdate, user_id: str
) -> Loan:
    result = await session.execute(
        select(Loan).where(Loan.id == loan_id, Loan.user_id == user_id)
    )
    loan = result.scalar_one_or_none()
    if not loan:
        raise HTTPException(status_code=404, detail="Loan not found")

    update_fields = data.model_dump(exclude_unset=True, by_alias=False)
    for field_name, value in update_fields.items():
        setattr(loan, field_name, value)

    await session.flush()
    await session.refresh(loan)
    return loan


async def generate_financial_flags(
    session: AsyncSession, monthly_income: float, user_id: str
) -> list[dict]:
    cards_result = await session.execute(
        select(CreditCard).where(CreditCard.user_id == user_id)
    )
    credit_cards = list(cards_result.scalars().all())

    loans_result = await session.execute(
        select(Loan).where(Loan.user_id == user_id)
    )
    loans = list(loans_result.scalars().all())

    current_month_start = date.today().replace(day=1)
    expenses_result = await session.execute(
        select(func.coalesce(func.sum(Expense.amount), 0)).where(
            Expense.date >= current_month_start,
            Expense.user_id == user_id,
        )
    )
    total_expenses = float(expenses_result.scalar())

    flags: list[dict] = []

    for card in credit_cards:
        credit_limit = float(card.credit_limit)
        used_amount = float(card.used_amount)
        if credit_limit <= 0:
            continue

        utilization = (used_amount / credit_limit) * 100
        if utilization > 75:
            severity = "critical" if utilization > 90 else "warning"
            paydown_target = round(used_amount - credit_limit * 0.3)
            flags.append({
                "id": f"flag-cc-{card.id}",
                "severity": severity,
                "title": (
                    f"{card.bank_name} {card.card_name} utilization "
                    f"at {round(utilization)}%"
                ),
                "description": (
                    f"Your credit utilization is "
                    f"{'dangerously ' if utilization > 90 else ''}"
                    f"high. This hurts your credit score. Ideal is below 30%."
                ),
                "action": (
                    f"Pay down ${paydown_target} to bring utilization under 30%."
                ),
                "category": "credit",
            })

        monthly_interest = used_amount * float(card.apr) / 100 / 12
        if monthly_interest > 50:
            flags.append({
                "id": f"flag-interest-{card.id}",
                "severity": "warning",
                "title": (
                    f"{card.bank_name} costing "
                    f"${round(monthly_interest)}/mo in interest"
                ),
                "description": (
                    f"Carrying a ${used_amount:,.0f} balance "
                    f"at {float(card.apr)}% APR."
                ),
                "action": (
                    f"Pay full balance to save "
                    f"${round(monthly_interest * 12)}/year in interest."
                ),
                "category": "credit",
            })

    total_emi = sum(float(loan.emi) for loan in loans)
    if monthly_income > 0:
        emi_to_income = (total_emi / monthly_income) * 100
        if emi_to_income > 40:
            flags.append({
                "id": "flag-emi-ratio",
                "severity": "critical",
                "title": f"EMI-to-income ratio at {round(emi_to_income)}%",
                "description": (
                    f"Total EMIs of ${total_emi:,.0f}/mo against "
                    f"${monthly_income:,.0f} income. Safe limit is 40%."
                ),
                "action": (
                    "Consider consolidating loans or "
                    "increasing income sources."
                ),
                "category": "loan",
            })

    if loans:
        highest_rate_loan = max(loans, key=lambda l: float(l.interest_rate))
        interest_rate = float(highest_rate_loan.interest_rate)
        if interest_rate > 8:
            remaining = float(highest_rate_loan.remaining_amount)
            monthly_interest_cost = round(remaining * interest_rate / 100 / 12)
            flags.append({
                "id": "flag-high-interest",
                "severity": "warning",
                "title": (
                    f"Prioritize {highest_rate_loan.loan_type} repayment "
                    f"({interest_rate}% APR)"
                ),
                "description": (
                    f"{highest_rate_loan.bank_name} "
                    f"{highest_rate_loan.loan_type} has the highest interest "
                    f"rate. You're paying ~${monthly_interest_cost}/mo "
                    f"in interest alone."
                ),
                "action": (
                    f"Pay $100 extra/mo to save "
                    f"~${round(monthly_interest_cost * 3)} over next 3 months."
                ),
                "category": "loan",
            })

    total_limit = sum(float(c.credit_limit) for c in credit_cards)
    total_used = sum(float(c.used_amount) for c in credit_cards)
    if total_limit > 0:
        total_utilization = (total_used / total_limit) * 100
        if total_utilization < 30:
            flags.append({
                "id": "flag-good-util",
                "severity": "success",
                "title": (
                    f"Overall credit utilization healthy "
                    f"at {round(total_utilization)}%"
                ),
                "description": (
                    f"Total used ${total_used:,.0f} of ${total_limit:,.0f} "
                    f"across {len(credit_cards)} cards."
                ),
                "action": (
                    "Keep it up! Under 30% helps improve your credit score."
                ),
                "category": "credit",
            })

    if monthly_income > 0:
        savings_rate = (
            (monthly_income - total_expenses - total_emi) / monthly_income
        ) * 100
        if savings_rate < 10:
            flags.append({
                "id": "flag-savings",
                "severity": "critical",
                "title": (
                    f"Savings rate critically low at {round(savings_rate)}%"
                ),
                "description": (
                    "After expenses and EMIs, you're barely saving. "
                    "Minimum recommended is 20%."
                ),
                "action": (
                    "Review subscriptions and discretionary spending "
                    "to free up $300+/mo."
                ),
                "category": "savings",
            })
        elif savings_rate < 20:
            flags.append({
                "id": "flag-savings-ok",
                "severity": "warning",
                "title": (
                    f"Savings rate at {round(savings_rate)}% "
                    "\u2014 room to improve"
                ),
                "description": (
                    "You're saving but below the 20% recommended target."
                ),
                "action": (
                    "Automate savings by setting up a transfer on payday."
                ),
                "category": "savings",
            })

    severity_order = {"critical": 0, "warning": 1, "info": 2, "success": 3}
    flags.sort(key=lambda f: severity_order.get(f["severity"], 99))

    return flags
