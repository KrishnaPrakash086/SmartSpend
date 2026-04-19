# SQLAlchemy model for credit card accounts, utilization tracking, and billing metadata
import uuid

from sqlalchemy import Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class CreditCard(Base):
    __tablename__ = "credit_cards"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    bank_name: Mapped[str] = mapped_column(String(100), nullable=False)
    card_name: Mapped[str] = mapped_column(String(100), nullable=False)
    card_type: Mapped[str] = mapped_column(String(20), nullable=False)
    # credit_limit is the issuer cap; used_amount is current statement balance (used for utilization %)
    credit_limit: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    used_amount: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False, default=0)
    billing_date: Mapped[int] = mapped_column(Integer, nullable=False)
    due_date: Mapped[int] = mapped_column(Integer, nullable=False)
    apr: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False)
    rewards_rate: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False, default=0)
    min_payment: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False, default=0)
    user_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
