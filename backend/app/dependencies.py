# Reusable FastAPI dependency aliases for database session injection
from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_database_session

DatabaseSession = Annotated[AsyncSession, Depends(get_database_session)]
