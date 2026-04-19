# SQLAlchemy model for loan accounts including EMI, tenure, and repayment tracking
import uuid

from sqlalchemy import Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Loan(Base):
    __tablename__ = "loans"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    loan_type: Mapped[str] = mapped_column(String(50), nullable=False)
    bank_name: Mapped[str] = mapped_column(String(100), nullable=False)
    principal_amount: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False)
    remaining_amount: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False)
    emi: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    interest_rate: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False)
    tenure_months: Mapped[int] = mapped_column(Integer, nullable=False)
    remaining_months: Mapped[int] = mapped_column(Integer, nullable=False)
    start_date: Mapped[str] = mapped_column(String(10), nullable=False)
    payment_method: Mapped[str] = mapped_column(String(30), nullable=False)
    user_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
