from pydantic import BaseModel


class VoiceInteractionResponse(BaseModel):
    id: str
    transcript: str
    parsed_result: dict
    status: str
    result_description: str
    expense_id: str | None
    created_at: str

    model_config = {"from_attributes": True}
