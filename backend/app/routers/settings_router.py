# User settings endpoints with auto-creation of default row on first access
from fastapi import APIRouter
from sqlalchemy import select

from app.dependencies import DatabaseSession
from app.models import UserSettings
from app.schemas import UserSettingsResponse, UserSettingsUpdate

router = APIRouter(prefix="/settings", tags=["Settings"])


@router.get("/", response_model=UserSettingsResponse)
async def get_settings(session: DatabaseSession):
    result = await session.execute(select(UserSettings))
    settings = result.scalar_one_or_none()

    # Auto-create default settings row if none exists (single-tenant assumption)
    if not settings:
        settings = UserSettings()
        session.add(settings)
        await session.flush()
        await session.refresh(settings)

    return UserSettingsResponse.from_orm_model(settings)


@router.patch("/", response_model=UserSettingsResponse)
async def update_settings(
    data: UserSettingsUpdate, session: DatabaseSession
):
    result = await session.execute(select(UserSettings))
    settings = result.scalar_one_or_none()

    if not settings:
        settings = UserSettings()
        session.add(settings)
        await session.flush()
        await session.refresh(settings)

    update_fields = data.model_dump(exclude_unset=True)

    # Unpack nested notification preferences into flat notify_* columns on the ORM model
    if "notifications" in update_fields:
        notification_prefs = update_fields.pop("notifications")
        if notification_prefs is not None:
            notification_field_map = {
                "budget_exceeded": "notify_budget_exceeded",
                "weekly_summary": "notify_weekly_summary",
                "voice_confirmations": "notify_voice_confirmations",
                "ai_insights": "notify_ai_insights",
            }
            for pref_key, column_name in notification_field_map.items():
                if pref_key in notification_prefs:
                    setattr(settings, column_name, notification_prefs[pref_key])

    for field_name, value in update_fields.items():
        setattr(settings, field_name, value)

    await session.flush()
    await session.refresh(settings)
    return UserSettingsResponse.from_orm_model(settings)
