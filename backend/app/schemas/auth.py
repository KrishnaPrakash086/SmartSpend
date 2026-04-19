from pydantic import BaseModel, Field

class SignUpRequest(BaseModel):
    username: str = Field(..., min_length=4, max_length=50)
    password: str = Field(..., min_length=6, max_length=128)
    display_name: str = Field(default="", max_length=100)
    preferred_currency: str = Field(default="INR", max_length=10)
    monthly_income: float = Field(default=0, ge=0)
    initial_categories: list[str] = Field(default_factory=lambda: ["Food & Dining", "Transport", "Entertainment", "Bills & Utilities", "Shopping", "Other"])

class SignInRequest(BaseModel):
    username: str
    password: str

class UserResponse(BaseModel):
    id: str
    username: str
    display_name: str
    preferred_currency: str
    monthly_income: float
    is_first_login: bool
    
    model_config = {"from_attributes": True}

class AuthResponse(BaseModel):
    token: str
    user: UserResponse
