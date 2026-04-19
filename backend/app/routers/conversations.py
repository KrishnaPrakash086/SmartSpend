from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from app.dependencies import DatabaseSession
from app.models import Conversation
from app.schemas.conversation import ConversationCreate, ConversationResponse

router = APIRouter(prefix="/conversations", tags=["Conversations"])


def _serialize(conversation: Conversation) -> ConversationResponse:
    return ConversationResponse(
        id=conversation.id,
        mode=conversation.mode,
        title=conversation.title,
        messages=conversation.messages,
        message_count=conversation.message_count,
        summary=conversation.summary,
        created_at=conversation.created_at.isoformat() if conversation.created_at else "",
        updated_at=conversation.updated_at.isoformat() if conversation.updated_at else "",
    )


@router.get("/", response_model=list[ConversationResponse])
async def list_conversations(
    session: DatabaseSession, mode: str | None = None
):
    query = select(Conversation).order_by(Conversation.updated_at.desc())
    if mode and mode.lower() != "all":
        query = query.where(Conversation.mode == mode.lower())
    result = await session.execute(query)
    return [_serialize(c) for c in result.scalars().all()]


@router.post(
    "/", response_model=ConversationResponse, status_code=status.HTTP_201_CREATED
)
async def save_conversation(data: ConversationCreate, session: DatabaseSession):
    messages_as_dicts = [m.model_dump() for m in data.messages]
    # Auto-generate title from first user message if default
    derived_title = data.title
    if derived_title == "Untitled" and messages_as_dicts:
        first_user_message = next(
            (m for m in messages_as_dicts if m.get("role") == "user"),
            None,
        )
        if first_user_message:
            content = first_user_message.get("content", "")[:80]
            derived_title = content if content else "Untitled"

    conversation = Conversation(
        mode=data.mode,
        title=derived_title,
        messages=messages_as_dicts,
        message_count=len(messages_as_dicts),
        summary=data.summary,
    )
    session.add(conversation)
    await session.flush()
    await session.refresh(conversation)
    return _serialize(conversation)


@router.get("/{conversation_id}", response_model=ConversationResponse)
async def get_conversation(conversation_id: str, session: DatabaseSession):
    result = await session.execute(
        select(Conversation).where(Conversation.id == conversation_id)
    )
    conversation = result.scalar_one_or_none()
    if not conversation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found"
        )
    return _serialize(conversation)


@router.delete("/{conversation_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_conversation(conversation_id: str, session: DatabaseSession):
    result = await session.execute(
        select(Conversation).where(Conversation.id == conversation_id)
    )
    conversation = result.scalar_one_or_none()
    if not conversation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found"
        )
    await session.delete(conversation)
    await session.flush()
