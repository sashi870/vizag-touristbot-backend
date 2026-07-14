from typing import Literal

from pydantic import BaseModel, Field


class HistoryMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(
        ...,
        min_length=1,
        max_length=10000,
    )


class HistoryRequest(BaseModel):
    history: list[HistoryMessage] = Field(
        default_factory=list,
        max_length=200,
    )