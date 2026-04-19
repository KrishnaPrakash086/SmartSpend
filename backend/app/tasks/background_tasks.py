# Celery background tasks — report generation, budget recalculation, and alert checks
import asyncio
import uuid

import structlog
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session, sessionmaker

from app.config import get_settings
from app.models import Budget, Expense, WebhookEvent
from app.tasks.celery_app import celery_application

logger = structlog.get_logger()

# Celery workers run outside the async event loop, so a synchronous engine is needed
settings = get_settings()
sync_engine = create_engine(settings.sync_database_url)
SyncSessionFactory = sessionmaker(bind=sync_engine)


@celery_application.task(name="generate_monthly_report")
def generate_monthly_report():
    logger.info("generate_monthly_report_started")

    with SyncSessionFactory() as session:
        expenses = session.execute(select(Expense)).scalars().all()
        budgets = session.execute(select(Budget)).scalars().all()

        expense_data = [
            {
                "description": e.description,
                "amount": float(e.amount),
                "category": e.category,
                "date": str(e.date),
            }
            for e in expenses
        ]
        budget_data = [
            {
                "category": b.category,
                "limit_amount": float(b.limit_amount),
                "spent_amount": float(b.spent_amount),
            }
            for b in budgets
        ]

        total_expenses = sum(e["amount"] for e in expense_data)
        category_totals: dict[str, float] = {}
        for expense_entry in expense_data:
            cat = expense_entry["category"]
            category_totals[cat] = category_totals.get(cat, 0) + expense_entry["amount"]

    async def _generate():
        from app.agents import ReportCrewAgent

        financial_context = {
            "total_expenses": total_expenses,
            "budgets": budget_data,
            "category_breakdown": [
                {"name": cat, "value": val} for cat, val in category_totals.items()
            ],
        }
        agent = ReportCrewAgent()
        return await agent.generate_report(financial_context)

    # Bridge async agent code into Celery's sync worker via asyncio.run
    result = asyncio.run(_generate())
    logger.info("generate_monthly_report_completed", result=result)
    return result


@celery_application.task(name="recalculate_all_budgets")
def recalculate_all_budgets():
    logger.info("recalculate_all_budgets_started")

    with SyncSessionFactory() as session:
        budgets = session.execute(select(Budget)).scalars().all()
        updated_count = 0

        for budget in budgets:
            total = session.execute(
                select(func.coalesce(func.sum(Expense.amount), 0)).where(
                    Expense.category == budget.category,
                    Expense.date >= budget.period_start,
                    Expense.date <= budget.period_end,
                )
            ).scalar()
            budget.spent_amount = float(total)
            updated_count += 1

        session.commit()

    logger.info("recalculate_all_budgets_completed", updated_count=updated_count)


@celery_application.task(name="check_budget_alerts")
def check_budget_alerts():
    logger.info("check_budget_alerts_started")
    alerts_created = 0

    with SyncSessionFactory() as session:
        budgets = session.execute(select(Budget)).scalars().all()

        for budget in budgets:
            if float(budget.limit_amount) <= 0:
                continue

            percentage = (float(budget.spent_amount) / float(budget.limit_amount)) * 100

            if percentage < 80:
                continue

            event_type = (
                "budget.exceeded" if percentage >= 100 else "budget.alert"
            )
            event = WebhookEvent(
                id=str(uuid.uuid4()),
                event_type=event_type,
                payload={
                    "category": budget.category,
                    "percentage": round(percentage, 1),
                    "spent": float(budget.spent_amount),
                    "limit": float(budget.limit_amount),
                },
                status="pending",
            )
            session.add(event)
            alerts_created += 1

        session.commit()

    logger.info("check_budget_alerts_completed", alerts_created=alerts_created)


@celery_application.task(name="process_recurring_expenses")
def process_recurring_expenses():
    logger.info("process_recurring_expenses_started")
    logger.info(
        "process_recurring_expenses_completed",
        message="no recurring rules configured yet",
    )
