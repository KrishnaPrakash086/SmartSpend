from pydantic import BaseModel


class AgentActivityResponse(BaseModel):
    id: str
    agent_name: str
    agent_type: str
    action: str
    details: dict
    duration_ms: int
    created_at: str

    model_config = {"from_attributes": True}
