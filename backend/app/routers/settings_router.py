from fastapi import APIRouter
from sqlalchemy import select

from app.dependencies import DatabaseSession, RequiredUserId
from app.models import UserSettings
from app.schemas import UserSettingsResponse, UserSettingsUpdate

router = APIRouter(prefix="/settings", tags=["Settings"])


@router.get("/", response_model=UserSettingsResponse)
async def get_settings(session: DatabaseSession, user_id: RequiredUserId):
    result = await session.execute(
        select(UserSettings).where(UserSettings.user_id == user_id)
    )
    settings = result.scalar_one_or_none()

    if not settings:
        settings = UserSettings(user_id=user_id)
        session.add(settings)
        await session.flush()
        await session.refresh(settings)

    return UserSettingsResponse.from_orm_model(settings)


@router.patch("/", response_model=UserSettingsResponse)
async def update_settings(
    data: UserSettingsUpdate, session: DatabaseSession, user_id: RequiredUserId
):
    result = await session.execute(
        select(UserSettings).where(UserSettings.user_id == user_id)
    )
    settings = result.scalar_one_or_none()

    if not settings:
        settings = UserSettings(user_id=user_id)
        session.add(settings)
        await session.flush()
        await session.refresh(settings)

    update_fields = data.model_dump(exclude_unset=True)

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
