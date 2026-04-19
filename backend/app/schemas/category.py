from pydantic import BaseModel, Field


class CategoryCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    color: str = "#64748b"
    icon: str = "MoreHorizontal"


class CategoryResponse(BaseModel):
    id: str
    name: str
    color: str
    icon: str

    model_config = {"from_attributes": True}
