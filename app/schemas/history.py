from typing import Literal

from pydantic import BaseModel, Field


class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(
        ...,
        min_length=1,
        max_length=4000,
    )


class HistoryRequest(BaseModel):
    history: list[ChatMessage] = Field(
        default_factory=list,
        max_length=100,
    )