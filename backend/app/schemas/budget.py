from pydantic import BaseModel, Field


class BudgetResponse(BaseModel):
    id: str
    category: str
    limit_amount: float
    spent_amount: float
    period_start: str
    period_end: str

    model_config = {"from_attributes": True}


class BudgetUpdate(BaseModel):
    limit_amount: float = Field(..., gt=0)
