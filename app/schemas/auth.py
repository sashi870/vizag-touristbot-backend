from pydantic import BaseModel, Field


class AuthRequest(BaseModel):
    username: str = Field(
        ...,
        min_length=4,
        max_length=20,
    )
    password: str = Field(
        ...,
        min_length=8,
        max_length=128,
    )