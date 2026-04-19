# Read-only endpoints for agent activity logs, voice interaction history, and webhook events
from typing import Optional

from fastapi import APIRouter
from sqlalchemy import select

from app.dependencies import DatabaseSession
from app.models import AgentActivity, VoiceInteraction, WebhookEvent
from app.schemas import (
    AgentActivityResponse,
    VoiceInteractionResponse,
    WebhookEventResponse,
)

router = APIRouter(prefix="", tags=["Tracking"])


def _serialize_datetime(dt) -> str:
    return dt.isoformat() if dt else ""


@router.get("/agents", response_model=list[AgentActivityResponse])
async def list_agent_activities(
    session: DatabaseSession, type: Optional[str] = None
):
    query = select(AgentActivity)
    if type and type != "All":
        query = query.where(AgentActivity.agent_type == type)
    query = query.order_by(AgentActivity.created_at.desc())

    result = await session.execute(query)
    activities = result.scalars().all()

    return [
        AgentActivityResponse(
            id=activity.id,
            agent_name=activity.agent_name,
            agent_type=activity.agent_type,
            action=activity.action,
            details=activity.details,
            duration_ms=activity.duration_ms,
            created_at=_serialize_datetime(activity.created_at),
        )
        for activity in activities
    ]


@router.get("/voice", response_model=list[VoiceInteractionResponse])
async def list_voice_interactions(session: DatabaseSession):
    query = select(VoiceInteraction).order_by(
        VoiceInteraction.created_at.desc()
    )
    result = await session.execute(query)
    interactions = result.scalars().all()

    return [
        VoiceInteractionResponse(
            id=interaction.id,
            transcript=interaction.transcript,
            parsed_result=interaction.parsed_result,
            status=interaction.status,
            result_description=interaction.result_description,
            expense_id=interaction.expense_id,
            created_at=_serialize_datetime(interaction.created_at),
        )
        for interaction in interactions
    ]


@router.get("/webhooks", response_model=list[WebhookEventResponse])
async def list_webhook_events(session: DatabaseSession):
    query = select(WebhookEvent).order_by(WebhookEvent.created_at.desc())
    result = await session.execute(query)
    events = result.scalars().all()

    return [
        WebhookEventResponse(
            id=event.id,
            event_type=event.event_type,
            payload=event.payload,
            status=event.status,
            created_at=_serialize_datetime(event.created_at),
        )
        for event in events
    ]
