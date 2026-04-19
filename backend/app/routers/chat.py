import uuid
import time
from datetime import date

import structlog
from fastapi import APIRouter, HTTPException
from sqlalchemy import select

from app.agents import (
    BudgetCouncilAgent,
    BudgetMonitorAgent,
    CoordinatorAgent,
    ReportCrewAgent,
)
from app.dependencies import DatabaseSession, RequiredUserId
from app.events.sse import event_manager
from app.models import AgentActivity, Budget, CreditCard, Expense, Loan, VoiceInteraction, WebhookEvent
from app.schemas import ExpenseCreate
from app.schemas.chat import (
    ChatRequest,
    ChatResponse,
    ConfirmCardRequest,
    ConfirmExpenseRequest,
    ConfirmLoanRequest,
    ParsedExpenseData,
    UpdateEntityRequest,
)
from app.services.expense_service import create_expense

logger = structlog.get_logger()

_cached_coordinator: CoordinatorAgent | None = None


GURU_SYSTEM_CONTEXT = (
    "You are Sana, an expert AI financial advisor for the SmartSpend app. You specialize in:\n"
    "- Stock market, equities, ETFs, mutual funds\n"
    "- Loans, EMIs, mortgage strategy, debt management\n"
    "- Investment planning, portfolio allocation, asset management\n"
    "- Savings strategies, emergency funds, retirement planning\n"
    "- Tax optimization basics, insurance needs\n\n"
    "STYLE:\n"
    "- Be warm, concise, and educational\n"
    "- Give concrete, actionable advice — not vague generalities\n"
    "- Use plain language; explain jargon when needed\n"
    "- Add a brief disclaimer for specific recommendations: 'This is educational, not certified advice'\n\n"
    "HANDLING NON-FINANCIAL QUESTIONS:\n"
    "- If the user asks a general question (not strictly finance), answer helpfully and completely — do not be "
    "evasive. You are an intelligent assistant who happens to specialize in finance.\n"
    "- For math, general knowledge, productivity, technology questions — answer them directly.\n"
    "- Only redirect if asked to do something harmful, illegal, or outside ethical AI use.\n"
    "- After answering a non-finance question briefly, you may offer: 'Anything financial I can help with?'\n\n"
    "WHAT YOU DON'T DO:\n"
    "- Do not log expenses or manage SmartSpend data (that's the SmartSpend assistant's job)\n"
    "- Do not invent current stock prices, exchange rates, or live market data\n"
    "- Do not recommend specific brokers or products by name"
)


def _get_coordinator() -> CoordinatorAgent:
    global _cached_coordinator
    if _cached_coordinator is None:
        _cached_coordinator = CoordinatorAgent()
    return _cached_coordinator


router = APIRouter(prefix="/chat", tags=["Chat"])


@router.post("/", response_model=ChatResponse)
async def process_chat_message(request: ChatRequest, session: DatabaseSession, user_id: RequiredUserId):
    coordinator = _get_coordinator()
    result = await coordinator.process_message(
        request.message, {"context_id": request.context_id}, session=session
    )

    message_id = str(uuid.uuid4())

    parsed_expense = None
    if result.get("intent") == "expense" and result.get("parsed_expense"):
        raw_parsed = result["parsed_expense"]
        if isinstance(raw_parsed, dict):
            parsed_expense = ParsedExpenseData(**raw_parsed)

    for trace in result.get("agent_trace", []):
        agent_label = trace.get("agent", "Unknown")
        activity = AgentActivity(
            agent_name=agent_label,
            agent_type=agent_label.split("(")[0].strip().lower().replace(" ", "_"),
            action=trace.get("action", ""),
            details=trace,
            duration_ms=trace.get("duration_ms", 0),
            user_id=user_id,
        )
        session.add(activity)

    if request.source == "voice":
        voice_status = "success" if result.get("content") else "failed"
        voice_interaction = VoiceInteraction(
            transcript=request.message,
            parsed_result=result.get("parsed_expense") or {},
            status=voice_status,
            result_description=(result.get("content", ""))[:500],
            user_id=user_id,
        )
        session.add(voice_interaction)

    await event_manager.publish(
        "chat.message", {"message_id": message_id, "intent": result.get("intent")}
    )

    return ChatResponse(
        message_id=message_id,
        content=result.get("content", ""),
        intent=result.get("intent"),
        parsed_expense=parsed_expense,
        missing_fields=result.get("missing_fields"),
        requires_confirmation=result.get("requires_confirmation", False),
        a2ui_type=result.get("a2ui_type"),
        a2ui_data=result.get("a2ui_data"),
        agent_trace=result.get("agent_trace"),
    )


@router.post("/confirm")
async def confirm_expense(request: ConfirmExpenseRequest, session: DatabaseSession, user_id: RequiredUserId):
    expense_data = ExpenseCreate(
        description=request.parsed_expense.description,
        amount=request.parsed_expense.amount,
        category=request.parsed_expense.category,
        date=request.parsed_expense.date,
        payment_method=request.parsed_expense.payment_method,
    )
    expense = await create_expense(session, expense_data, user_id)

    activity = AgentActivity(
        agent_name="Coordinator (ADK)",
        agent_type="coordinator",
        action=f"Confirmed and created expense: {expense.description}",
        details={"expense_id": expense.id, "amount": float(expense.amount)},
        duration_ms=0,
        user_id=user_id,
    )
    session.add(activity)

    webhook = WebhookEvent(
        event_type="expense.created",
        payload={
            "expense_id": expense.id,
            "amount": float(expense.amount),
            "category": expense.category,
        },
        status="pending",
    )
    session.add(webhook)

    await event_manager.publish(
        "expense.created",
        {
            "expense_id": expense.id,
            "amount": float(expense.amount),
            "category": expense.category,
        },
    )

    return {
        "id": expense.id,
        "description": expense.description,
        "amount": float(expense.amount),
        "category": expense.category,
    }


@router.post("/confirm-bulk")
async def confirm_bulk_expenses(body: dict, session: DatabaseSession, user_id: RequiredUserId):
    expenses_data = body.get("expenses", [])
    if not expenses_data:
        raise HTTPException(status_code=422, detail="No expenses provided")

    created = []
    for exp in expenses_data:
        expense_data = ExpenseCreate(
            description=exp.get("description", "Expense"),
            amount=exp.get("amount", 0),
            category=exp.get("category", "Other"),
            date=exp.get("date", ""),
            payment_method=exp.get("payment_method", "Cash"),
        )
        expense = await create_expense(session, expense_data, user_id)
        created.append({
            "id": expense.id,
            "description": expense.description,
            "amount": float(expense.amount),
            "category": expense.category,
            "date": expense.date.isoformat() if expense.date else "",
        })

        session.add(AgentActivity(
            agent_name="Coordinator (ADK)",
            agent_type="coordinator",
            action=f"Bulk-confirmed expense: {expense.description}",
            details={"expense_id": expense.id, "amount": float(expense.amount)},
            duration_ms=0,
            user_id=user_id,
        ))

    await event_manager.publish("expenses.bulk_created", {"count": len(created)})
    return {"created": created, "count": len(created)}


@router.post("/confirm-card")
async def confirm_card(request: ConfirmCardRequest, session: DatabaseSession, user_id: RequiredUserId):
    card = CreditCard(
        bank_name=request.parsed_card.bank_name or "",
        card_name=request.parsed_card.card_name or "",
        card_type=request.parsed_card.card_type or "Visa",
        credit_limit=request.parsed_card.credit_limit or 0,
        used_amount=request.parsed_card.used_amount or 0,
        billing_date=request.parsed_card.billing_date or 15,
        due_date=request.parsed_card.due_date or 5,
        apr=request.parsed_card.apr or 0,
        rewards_rate=request.parsed_card.rewards_rate or 0,
        min_payment=request.parsed_card.min_payment or 0,
        user_id=user_id,
    )
    session.add(card)
    await session.flush()
    await session.refresh(card)

    activity = AgentActivity(
        agent_name="Coordinator (ADK)",
        agent_type="coordinator",
        action=f"Confirmed and created credit card: {card.bank_name} {card.card_name}",
        details={"card_id": card.id, "bank_name": card.bank_name},
        duration_ms=0,
        user_id=user_id,
    )
    session.add(activity)

    await event_manager.publish(
        "card.created",
        {"card_id": card.id, "bank_name": card.bank_name, "card_name": card.card_name},
    )

    return {
        "id": card.id,
        "bankName": card.bank_name,
        "cardName": card.card_name,
        "cardType": card.card_type,
        "limit": float(card.credit_limit),
        "used": float(card.used_amount),
        "apr": float(card.apr),
        "rewardsRate": float(card.rewards_rate),
        "billingDate": card.billing_date,
        "dueDate": card.due_date,
        "minPayment": float(card.min_payment),
    }


@router.post("/confirm-loan")
async def confirm_loan(request: ConfirmLoanRequest, session: DatabaseSession, user_id: RequiredUserId):
    loan = Loan(
        loan_type=request.parsed_loan.loan_type or "Personal Loan",
        bank_name=request.parsed_loan.bank_name or "",
        principal_amount=request.parsed_loan.principal_amount or 0,
        remaining_amount=request.parsed_loan.remaining_amount or request.parsed_loan.principal_amount or 0,
        emi=request.parsed_loan.emi or 0,
        interest_rate=request.parsed_loan.interest_rate or 0,
        tenure_months=request.parsed_loan.tenure_months or 12,
        remaining_months=request.parsed_loan.remaining_months or request.parsed_loan.tenure_months or 12,
        start_date=request.parsed_loan.start_date or date.today().isoformat(),
        payment_method=request.parsed_loan.payment_method or "Auto-debit",
        user_id=user_id,
    )
    session.add(loan)
    await session.flush()
    await session.refresh(loan)

    activity = AgentActivity(
        agent_name="Coordinator (ADK)",
        agent_type="coordinator",
        action=f"Confirmed and created loan: {loan.loan_type} from {loan.bank_name}",
        details={"loan_id": loan.id, "bank_name": loan.bank_name},
        duration_ms=0,
        user_id=user_id,
    )
    session.add(activity)

    await event_manager.publish(
        "loan.created",
        {"loan_id": loan.id, "loan_type": loan.loan_type, "bank_name": loan.bank_name},
    )

    return {
        "id": loan.id,
        "loanType": loan.loan_type,
        "bankName": loan.bank_name,
        "principalAmount": float(loan.principal_amount),
        "remainingAmount": float(loan.remaining_amount),
        "emi": float(loan.emi),
        "interestRate": float(loan.interest_rate),
        "tenureMonths": loan.tenure_months,
        "remainingMonths": loan.remaining_months,
        "startDate": loan.start_date,
        "paymentMethod": loan.payment_method,
    }


@router.post("/update")
async def update_entity(request: UpdateEntityRequest, session: DatabaseSession, user_id: RequiredUserId):
    entity_type_map = {
        "credit_card": CreditCard,
        "loan": Loan,
        "budget": Budget,
    }

    model_class = entity_type_map.get(request.entity_type)
    if not model_class:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown entity type: {request.entity_type}. Valid types: {', '.join(entity_type_map.keys())}",
        )

    query_result = await session.execute(
        select(model_class).where(model_class.id == request.entity_id, model_class.user_id == user_id)
    )
    entity = query_result.scalar_one_or_none()
    if not entity:
        raise HTTPException(
            status_code=404,
            detail=f"{request.entity_type} with id {request.entity_id} not found",
        )

    for field_name, field_value in request.updates.items():
        if hasattr(entity, field_name):
            setattr(entity, field_name, field_value)

    await session.flush()
    await session.refresh(entity)

    activity = AgentActivity(
        agent_name="Coordinator (ADK)",
        agent_type="coordinator",
        action=f"Updated {request.entity_type} {request.entity_id}: {list(request.updates.keys())}",
        details={"entity_type": request.entity_type, "entity_id": request.entity_id, "updates": request.updates},
        duration_ms=0,
        user_id=user_id,
    )
    session.add(activity)

    return {"id": entity.id, "entity_type": request.entity_type, "updated_fields": list(request.updates.keys())}


@router.post("/analyze")
async def analyze_finances(session: DatabaseSession, user_id: RequiredUserId):
    start_time = time.perf_counter()
    results = {}

    budgets_result = await session.execute(
        select(Budget).where(Budget.user_id == user_id)
    )
    budgets = budgets_result.scalars().all()
    budget_data = [
        {
            "category": b.category,
            "limit_amount": float(b.limit_amount),
            "spent_amount": float(b.spent_amount),
        }
        for b in budgets
    ]

    expenses_result = await session.execute(
        select(Expense).where(Expense.user_id == user_id)
    )
    expenses = expenses_result.scalars().all()
    expense_data = [
        {
            "description": e.description,
            "amount": float(e.amount),
            "category": e.category,
            "date": str(e.date),
        }
        for e in expenses
    ]

    budget_monitor = BudgetMonitorAgent()
    budget_analysis = await budget_monitor.analyze_budgets(budget_data, expense_data)
    results["budget_analysis"] = budget_analysis

    total_expenses = sum(e["amount"] for e in expense_data)
    category_breakdown = {}
    for expense in expense_data:
        cat = expense["category"]
        category_breakdown[cat] = category_breakdown.get(cat, 0) + expense["amount"]

    from app.models import UserSettings as _UserSettings
    us_result = await session.execute(
        select(_UserSettings).where(_UserSettings.user_id == user_id)
    )
    user_settings = us_result.scalar_one_or_none()
    monthly_income_value = float(user_settings.monthly_income) if user_settings else 0

    financial_context = {
        "total_expenses": total_expenses,
        "total_income": monthly_income_value,
        "budgets": budget_data,
        "category_breakdown": [
            {"name": cat, "value": value} for cat, value in category_breakdown.items()
        ],
    }

    report_crew = ReportCrewAgent()
    report = await report_crew.generate_report(financial_context)
    results["report"] = report

    council = BudgetCouncilAgent()
    council_result = await council.debate_budget_strategy(financial_context)
    results["council"] = council_result

    total_duration_ms = int((time.perf_counter() - start_time) * 1000)

    agent_log_entries = [
        ("Budget Monitor (LangChain)", "budget_monitor", "Budget analysis completed", "budget_analysis"),
        ("Report Crew (CrewAI)", "report_crew", "Financial report generated", "report"),
        ("Budget Council (AutoGen)", "budget_council", "Strategy debate concluded", "council"),
    ]
    for agent_name, agent_type, action, result_key in agent_log_entries:
        activity = AgentActivity(
            agent_name=agent_name,
            agent_type=agent_type,
            action=action,
            details=results.get(result_key, {}),
            duration_ms=total_duration_ms // 3,
            user_id=user_id,
        )
        session.add(activity)

    return results


@router.post("/guru")
async def guru_chat(request: ChatRequest, session: DatabaseSession, user_id: RequiredUserId):
    import asyncio as _asyncio
    import time as _time
    from langchain_core.messages import SystemMessage, HumanMessage

    from app.config import get_settings
    from app.services.llm_provider import get_shared_llm

    start_time = _time.perf_counter()
    reply_content = ""
    used_llm = False
    llm = get_shared_llm()
    timeout = get_settings().llm_request_timeout_seconds

    if llm:
        try:
            response = await _asyncio.wait_for(
                llm.ainvoke([
                    SystemMessage(content=GURU_SYSTEM_CONTEXT),
                    HumanMessage(content=request.message),
                ]),
                timeout=timeout,
            )
            reply_content = (response.content or "").strip()
            used_llm = True
        except _asyncio.TimeoutError:
            logger.warning("guru_llm_timeout")
        except Exception as error:
            logger.warning("guru_llm_failed", error=str(error))

    if not reply_content:
        reply_content = (
            "The financial advisor is temporarily unavailable (LLM offline). "
            "General tip: diversify across asset classes, keep 6 months of emergency savings, "
            "and prioritize high-interest debt before investing."
        )

    duration_ms = int((_time.perf_counter() - start_time) * 1000)

    activity = AgentActivity(
        agent_name="Financial Guru (Gemini)",
        agent_type="guru",
        action=f"Answered advisory query ({'LLM' if used_llm else 'fallback'})",
        details={"query": request.message[:200], "used_llm": used_llm},
        duration_ms=duration_ms,
        user_id=user_id,
    )
    session.add(activity)

    await event_manager.publish("guru.response", {"duration_ms": duration_ms})

    return {
        "content": reply_content,
        "used_llm": used_llm,
        "duration_ms": duration_ms,
    }
