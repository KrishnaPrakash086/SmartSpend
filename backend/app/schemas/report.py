from pydantic import BaseModel


class MonthlySummary(BaseModel):
    month: str
    income: float
    expenses: float
    savings: float


class CategoryBreakdown(BaseModel):
    name: str
    value: float
    color: str


class CategoryTrend(BaseModel):
    month: str
    food_and_dining: float = 0
    transport: float = 0
    entertainment: float = 0
    bills_and_utilities: float = 0
    shopping: float = 0
    other: float = 0


class ReportResponse(BaseModel):
    monthly: list[MonthlySummary]
    trends: list[dict]
    categories: list[CategoryBreakdown]
    ai_summary: str | None = None
