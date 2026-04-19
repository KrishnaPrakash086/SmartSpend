# Schemas for conversational chat, A2UI interactive cards, and HITL confirmation flows
from pydantic import BaseModel


class ParsedExpenseData(BaseModel):
    description: str | None = None
    amount: float | None = None
    category: str | None = None
    date: str | None = None
    payment_method: str | None = None


class ParsedCardData(BaseModel):
    bank_name: str | None = None
    card_name: str | None = None
    card_type: str | None = None
    credit_limit: float | None = None
    used_amount: float | None = None
    apr: float | None = None
    rewards_rate: float | None = None
    billing_date: int | None = None
    due_date: int | None = None
    min_payment: float | None = None


class ParsedLoanData(BaseModel):
    loan_type: str | None = None
    bank_name: str | None = None
    principal_amount: float | None = None
    remaining_amount: float | None = None
    emi: float | None = None
    interest_rate: float | None = None
    tenure_months: int | None = None
    remaining_months: int | None = None
    start_date: str | None = None
    payment_method: str | None = None


class ChatRequest(BaseModel):
    message: str
    source: str = "text"
    context_id: str | None = None


class ChatResponse(BaseModel):
    message_id: str
    role: str = "assistant"
    content: str
    intent: str | None = None
    parsed_expense: ParsedExpenseData | None = None
    missing_fields: list[str] | None = None
    requires_confirmation: bool = False
    # A2UI fields — tell the frontend which interactive card to render
    a2ui_type: str | None = None
    a2ui_data: dict | None = None
    agent_trace: list[dict] | None = None


class ConfirmExpenseRequest(BaseModel):
    message_id: str
    parsed_expense: ParsedExpenseData


class ConfirmCardRequest(BaseModel):
    message_id: str
    parsed_card: ParsedCardData


class ConfirmLoanRequest(BaseModel):
    message_id: str
    parsed_loan: ParsedLoanData


class UpdateEntityRequest(BaseModel):
    entity_type: str
    entity_id: str
    updates: dict
