from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    email: str = Field(description="Clinic staff email")
    password: str = Field(min_length=1)
    clinic_slug: str | None = Field(
        default=None,
        description=(
            "Optional clinic slug to scope the login to a specific tenant. "
            "Required when the same email is registered in more than one clinic "
            "(otherwise the API refuses to guess and returns 401)."
        ),
    )


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    clinic_id: int
    user_id: int
    role: str


class UserRead(BaseModel):
    model_config = {"from_attributes": True}

    id: int
    clinic_id: int
    email: str
    full_name: str
    role: str
    is_active: bool