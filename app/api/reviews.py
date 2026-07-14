from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, status

from app.auth import get_current_username
from app.core.database import get_db_connection
from app.schemas import ReviewRequest


router = APIRouter(tags=["reviews"])


def normalize_review_place_name(value: object) -> str:
    normalized = str(value or "").strip().lower()
    normalized = re.sub(r"\s+", " ", normalized)
    return normalized.replace("’", "'")


def review_summary_for_place(place_name: str) -> dict:
    normalized = normalize_review_place_name(place_name)

    with get_db_connection() as connection:
        rows = connection.execute(
            """
            SELECT id, username, place_name, category, rating, review,
                   visited_date, helpful, created_at
            FROM reviews
            ORDER BY created_at DESC
            """
        ).fetchall()

    reviews = [
        dict(row)
        for row in rows
        if normalize_review_place_name(row["place_name"]) == normalized
    ]

    ratings = [float(item["rating"]) for item in reviews]
    average = round(sum(ratings) / len(ratings), 1) if ratings else 0

    return {
        "average_rating": average,
        "review_count": len(reviews),
        "reviews": reviews[:10],
    }


@router.post("/reviews", status_code=status.HTTP_201_CREATED)
def add_place_review(
    data: ReviewRequest,
    current_username: str = Depends(get_current_username),
):
    place_name = re.sub(r"\s+", " ", data.place_name).strip()
    category = re.sub(r"\s+", " ", data.category).strip()
    review_text = re.sub(r"\s+", " ", data.review).strip()
    visited_date = data.visited_date.strip()

    now = datetime.now(timezone.utc)
    created_at = now.isoformat()
    rate_limit_start = (now - timedelta(minutes=10)).isoformat()

    with get_db_connection() as connection:
        recent_review_count = connection.execute(
            """
            SELECT COUNT(*)
            FROM reviews
            WHERE username = ?
              AND created_at >= ?
            """,
            (current_username, rate_limit_start),
        ).fetchone()[0]

        if recent_review_count >= 5:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Too many reviews submitted. Please try again later.",
            )

        duplicate = connection.execute(
            """
            SELECT id
            FROM reviews
            WHERE username = ?
              AND LOWER(TRIM(place_name)) = LOWER(TRIM(?))
              AND review = ?
              AND created_at >= ?
            LIMIT 1
            """,
            (
                current_username,
                place_name,
                review_text,
                rate_limit_start,
            ),
        ).fetchone()

        if duplicate is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="You recently submitted the same review.",
            )

        cursor = connection.execute(
            """
            INSERT INTO reviews (
                username,
                place_name,
                category,
                rating,
                review,
                visited_date,
                helpful,
                created_at
            ) VALUES (?, ?, ?, ?, ?, ?, 0, ?)
            """,
            (
                current_username,
                place_name,
                category,
                data.rating,
                review_text,
                visited_date,
                created_at,
            ),
        )

        review_id = cursor.lastrowid
        connection.commit()

    new_review = {
        "id": review_id,
        "username": current_username,
        "place_name": place_name,
        "category": category,
        "rating": data.rating,
        "review": review_text,
        "visited_date": visited_date,
        "helpful": 0,
        "created_at": created_at,
    }

    return {
        "success": True,
        "message": "Thank you! Your review has been submitted.",
        "review": new_review,
        "summary": review_summary_for_place(place_name),
    }


@router.get("/reviews")
def get_place_reviews(place_name: str = ""):
    place_name = place_name.strip()

    if not place_name:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="place_name is required.",
        )

    summary = review_summary_for_place(place_name)

    return {
        "success": True,
        "place_name": place_name,
        **summary,
    }


@router.get("/top-rated-places")
def top_rated_places(limit: int = 10):
    safe_limit = max(1, min(limit, 50))

    with get_db_connection() as connection:
        rows = connection.execute(
            """
            SELECT place_name,
                   category,
                   ROUND(AVG(rating), 1) AS average_rating,
                   COUNT(*) AS review_count
            FROM reviews
            GROUP BY LOWER(TRIM(place_name)), category
            ORDER BY average_rating DESC, review_count DESC
            LIMIT ?
            """,
            (safe_limit,),
        ).fetchall()

    return {
        "success": True,
        "places": [dict(row) for row in rows],
    }