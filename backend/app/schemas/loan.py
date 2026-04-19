# Pydantic schemas for loan CRUD with camelCase alias mapping for frontend compatibility
from typing import Literal

from pydantic import BaseModel, Field


class LoanCreate(BaseModel):
    loan_type: str = Field(..., alias="type")
    bank_name: str = Field(..., alias="bankName")
    principal_amount: float = Field(..., gt=0, alias="principalAmount")
    remaining_amount: float = Field(..., ge=0, alias="remainingAmount")
    emi: float = Field(..., gt=0)
    interest_rate: float = Field(..., ge=0, alias="interestRate")
    tenure_months: int = Field(..., gt=0, alias="tenureMonths")
    remaining_months: int = Field(..., ge=0, alias="remainingMonths")
    start_date: str = Field(..., alias="startDate")
    payment_method: Literal["Auto-debit", "Manual", "Standing Instruction"] = Field(
        ..., alias="paymentMethod"
    )

    model_config = {"populate_by_name": True}


class LoanResponse(BaseModel):
    id: str
    type: str
    bankName: str
    principalAmount: float
    remainingAmount: float
    emi: float
    interestRate: float
    tenureMonths: int
    remainingMonths: int
    startDate: str
    paymentMethod: str

    model_config = {"from_attributes": True}

    # Manual ORM-to-schema mapping because column names (snake_case) differ from response keys (camelCase)
    @classmethod
    def from_orm_model(cls, loan) -> "LoanResponse":
        return cls(
            id=loan.id,
            type=loan.loan_type,
            bankName=loan.bank_name,
            principalAmount=float(loan.principal_amount),
            remainingAmount=float(loan.remaining_amount),
            emi=float(loan.emi),
            interestRate=float(loan.interest_rate),
            tenureMonths=loan.tenure_months,
            remainingMonths=loan.remaining_months,
            startDate=loan.start_date,
            paymentMethod=loan.payment_method,
        )


class LoanUpdate(BaseModel):
    remaining_amount: float | None = Field(None, alias="remainingAmount")
    emi: float | None = None
    remaining_months: int | None = Field(None, alias="remainingMonths")

    model_config = {"populate_by_name": True}
