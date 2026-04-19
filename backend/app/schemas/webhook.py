from pydantic import BaseModel


class WebhookEventResponse(BaseModel):
    id: str
    event_type: str
    payload: dict
    status: str
    created_at: str

    model_config = {"from_attributes": True}
