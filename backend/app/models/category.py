import uuid

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Category(Base):
    __tablename__ = "categories"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    color: Mapped[str] = mapped_column(String(20), nullable=False, default="#64748b")
    icon: Mapped[str] = mapped_column(String(50), nullable=False, default="MoreHorizontal")
    user_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
