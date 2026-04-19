from datetime import datetime, timedelta, timezone
import structlog
from fastapi import APIRouter, HTTPException, status, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import bcrypt
from jose import jwt, JWTError
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from app.config import get_settings
from app.dependencies import DatabaseSession
from app.models.user import User
from app.models import Category, Budget, UserSettings
from app.schemas.auth import SignUpRequest, SignInRequest, AuthResponse, UserResponse

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/auth", tags=["Auth"])

security = HTTPBearer(auto_error=False)


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode("utf-8"), hashed.encode("utf-8"))

SECRET_KEY = "smartspend-jwt-secret-key-change-in-production"
ALGORITHM = "HS256"
TOKEN_EXPIRE_HOURS = 24

def create_token(user_id: str, username: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(hours=TOKEN_EXPIRE_HOURS)
    payload = {"sub": user_id, "username": username, "exp": expire}
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)

def verify_token(token: str) -> dict | None:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except JWTError:
        return None

@router.post("/signup", response_model=AuthResponse, status_code=status.HTTP_201_CREATED)
async def signup(data: SignUpRequest, session: DatabaseSession):
    existing = await session.execute(select(User).where(User.username == data.username))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Username already taken")
    
    user = User(
        username=data.username,
        password_hash=hash_password(data.password),
        display_name=data.display_name or data.username,
        preferred_currency=data.preferred_currency,
        monthly_income=data.monthly_income,
        is_first_login=True,
    )
    session.add(user)
    await session.flush()
    await session.refresh(user)
    
    category_colors = {
        "Food & Dining": "#10b981", "Transport": "#8b5cf6", "Entertainment": "#f59e0b",
        "Bills & Utilities": "#3b82f6", "Shopping": "#f43f5e", "Other": "#64748b",
    }
    for cat_name in data.initial_categories:
        cat = Category(name=cat_name, color=category_colors.get(cat_name, "#64748b"), icon="MoreHorizontal", user_id=user.id)
        session.add(cat)
    
    settings = UserSettings(
        currency=data.preferred_currency,
        monthly_income=data.monthly_income,
        budget_cycle_start=1,
        notify_budget_exceeded=True,
        notify_weekly_summary=True,
        notify_voice_confirmations=True,
        notify_ai_insights=False,
        voice_enabled=True,
        language="English",
        user_id=user.id,
    )
    session.add(settings)
    
    from datetime import date
    today = date.today()
    period_start = today.replace(day=1)
    if today.month == 12:
        period_end = today.replace(year=today.year + 1, month=1, day=1) - timedelta(days=1)
    else:
        period_end = today.replace(month=today.month + 1, day=1) - timedelta(days=1)
    
    for cat_name in data.initial_categories:
        budget = Budget(category=cat_name, limit_amount=0, spent_amount=0, period_start=period_start, period_end=period_end, user_id=user.id)
        session.add(budget)
    
    try:
        await session.flush()
    except IntegrityError as exc:
        await session.rollback()
        logger.warning("signup_seed_conflict", user_id=user.id, error=str(exc))
        raise HTTPException(status_code=409, detail="Account setup conflict — please try a different username")
    
    token = create_token(user.id, user.username)
    return AuthResponse(
        token=token,
        user=UserResponse(
            id=user.id, username=user.username, display_name=user.display_name,
            preferred_currency=user.preferred_currency, monthly_income=float(user.monthly_income),
            is_first_login=True,
        ),
    )

@router.post("/signin", response_model=AuthResponse)
async def signin(data: SignInRequest, session: DatabaseSession):
    result = await session.execute(select(User).where(User.username == data.username))
    user = result.scalar_one_or_none()
    if not user or not verify_password(data.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid username or password")
    
    token = create_token(user.id, user.username)
    return AuthResponse(
        token=token,
        user=UserResponse(
            id=user.id, username=user.username, display_name=user.display_name,
            preferred_currency=user.preferred_currency, monthly_income=float(user.monthly_income),
            is_first_login=user.is_first_login,
        ),
    )

@router.get("/me", response_model=UserResponse)
async def get_me(session: DatabaseSession, credentials: HTTPAuthorizationCredentials = Depends(security)):
    if not credentials:
        raise HTTPException(status_code=401, detail="Not authenticated")
    payload = verify_token(credentials.credentials)
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    
    result = await session.execute(select(User).where(User.id == payload["sub"]))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    
    return UserResponse(
        id=user.id, username=user.username, display_name=user.display_name,
        preferred_currency=user.preferred_currency, monthly_income=float(user.monthly_income),
        is_first_login=user.is_first_login,
    )

@router.post("/complete-onboarding")
async def complete_onboarding(session: DatabaseSession, credentials: HTTPAuthorizationCredentials = Depends(security)):
    if not credentials:
        raise HTTPException(status_code=401, detail="Not authenticated")
    payload = verify_token(credentials.credentials)
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    
    result = await session.execute(select(User).where(User.id == payload["sub"]))
    user = result.scalar_one_or_none()
    if user:
        user.is_first_login = False
        await session.flush()
    
    return {"status": "ok"}


@router.post("/change-password")
async def change_password(data: dict, session: DatabaseSession, credentials: HTTPAuthorizationCredentials = Depends(security)):
    if not credentials:
        raise HTTPException(status_code=401, detail="Not authenticated")
    payload = verify_token(credentials.credentials)
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    current_password = data.get("current_password", "")
    new_password = data.get("new_password", "")
    confirm_password = data.get("confirm_password", "")

    if len(new_password) < 6:
        raise HTTPException(status_code=422, detail="New password must be at least 6 characters")
    if new_password != confirm_password:
        raise HTTPException(status_code=422, detail="New passwords don't match")

    result = await session.execute(select(User).where(User.id == payload["sub"]))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if not verify_password(current_password, user.password_hash):
        raise HTTPException(status_code=400, detail="Current password is incorrect")

    user.password_hash = hash_password(new_password)
    await session.flush()

    return {"status": "ok", "message": "Password changed successfully"}
