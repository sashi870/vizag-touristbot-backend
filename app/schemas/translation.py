from pydantic import BaseModel, Field


class TranslateTextRequest(BaseModel):
    text: str = Field(
        ...,
        min_length=1,
        max_length=10000,
    )
    target_language: str = Field(
        ...,
        min_length=2,
        max_length=50,
    )
    source_language: str = Field(
        default="auto",
        min_length=2,
        max_length=50,
    )