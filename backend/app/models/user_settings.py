# SQLAlchemy model for user preferences — currency, income, notification toggles, and voice config
import uuid

from sqlalchemy import Boolean, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class UserSettings(Base):
    __tablename__ = "user_settings"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    currency: Mapped[str] = mapped_column(String(10), nullable=False, default="USD")
    monthly_income: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False, default=0)
    budget_cycle_start: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    # Flat boolean columns instead of nested JSON for straightforward SQL queries and partial updates
    notify_budget_exceeded: Mapped[bool] = mapped_column(Boolean, default=True)
    notify_weekly_summary: Mapped[bool] = mapped_column(Boolean, default=True)
    notify_voice_confirmations: Mapped[bool] = mapped_column(Boolean, default=True)
    notify_ai_insights: Mapped[bool] = mapped_column(Boolean, default=False)

    voice_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    language: Mapped[str] = mapped_column(String(20), nullable=False, default="English")
