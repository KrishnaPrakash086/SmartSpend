from typing import Annotated
from fastapi import Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.database import get_database_session

DatabaseSession = Annotated[AsyncSession, Depends(get_database_session)]

_security = HTTPBearer(auto_error=False)

async def get_current_user_id(
    credentials: HTTPAuthorizationCredentials = Depends(_security),
) -> str | None:
    """Extract user_id from JWT. Returns None for unauthenticated requests (public endpoints)."""
    if not credentials:
        return None
    from app.routers.auth import verify_token
    payload = verify_token(credentials.credentials)
    if not payload:
        return None
    return payload.get("sub")

async def require_current_user_id(
    credentials: HTTPAuthorizationCredentials = Depends(_security),
) -> str:
    """Same as get_current_user_id but raises 401 if not authenticated."""
    if not credentials:
        raise HTTPException(status_code=401, detail="Authentication required")
    from app.routers.auth import verify_token
    payload = verify_token(credentials.credentials)
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid token payload")
    return user_id

OptionalUserId = Annotated[str | None, Depends(get_current_user_id)]
RequiredUserId = Annotated[str, Depends(require_current_user_id)]
