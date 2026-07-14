from datetime import date
from typing import Optional

from pydantic import BaseModel, Field


class ReviewRequest(BaseModel):
    place_name: str = Field(
        ...,
        min_length=1,
        max_length=200,
    )
    category: str = Field(
        ...,
        min_length=1,
        max_length=100,
    )
    rating: int = Field(
        ...,
        ge=1,
        le=5,
    )
    review: str = Field(
        ...,
        min_length=1,
        max_length=2000,
    )
    visited_date: Optional[date] = None


class ReviewHelpfulRequest(BaseModel):
    review_id: int = Field(..., ge=1)