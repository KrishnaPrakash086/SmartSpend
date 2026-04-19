# SQLAlchemy model for individual expense records
import uuid
from datetime import date, datetime

from sqlalchemy import Date, DateTime, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.database import Base


class Expense(Base):
    __tablename__ = "expenses"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    description: Mapped[str] = mapped_column(String(500), nullable=False)
    amount: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    # Category stored as a denormalized string to simplify queries and avoid FK joins on every list call
    category: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    payment_method: Mapped[str] = mapped_column(String(50), nullable=False)
    added_via: Mapped[str] = mapped_column(String(20), nullable=False, default="manual")
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Split transactions share a group_id — the total across the group equals the original amount
    group_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    group_description: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )
