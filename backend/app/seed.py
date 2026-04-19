# Database seed script — populates demo data for categories, expenses, budgets, cards, and loans
import asyncio
import uuid

import structlog
from sqlalchemy import select

from app.database import AsyncSessionFactory
from app.models import (
    AgentActivity,
    Budget,
    Category,
    CreditCard,
    Expense,
    Loan,
    UserSettings,
    VoiceInteraction,
    WebhookEvent,
)

logger = structlog.get_logger()

CATEGORIES = [
    {"name": "Food & Dining", "color": "#10b981", "icon": "UtensilsCrossed"},
    {"name": "Transport", "color": "#8b5cf6", "icon": "Car"},
    {"name": "Entertainment", "color": "#f59e0b", "icon": "Gamepad2"},
    {"name": "Bills & Utilities", "color": "#3b82f6", "icon": "Zap"},
    {"name": "Shopping", "color": "#f43f5e", "icon": "ShoppingBag"},
    {"name": "Other", "color": "#64748b", "icon": "MoreHorizontal"},
]

EXPENSE_ENTRIES = [
    ("Swiggy order - Biryani", "Food & Dining", "UPI", "voice", 18.50, "2026-04-14"),
    ("Uber to Airport", "Transport", "UPI", "manual", 45.00, "2026-04-13"),
    ("Netflix Subscription", "Entertainment", "Credit Card", "manual", 15.99, "2026-04-01"),
    ("Electricity Bill", "Bills & Utilities", "Debit Card", "manual", 125.00, "2026-04-05"),
    ("Amazon - Headphones", "Shopping", "Credit Card", "manual", 79.99, "2026-04-10"),
    ("Starbucks Coffee", "Food & Dining", "UPI", "voice", 6.75, "2026-04-15"),
    ("Metro Card Recharge", "Transport", "Debit Card", "manual", 50.00, "2026-04-02"),
    ("Movie Tickets - IMAX", "Entertainment", "UPI", "manual", 32.00, "2026-04-06"),
    ("Water Bill", "Bills & Utilities", "Debit Card", "manual", 65.00, "2026-04-03"),
    ("Zara - Winter Jacket", "Shopping", "Credit Card", "manual", 129.99, "2026-04-08"),
    ("Pizza Hut Delivery", "Food & Dining", "Cash", "voice", 22.50, "2026-04-12"),
    ("Gas Station Fill-up", "Transport", "Debit Card", "manual", 58.00, "2026-04-09"),
    ("Spotify Premium", "Entertainment", "Credit Card", "manual", 9.99, "2026-04-01"),
    ("Internet Bill", "Bills & Utilities", "Debit Card", "manual", 79.99, "2026-04-01"),
    ("Nike Running Shoes", "Shopping", "Credit Card", "manual", 129.99, "2026-04-11"),
    ("Lunch at Cafe", "Food & Dining", "Cash", "voice", 15.00, "2026-04-11"),
    ("Lyft to Office", "Transport", "UPI", "voice", 18.50, "2026-04-10"),
    ("Concert Tickets", "Entertainment", "Credit Card", "manual", 89.00, "2026-04-07"),
    ("Phone Bill", "Bills & Utilities", "UPI", "manual", 85.00, "2026-04-01"),
    ("Books from Barnes & Noble", "Shopping", "Debit Card", "manual", 34.99, "2026-04-04"),
    ("Grocery - Whole Foods", "Food & Dining", "Debit Card", "manual", 165.30, "2026-04-09"),
    ("Parking Fee", "Transport", "Cash", "manual", 15.00, "2026-04-08"),
    ("Disney+ Annual", "Entertainment", "Credit Card", "manual", 139.99, "2026-03-15"),
    ("Gas Bill", "Bills & Utilities", "Debit Card", "manual", 95.00, "2026-04-04"),
    ("IKEA Home Decor", "Shopping", "Credit Card", "manual", 67.50, "2026-03-28"),
    ("Chipotle Burrito", "Food & Dining", "UPI", "voice", 12.95, "2026-04-14"),
    ("Toll Road Fee", "Transport", "Cash", "manual", 8.50, "2026-04-07"),
    ("Gaming Subscription", "Entertainment", "Credit Card", "manual", 14.99, "2026-04-01"),
    ("Rent Payment", "Bills & Utilities", "Debit Card", "manual", 350.00, "2026-04-01"),
    ("Target - Household", "Shopping", "Debit Card", "manual", 45.80, "2026-03-22"),
    ("Thai Food Delivery", "Food & Dining", "UPI", "voice", 28.40, "2026-04-13"),
    ("Bus Pass Monthly", "Transport", "Debit Card", "manual", 85.00, "2026-04-01"),
    ("Bowling Night", "Entertainment", "Cash", "manual", 35.00, "2026-03-30"),
    ("Insurance Premium", "Bills & Utilities", "Credit Card", "manual", 200.00, "2026-04-01"),
    ("Costco Bulk Shopping", "Shopping", "Debit Card", "manual", 156.75, "2026-03-18"),
    ("Sushi Restaurant", "Food & Dining", "Credit Card", "manual", 52.80, "2026-04-06"),
    ("Car Wash", "Transport", "Cash", "manual", 25.00, "2026-04-05"),
    ("Gym Membership", "Other", "Credit Card", "manual", 55.00, "2026-04-01"),
    ("Dry Cleaning", "Other", "Cash", "manual", 28.00, "2026-04-07"),
    ("Doctor Visit Copay", "Other", "Debit Card", "manual", 40.00, "2026-04-03"),
    ("Breakfast at Diner", "Food & Dining", "Cash", "voice", 14.25, "2026-04-10"),
    ("Uber Eats - Ramen", "Food & Dining", "UPI", "voice", 19.99, "2026-04-08"),
    ("Train Ticket", "Transport", "Debit Card", "manual", 35.00, "2026-03-25"),
    ("Karaoke Night", "Entertainment", "Cash", "manual", 45.00, "2026-03-20"),
    ("Cloud Storage Plan", "Bills & Utilities", "Credit Card", "manual", 9.99, "2026-04-01"),
    ("Etsy - Handmade Gift", "Shopping", "Credit Card", "manual", 42.50, "2026-03-14"),
    ("Smoothie King", "Food & Dining", "UPI", "voice", 8.50, "2026-04-15"),
    ("Airport Shuttle", "Transport", "Cash", "manual", 35.00, "2026-03-10"),
    ("Art Supplies", "Other", "Debit Card", "manual", 65.00, "2026-03-28"),
    ("Haircut", "Other", "Cash", "manual", 35.00, "2026-04-05"),
    ("Vitamins & Supplements", "Other", "Debit Card", "manual", 42.00, "2026-03-15"),
    ("Dominos Pizza", "Food & Dining", "UPI", "voice", 24.50, "2026-03-12"),
    ("Uber Pool Ride", "Transport", "UPI", "manual", 12.00, "2026-03-08"),
]

BUDGETS = [
    {"category": "Food & Dining", "limit_amount": 1500, "spent_amount": 1450, "period_start": "2026-04-01", "period_end": "2026-04-30"},
    {"category": "Transport", "limit_amount": 1200, "spent_amount": 890, "period_start": "2026-04-01", "period_end": "2026-04-30"},
    {"category": "Entertainment", "limit_amount": 600, "spent_amount": 650, "period_start": "2026-04-01", "period_end": "2026-04-30"},
    {"category": "Bills & Utilities", "limit_amount": 1500, "spent_amount": 1200, "period_start": "2026-04-01", "period_end": "2026-04-30"},
    {"category": "Shopping", "limit_amount": 1000, "spent_amount": 740, "period_start": "2026-04-01", "period_end": "2026-04-30"},
    {"category": "Other", "limit_amount": 500, "spent_amount": 300, "period_start": "2026-04-01", "period_end": "2026-04-30"},
]

CREDIT_CARDS = [
    {
        "bank_name": "Chase", "card_name": "Sapphire Preferred", "card_type": "Visa",
        "credit_limit": 15000, "used_amount": 4200, "billing_date": 15, "due_date": 5,
        "apr": 21.49, "rewards_rate": 2, "min_payment": 125,
    },
    {
        "bank_name": "Amex", "card_name": "Gold Card", "card_type": "Amex",
        "credit_limit": 10000, "used_amount": 2800, "billing_date": 20, "due_date": 10,
        "apr": 22.99, "rewards_rate": 4, "min_payment": 84,
    },
    {
        "bank_name": "Citi", "card_name": "Double Cash", "card_type": "Mastercard",
        "credit_limit": 8000, "used_amount": 6100, "billing_date": 1, "due_date": 21,
        "apr": 18.49, "rewards_rate": 2, "min_payment": 183,
    },
    {
        "bank_name": "Capital One", "card_name": "Venture X", "card_type": "Visa",
        "credit_limit": 20000, "used_amount": 3500, "billing_date": 25, "due_date": 15,
        "apr": 19.99, "rewards_rate": 2, "min_payment": 105,
    },
]

LOANS = [
    {
        "loan_type": "Home Loan", "bank_name": "Wells Fargo",
        "principal_amount": 320000, "remaining_amount": 285000,
        "emi": 1580, "interest_rate": 6.75,
        "tenure_months": 360, "remaining_months": 312,
        "start_date": "2022-06-01", "payment_method": "Auto-debit",
    },
    {
        "loan_type": "Car Loan", "bank_name": "Chase",
        "principal_amount": 35000, "remaining_amount": 22000,
        "emi": 620, "interest_rate": 5.49,
        "tenure_months": 72, "remaining_months": 42,
        "start_date": "2023-01-15", "payment_method": "Auto-debit",
    },
    {
        "loan_type": "Personal Loan", "bank_name": "SoFi",
        "principal_amount": 15000, "remaining_amount": 8400,
        "emi": 420, "interest_rate": 11.99,
        "tenure_months": 48, "remaining_months": 22,
        "start_date": "2024-06-01", "payment_method": "Manual",
    },
    {
        "loan_type": "Education Loan", "bank_name": "Sallie Mae",
        "principal_amount": 45000, "remaining_amount": 38000,
        "emi": 380, "interest_rate": 4.99,
        "tenure_months": 180, "remaining_months": 156,
        "start_date": "2025-01-01", "payment_method": "Standing Instruction",
    },
]

VOICE_INTERACTIONS = [
    {"transcript": "I spent forty-five dollars on lunch today", "parsed_result": {"amount": 45, "category": "Food & Dining", "description": "Lunch"}, "status": "success", "result_description": "Expense Created", "expense_id": "exp-001", "created_at": "2026-04-15T10:30:00Z"},
    {"transcript": "What's my food budget looking like?", "parsed_result": {"action": "check_budget", "category": "Food & Dining"}, "status": "success", "result_description": "Budget Checked", "expense_id": None, "created_at": "2026-04-15T09:15:00Z"},
    {"transcript": "Add two hundred for electricity bill", "parsed_result": {"amount": 200, "category": "Bills & Utilities", "description": "Electricity bill"}, "status": "success", "result_description": "Expense Created", "expense_id": "exp-004", "created_at": "2026-04-14T16:45:00Z"},
    {"transcript": "How much have I spent on Uber this month?", "parsed_result": {"action": "query", "category": "Transport", "keyword": "Uber"}, "status": "success", "result_description": "Budget Checked", "expense_id": None, "created_at": "2026-04-14T14:20:00Z"},
    {"transcript": "Twenty bucks for coffee and snacks", "parsed_result": {"amount": 20, "category": "Food & Dining", "description": "Coffee and snacks"}, "status": "success", "result_description": "Expense Created", "expense_id": "exp-006", "created_at": "2026-04-13T11:00:00Z"},
    {"transcript": "Record fifteen dollars for parking", "parsed_result": {"amount": 15, "category": "Transport", "description": "Parking"}, "status": "success", "result_description": "Expense Created", "expense_id": "exp-022", "created_at": "2026-04-13T08:30:00Z"},
    {"transcript": "Hmm something mumble...", "parsed_result": {}, "status": "failed", "result_description": "Failed — could not parse", "expense_id": None, "created_at": "2026-04-12T19:00:00Z"},
    {"transcript": "Spent sixty on groceries at Whole Foods", "parsed_result": {"amount": 60, "category": "Food & Dining", "description": "Groceries at Whole Foods"}, "status": "success", "result_description": "Expense Created", "expense_id": "exp-021", "created_at": "2026-04-12T15:30:00Z"},
    {"transcript": "Add thirty-five for Netflix and Disney Plus", "parsed_result": {"amount": 35, "category": "Entertainment", "description": "Netflix and Disney Plus"}, "status": "success", "result_description": "Expense Created", "expense_id": "exp-003", "created_at": "2026-04-11T20:00:00Z"},
    {"transcript": "What's my total spending this week?", "parsed_result": {"action": "query", "period": "this_week"}, "status": "success", "result_description": "Budget Checked", "expense_id": None, "created_at": "2026-04-11T10:00:00Z"},
    {"transcript": "Eighty dollars for new running shoes", "parsed_result": {"amount": 80, "category": "Shopping", "description": "Running shoes"}, "status": "success", "result_description": "Expense Created", "expense_id": "exp-015", "created_at": "2026-04-10T14:00:00Z"},
    {"transcript": "Record pizza delivery twenty-two fifty", "parsed_result": {"amount": 22.50, "category": "Food & Dining", "description": "Pizza delivery"}, "status": "success", "result_description": "Expense Created", "expense_id": "exp-011", "created_at": "2026-04-10T12:30:00Z"},
]

AGENT_ACTIVITIES = [
    {"agent_name": "Coordinator (ADK)", "agent_type": "coordinator", "action": "Received voice input → Routed to Expense Parser Agent", "details": {"input": "I spent forty-five dollars on lunch today", "route": "expense_parser"}, "duration_ms": 120, "created_at": "2026-04-15T10:30:00Z"},
    {"agent_name": "Expense Parser (LangChain)", "agent_type": "expense_parser", "action": "Parsed voice input → Categorized as Food & Dining → Created expense", "details": {"parsed": {"amount": 45, "category": "Food & Dining"}, "confidence": 0.95}, "duration_ms": 850, "created_at": "2026-04-15T10:30:01Z"},
    {"agent_name": "Budget Monitor (LangChain)", "agent_type": "budget_monitor", "action": "Budget check triggered → Food & Dining at 97% of limit", "details": {"category": "Food & Dining", "spent": 1450, "limit": 1500, "percentage": 97}, "duration_ms": 200, "created_at": "2026-04-15T10:30:02Z"},
    {"agent_name": "Budget Monitor (LangChain)", "agent_type": "budget_monitor", "action": "Alert generated → Food budget nearing limit", "details": {"alert_type": "warning", "threshold": 85}, "duration_ms": 150, "created_at": "2026-04-15T10:30:02Z"},
    {"agent_name": "Coordinator (ADK)", "agent_type": "coordinator", "action": "Received budget query → Routed to Budget Monitor", "details": {"input": "What's my food budget looking like?", "route": "budget_monitor"}, "duration_ms": 95, "created_at": "2026-04-15T09:15:00Z"},
    {"agent_name": "Budget Monitor (LangChain)", "agent_type": "budget_monitor", "action": "Retrieved budget status for Food & Dining → Responded to user", "details": {"spent": 1450, "limit": 1500, "remaining": 50}, "duration_ms": 300, "created_at": "2026-04-15T09:15:01Z"},
    {"agent_name": "Report Crew (CrewAI)", "agent_type": "report_crew", "action": "Analyst agent gathered spending data → Advisor agent generated insights", "details": {"period": "April 2026", "categories_analyzed": 6}, "duration_ms": 3200, "created_at": "2026-04-15T08:00:00Z"},
    {"agent_name": "Report Crew (CrewAI)", "agent_type": "report_crew", "action": "Weekly financial report generated successfully", "details": {"report_id": "rpt-042", "sections": ["spending_summary", "budget_adherence", "recommendations"]}, "duration_ms": 1500, "created_at": "2026-04-15T08:00:04Z"},
    {"agent_name": "Budget Council (AutoGen)", "agent_type": "budget_council", "action": "Council debate initiated on savings strategy optimization", "details": {"participants": ["Saver Agent", "Spender Agent", "Balancer Agent"], "topic": "Reduce dining expenses"}, "duration_ms": 4500, "created_at": "2026-04-14T22:00:00Z"},
    {"agent_name": "Budget Council (AutoGen)", "agent_type": "budget_council", "action": "Consensus reached → Recommend reducing dining out from 4x to 2x per week", "details": {"recommendation": "Reduce dining out frequency", "estimated_savings": 320, "votes": {"for": 2, "against": 1}}, "duration_ms": 2000, "created_at": "2026-04-14T22:00:05Z"},
    {"agent_name": "Coordinator (ADK)", "agent_type": "coordinator", "action": "Received expense input → Routed to Expense Parser", "details": {"input": "Add two hundred for electricity bill", "route": "expense_parser"}, "duration_ms": 110, "created_at": "2026-04-14T16:45:00Z"},
    {"agent_name": "Expense Parser (LangChain)", "agent_type": "expense_parser", "action": "Parsed input → Bills & Utilities category → Stored expense", "details": {"parsed": {"amount": 200, "category": "Bills & Utilities"}, "confidence": 0.98}, "duration_ms": 720, "created_at": "2026-04-14T16:45:01Z"},
    {"agent_name": "Budget Monitor (LangChain)", "agent_type": "budget_monitor", "action": "Post-expense check → Bills & Utilities at 80%", "details": {"category": "Bills & Utilities", "spent": 1200, "limit": 1500}, "duration_ms": 180, "created_at": "2026-04-14T16:45:02Z"},
    {"agent_name": "Coordinator (ADK)", "agent_type": "coordinator", "action": "Received query → Routed to Budget Monitor for Uber spending lookup", "details": {"input": "How much have I spent on Uber this month?", "route": "budget_monitor"}, "duration_ms": 100, "created_at": "2026-04-14T14:20:00Z"},
    {"agent_name": "Budget Monitor (LangChain)", "agent_type": "budget_monitor", "action": "Queried Uber-related expenses → Found 3 transactions totaling $87", "details": {"keyword": "Uber", "transactions_found": 3, "total": 87}, "duration_ms": 450, "created_at": "2026-04-14T14:20:01Z"},
    {"agent_name": "Report Crew (CrewAI)", "agent_type": "report_crew", "action": "Daily spending digest compiled → Sent notification", "details": {"date": "2026-04-14", "total_spent": 285, "transactions": 5}, "duration_ms": 1800, "created_at": "2026-04-14T23:00:00Z"},
    {"agent_name": "Budget Council (AutoGen)", "agent_type": "budget_council", "action": "Entertainment budget exceeded → Emergency review initiated", "details": {"category": "Entertainment", "overspend": 50, "action": "reallocate"}, "duration_ms": 3000, "created_at": "2026-04-13T20:00:00Z"},
    {"agent_name": "Expense Parser (LangChain)", "agent_type": "expense_parser", "action": "Failed to parse voice input → Returned error to user", "details": {"input": "Hmm something mumble...", "error": "Confidence below threshold"}, "duration_ms": 500, "created_at": "2026-04-12T19:00:01Z"},
    {"agent_name": "Coordinator (ADK)", "agent_type": "coordinator", "action": "System health check → All agents operational", "details": {"agents_checked": 4, "all_healthy": True}, "duration_ms": 50, "created_at": "2026-04-12T06:00:00Z"},
    {"agent_name": "Report Crew (CrewAI)", "agent_type": "report_crew", "action": "Monthly AI insights generated for March 2026", "details": {"insights_count": 5, "key_finding": "Food spending up 15%"}, "duration_ms": 5200, "created_at": "2026-04-01T00:05:00Z"},
]

WEBHOOK_EVENTS = [
    {"event_type": "expense.created", "payload": {"expense_id": "exp-001", "amount": 45}, "status": "delivered", "created_at": "2026-04-15T10:30:03Z"},
    {"event_type": "budget.alert", "payload": {"category": "Food & Dining", "percentage": 97}, "status": "delivered", "created_at": "2026-04-15T10:30:04Z"},
    {"event_type": "report.generated", "payload": {"report_id": "rpt-042"}, "status": "delivered", "created_at": "2026-04-15T08:00:05Z"},
    {"event_type": "expense.created", "payload": {"expense_id": "exp-004", "amount": 200}, "status": "pending", "created_at": "2026-04-14T16:45:03Z"},
    {"event_type": "budget.exceeded", "payload": {"category": "Entertainment", "overspend": 50}, "status": "failed", "created_at": "2026-04-13T20:00:01Z"},
]


async def seed_database():
    from datetime import date, datetime

    logger.info("seed_database_started")

    async with AsyncSessionFactory() as session:
        # Idempotency guard — skip seeding if any category already exists
        existing = await session.execute(select(Category).limit(1))
        if existing.scalar_one_or_none():
            logger.info("seed_database_skipped", reason="data already exists")
            return

        for cat in CATEGORIES:
            session.add(Category(id=str(uuid.uuid4()), **cat))
        logger.info("seeded_categories", count=len(CATEGORIES))

        expense_ids = {}
        for idx, (desc, category, payment, added_via, amount, date_str) in enumerate(EXPENSE_ENTRIES):
            expense_id = f"exp-{idx + 1:03d}"
            expense_ids[expense_id] = True
            session.add(
                Expense(
                    id=expense_id,
                    description=desc,
                    amount=amount,
                    category=category,
                    date=date.fromisoformat(date_str),
                    payment_method=payment,
                    added_via=added_via,
                )
            )
        logger.info("seeded_expenses", count=len(EXPENSE_ENTRIES))

        for budget in BUDGETS:
            session.add(
                Budget(
                    id=str(uuid.uuid4()),
                    category=budget["category"],
                    limit_amount=budget["limit_amount"],
                    spent_amount=budget["spent_amount"],
                    period_start=date.fromisoformat(budget["period_start"]),
                    period_end=date.fromisoformat(budget["period_end"]),
                )
            )
        logger.info("seeded_budgets", count=len(BUDGETS))

        for card in CREDIT_CARDS:
            session.add(CreditCard(id=str(uuid.uuid4()), **card))
        logger.info("seeded_credit_cards", count=len(CREDIT_CARDS))

        for loan in LOANS:
            session.add(Loan(id=str(uuid.uuid4()), **loan))
        logger.info("seeded_loans", count=len(LOANS))

        session.add(
            UserSettings(
                id=str(uuid.uuid4()),
                currency="USD",
                monthly_income=8450,
                budget_cycle_start=1,
                notify_budget_exceeded=True,
                notify_weekly_summary=True,
                notify_voice_confirmations=True,
                notify_ai_insights=False,
                voice_enabled=True,
                language="English",
            )
        )
        logger.info("seeded_user_settings")

        for vi in VOICE_INTERACTIONS:
            session.add(
                VoiceInteraction(
                    id=str(uuid.uuid4()),
                    transcript=vi["transcript"],
                    parsed_result=vi["parsed_result"],
                    status=vi["status"],
                    result_description=vi["result_description"],
                    expense_id=vi["expense_id"],
                    created_at=datetime.fromisoformat(vi["created_at"].replace("Z", "+00:00")),
                )
            )
        logger.info("seeded_voice_interactions", count=len(VOICE_INTERACTIONS))

        for aa in AGENT_ACTIVITIES:
            session.add(
                AgentActivity(
                    id=str(uuid.uuid4()),
                    agent_name=aa["agent_name"],
                    agent_type=aa["agent_type"],
                    action=aa["action"],
                    details=aa["details"],
                    duration_ms=aa["duration_ms"],
                    created_at=datetime.fromisoformat(aa["created_at"].replace("Z", "+00:00")),
                )
            )
        logger.info("seeded_agent_activities", count=len(AGENT_ACTIVITIES))

        for we in WEBHOOK_EVENTS:
            session.add(
                WebhookEvent(
                    id=str(uuid.uuid4()),
                    event_type=we["event_type"],
                    payload=we["payload"],
                    status=we["status"],
                    created_at=datetime.fromisoformat(we["created_at"].replace("Z", "+00:00")),
                )
            )
        logger.info("seeded_webhook_events", count=len(WEBHOOK_EVENTS))

        await session.commit()
        logger.info("seed_database_completed")


if __name__ == "__main__":
    asyncio.run(seed_database())
