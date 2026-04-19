# Pydantic schemas for expense creation, response serialization, and query filtering
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field


class ExpenseCreate(BaseModel):
    description: str = Field(..., min_length=1, max_length=500)
    amount: float = Field(..., gt=0)
    category: str = Field(..., min_length=1, max_length=100)
    # Date is str (not date type) because frontend sends ISO strings and agent parsers produce strings
    date: str
    payment_method: Literal["Cash", "Credit Card", "Debit Card", "UPI", "Bank Transfer"]
    added_via: Literal["voice", "manual"] = "manual"
    notes: str | None = None
    group_id: str | None = None
    group_description: str | None = None


class ExpenseResponse(BaseModel):
    id: str
    description: str
    amount: float
    category: str
    date: str
    payment_method: str
    added_via: str
    notes: str | None
    group_id: str | None
    group_description: str | None
    created_at: str

    model_config = {"from_attributes": True}


class ExpenseFilters(BaseModel):
    search: str | None = None
    category: str | None = None
    date_from: str | None = None
    date_to: str | None = None
    page: int = 1
    per_page: int = 50


class ExpenseUpdate(BaseModel):
    description: str | None = None
    amount: float | None = Field(None, gt=0)
    category: str | None = None
    date: str | None = None
    payment_method: str | None = None
    notes: str | None = None
