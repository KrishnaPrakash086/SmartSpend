# SQLAlchemy model for voice-to-expense interaction logs and their parse results
import uuid
from datetime import datetime

from sqlalchemy import DateTime, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.database import Base


class VoiceInteraction(Base):
    __tablename__ = "voice_interactions"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    transcript: Mapped[str] = mapped_column(Text, nullable=False)
    # JSONB stores variable-shape parse output (amount, category, etc.) without schema migration per field
    parsed_result: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="processing")
    result_description: Mapped[str] = mapped_column(String(500), nullable=False, default="")
    expense_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )
