# VAPI voice-assistant webhook — receives transcripts, parses expenses, and returns tool-call responses
import uuid

import structlog
from fastapi import APIRouter

from app.dependencies import DatabaseSession
from app.events.sse import event_manager
from app.models import AgentActivity, VoiceInteraction
from app.schemas import ExpenseCreate
from app.services.expense_service import create_expense

logger = structlog.get_logger()

router = APIRouter(prefix="/vapi", tags=["VAPI"])


@router.post("/webhook")
async def vapi_webhook(body: dict, session: DatabaseSession):
    message = body.get("message", {})
    function_call = message.get("functionCall", {})
    transcript = function_call.get("parameters", {}).get("transcript", "")
    tool_call_id = function_call.get("id", str(uuid.uuid4()))

    if not transcript:
        return {
            "results": [
                {
                    "toolCallId": tool_call_id,
                    "result": "No transcript provided.",
                }
            ]
        }

    # Reuse the same singleton coordinator as the chat router — avoids reloading intent .md files per call
    from app.routers.chat import _get_coordinator
    coordinator = _get_coordinator()
    result = await coordinator.process_message(transcript)

    parsed_expense = result.get("parsed_expense", {})
    missing_fields = result.get("missing_fields", [])

    voice_interaction = VoiceInteraction(
        transcript=transcript,
        parsed_result=parsed_expense or {},
        status="success" if parsed_expense and not missing_fields else "processing",
        result_description="",
    )

    for trace in result.get("agent_trace", []):
        agent_label = trace.get("agent", "Unknown")
        activity = AgentActivity(
            agent_name=agent_label,
            agent_type=agent_label.split("(")[0].strip().lower().replace(" ", "_"),
            action=trace.get("action", ""),
            details=trace,
            duration_ms=trace.get("duration_ms", 0),
        )
        session.add(activity)

    parsed_amount = parsed_expense.get("amount", 0) if parsed_expense else 0
    parsed_date = parsed_expense.get("date", "") if parsed_expense else ""
    has_valid_fields = (
        parsed_expense
        and not missing_fields
        and parsed_amount > 0
        and len(parsed_date) >= 8
    )

    if has_valid_fields:
        from datetime import date as date_type
        try:
            date_type.fromisoformat(parsed_date)
        except ValueError:
            parsed_date = date_type.today().isoformat()

        expense_data = ExpenseCreate(
            description=parsed_expense.get("description", "Voice expense"),
            amount=parsed_amount,
            category=parsed_expense.get("category", "Other"),
            date=parsed_date,
            payment_method=parsed_expense.get("payment_method", "Cash"),
            added_via="voice",
        )
        expense = await create_expense(session, expense_data)
        voice_interaction.expense_id = expense.id
        voice_interaction.status = "success"
        voice_interaction.result_description = (
            f"Logged ${expense.amount:.2f} expense for "
            f"{expense.description} in {expense.category} category"
        )

        await event_manager.publish(
            "expense.created",
            {
                "expense_id": expense.id,
                "amount": float(expense.amount),
                "source": "voice",
            },
        )

        response_text = voice_interaction.result_description
    elif not has_valid_fields:
        missing_labels = ", ".join(missing_fields) if missing_fields else "details"
        voice_interaction.result_description = (
            f"Partially parsed. Missing: {missing_labels}"
        )
        response_text = (
            f"I got part of that, but I still need {missing_labels}. "
            "Could you clarify?"
        )

    session.add(voice_interaction)

    # Response format required by VAPI: array of results keyed by toolCallId
    return {
        "results": [
            {
                "toolCallId": tool_call_id,
                "result": response_text,
            }
        ]
    }


@router.get("/health")
async def vapi_health():
    return {"status": "ok"}
