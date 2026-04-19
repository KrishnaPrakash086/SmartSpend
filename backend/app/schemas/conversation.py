from pydantic import BaseModel, Field
from typing import Literal


class ConversationMessage(BaseModel):
    role: str
    content: str
    is_guru: bool = False
    source: str = "text"
    timestamp: str | None = None


class ConversationCreate(BaseModel):
    mode: Literal["smartspend", "guru"]
    title: str = Field(default="Untitled", max_length=255)
    messages: list[ConversationMessage]
    summary: str | None = None


class ConversationResponse(BaseModel):
    id: str
    mode: str
    title: str
    messages: list[dict]
    message_count: int
    summary: str | None
    created_at: str
    updated_at: str

    model_config = {"from_attributes": True}
