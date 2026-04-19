from datetime import date, timedelta

from fastapi import APIRouter
from sqlalchemy import func, select

from app.dependencies import DatabaseSession, RequiredUserId
from app.models import Budget, CreditCard, Expense, Loan, UserSettings
from app.schemas import ReportResponse
from app.services import report_service

router = APIRouter(prefix="/reports", tags=["Reports"])


@router.get("/", response_model=ReportResponse)
async def get_report_data(session: DatabaseSession, user_id: RequiredUserId):
    settings_result = await session.execute(
        select(UserSettings).where(UserSettings.user_id == user_id)
    )
    settings_row = settings_result.scalar_one_or_none()

    report_data = await report_service.generate_report_data(
        session, settings_row, user_id
    )
    return ReportResponse(**report_data)


@router.get("/payment-methods")
async def payment_method_breakdown(session: DatabaseSession, user_id: RequiredUserId):
    start_of_month = date.today().replace(day=1)

    query = (
        select(
            Expense.payment_method.label("method"),
            func.coalesce(func.sum(Expense.amount), 0).label("total"),
        )
        .where(Expense.date >= start_of_month, Expense.user_id == user_id)
        .group_by(Expense.payment_method)
    )
    result = await session.execute(query)
    rows = result.all()

    method_colors = {
        "Credit Card": "#8b5cf6",
        "Debit Card": "#3b82f6",
        "UPI": "#10b981",
        "Bank Transfer": "#f59e0b",
        "Cash": "#64748b",
    }

    return [
        {
            "name": row.method,
            "value": float(row.total),
            "color": method_colors.get(row.method, "#64748b"),
        }
        for row in rows if float(row.total) > 0
    ]


@router.get("/loans-summary")
async def loans_summary(session: DatabaseSession, user_id: RequiredUserId):
    result = await session.execute(
        select(Loan).where(Loan.user_id == user_id)
    )
    loans = result.scalars().all()
    return [
        {
            "type": loan.loan_type,
            "emi": float(loan.emi),
            "remaining": float(loan.remaining_amount),
            "rate": f"{float(loan.interest_rate)}%",
            "tenure": f"{loan.tenure_months // 12} yrs" if loan.tenure_months >= 12 else f"{loan.tenure_months} mo",
            "status": "active" if loan.remaining_amount > 0 else "closed",
        }
        for loan in loans
    ]


@router.get("/smart-actions")
async def smart_actions(session: DatabaseSession, user_id: RequiredUserId):
    actions: list[dict] = []

    budgets_result = await session.execute(
        select(Budget).where(Budget.user_id == user_id)
    )
    budgets = budgets_result.scalars().all()
    for budget in budgets:
        limit = float(budget.limit_amount)
        spent = float(budget.spent_amount)
        if limit <= 0:
            continue
        pct = (spent / limit) * 100
        if pct > 100:
            actions.append({
                "icon": "AlertTriangle",
                "title": f"{budget.category} budget exceeded",
                "desc": f"You spent ${spent:.0f} vs a ${limit:.0f} limit ({pct:.0f}%). Consider reducing spend in this category.",
                "priority": "high",
            })
        elif pct > 85:
            remaining = limit - spent
            actions.append({
                "icon": "AlertTriangle",
                "title": f"{budget.category} budget at {pct:.0f}%",
                "desc": f"Only ${remaining:.0f} left in your {budget.category} budget for the rest of the cycle.",
                "priority": "medium",
            })

    loans_result = await session.execute(
        select(Loan).where(Loan.user_id == user_id)
    )
    loans = loans_result.scalars().all()
    if loans:
        highest_rate_loan = max(loans, key=lambda l: float(l.interest_rate))
        if float(highest_rate_loan.interest_rate) > 10:
            monthly_interest = float(highest_rate_loan.remaining_amount) * float(highest_rate_loan.interest_rate) / 100 / 12
            actions.append({
                "icon": "CreditCard",
                "title": f"Pay off {highest_rate_loan.loan_type} first",
                "desc": f"Your {highest_rate_loan.loan_type} at {highest_rate_loan.interest_rate}% APR costs ~${monthly_interest:.0f}/mo in interest alone.",
                "priority": "high",
            })

    cards_result = await session.execute(
        select(CreditCard).where(CreditCard.user_id == user_id)
    )
    cards = cards_result.scalars().all()
    total_limit = sum(float(c.credit_limit) for c in cards)
    total_used = sum(float(c.used_amount) for c in cards)
    if total_limit > 0:
        utilization = (total_used / total_limit) * 100
        if utilization > 30:
            actions.append({
                "icon": "TrendingUp",
                "title": f"Credit utilization at {utilization:.0f}%",
                "desc": f"Total used ${total_used:.0f} of ${total_limit:.0f}. Keep utilization under 30% to improve credit score.",
                "priority": "medium" if utilization < 60 else "high",
            })

    thirty_days_ago = date.today() - timedelta(days=30)
    month_spend_result = await session.execute(
        select(func.coalesce(func.sum(Expense.amount), 0))
        .where(Expense.date >= thirty_days_ago, Expense.user_id == user_id)
    )
    month_total = float(month_spend_result.scalar() or 0)

    if not actions and month_total > 0:
        actions.append({
            "icon": "Lightbulb",
            "title": "You're on track this month",
            "desc": f"Total spending of ${month_total:.0f} in the last 30 days. Keep logging expenses to get more insights.",
            "priority": "low",
        })

    return actions
