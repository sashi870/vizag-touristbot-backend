from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    query: str = Field(
        ...,
        min_length=1,
        max_length=2000,
    )
    original_query: str = Field(
        default="",
        max_length=2000,
    )
    language: str = Field(
        default="English",
        max_length=20,
    )
    session_id: str = Field(
        ...,
        min_length=16,
        max_length=128,
        pattern=r"^[A-Za-z0-9._:-]+$",
    )