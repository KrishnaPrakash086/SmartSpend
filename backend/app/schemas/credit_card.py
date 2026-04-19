# Pydantic schemas for credit cards with alias mapping between camelCase frontend and snake_case backend
from typing import Literal

from pydantic import BaseModel, Field


class CreditCardCreate(BaseModel):
    bank_name: str = Field(..., alias="bankName")
    card_name: str = Field(..., alias="cardName")
    card_type: Literal["Visa", "Mastercard", "Amex", "RuPay"] = Field(..., alias="cardType")
    credit_limit: float = Field(..., gt=0, alias="limit")
    used_amount: float = Field(0, ge=0, alias="used")
    billing_date: int = Field(..., ge=1, le=31, alias="billingDate")
    due_date: int = Field(..., ge=1, le=31, alias="dueDate")
    apr: float = Field(..., ge=0)
    rewards_rate: float = Field(0, ge=0, alias="rewardsRate")
    min_payment: float = Field(0, ge=0, alias="minPayment")

    model_config = {"populate_by_name": True}


class CreditCardResponse(BaseModel):
    id: str
    bankName: str
    cardName: str
    cardType: str
    limit: float
    used: float
    billingDate: int
    dueDate: int
    apr: float
    rewardsRate: float
    minPayment: float

    model_config = {"from_attributes": True}

    @classmethod
    def from_orm_model(cls, card) -> "CreditCardResponse":
        return cls(
            id=card.id,
            bankName=card.bank_name,
            cardName=card.card_name,
            cardType=card.card_type,
            limit=float(card.credit_limit),
            used=float(card.used_amount),
            billingDate=card.billing_date,
            dueDate=card.due_date,
            apr=float(card.apr),
            rewardsRate=float(card.rewards_rate),
            minPayment=float(card.min_payment),
        )


class CreditCardUpdate(BaseModel):
    bank_name: str | None = Field(None, alias="bankName")
    card_name: str | None = Field(None, alias="cardName")
    card_type: str | None = Field(None, alias="cardType")
    credit_limit: float | None = Field(None, alias="limit")
    used_amount: float | None = Field(None, alias="used")
    apr: float | None = None
    rewards_rate: float | None = Field(None, alias="rewardsRate")
    min_payment: float | None = Field(None, alias="minPayment")

    model_config = {"populate_by_name": True}
