from pydantic import BaseModel, Field


class ReviewRequest(BaseModel):
    place_name: str = Field(
        ...,
        min_length=1,
        max_length=200,
    )
    category: str = Field(
        default="",
        max_length=100,
    )
    rating: int = Field(
        ...,
        ge=1,
        le=5,
    )
    review: str = Field(
        ...,
        min_length=2,
        max_length=2000,
    )
    visited_date: str = Field(
        default="",
        max_length=30,
    )


class ReviewHelpfulRequest(BaseModel):
    place_name: str = Field(
        ...,
        min_length=1,
        max_length=200,
    )
    created_at: str = Field(
        default="",
        max_length=50,
    )