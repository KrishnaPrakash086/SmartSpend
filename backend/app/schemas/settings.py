# Pydantic schemas that reshape flat DB columns into nested notification preferences for the frontend
from pydantic import BaseModel


class NotificationPreferences(BaseModel):
    budget_exceeded: bool = True
    weekly_summary: bool = True
    voice_confirmations: bool = True
    ai_insights: bool = False


class UserSettingsResponse(BaseModel):
    currency: str
    monthly_income: float
    budget_cycle_start: int
    notifications: NotificationPreferences
    voice_enabled: bool
    language: str

    model_config = {"from_attributes": True}

    # Maps flat notify_* DB columns into a nested NotificationPreferences object for the frontend
    @classmethod
    def from_orm_model(cls, row) -> "UserSettingsResponse":
        return cls(
            currency=row.currency,
            monthly_income=float(row.monthly_income),
            budget_cycle_start=row.budget_cycle_start,
            notifications=NotificationPreferences(
                budget_exceeded=row.notify_budget_exceeded,
                weekly_summary=row.notify_weekly_summary,
                voice_confirmations=row.notify_voice_confirmations,
                ai_insights=row.notify_ai_insights,
            ),
            voice_enabled=row.voice_enabled,
            language=row.language,
        )


class UserSettingsUpdate(BaseModel):
    currency: str | None = None
    monthly_income: float | None = None
    budget_cycle_start: int | None = None
    notifications: NotificationPreferences | None = None
    voice_enabled: bool | None = None
    language: str | None = None
