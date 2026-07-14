from typing import Optional

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    query: str = Field(
        ...,
        min_length=1,
        max_length=5000,
    )
    original_query: Optional[str] = Field(
        default=None,
        max_length=5000,
    )
    language: str = Field(
        default="English",
        max_length=50,
    )
    session_id: Optional[str] = Field(
        default=None,
        max_length=200,
    )