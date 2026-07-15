from __future__ import annotations

import json
from datetime import datetime, timezone

from fastapi import APIRouter, Depends

from app.auth import get_current_username
from app.core.database import get_db_connection
from app.schemas import HistoryRequest


router = APIRouter(tags=["history"])


@router.get("/history")
def get_history(
    current_username: str = Depends(get_current_username),
):
    with get_db_connection() as connection:
        row = connection.execute(
            """
            SELECT history_json
            FROM chat_history
            WHERE username = ?
            """,
            (current_username,),
        ).fetchone()

    history = []

    if row is not None:
        try:
            decoded = json.loads(row["history_json"])
            history = decoded if isinstance(decoded, list) else []
        except (json.JSONDecodeError, TypeError):
            history = []

    return {
        "username": current_username,
        "history": history,
    }


@router.post("/history")
def save_history(
    payload: HistoryRequest,
    current_username: str = Depends(get_current_username),
):
    items = [item.model_dump() for item in payload.history]
    updated_at = datetime.now(timezone.utc).isoformat()

    with get_db_connection() as connection:
        connection.execute(
            """
            INSERT INTO chat_history (
                username,
                history_json,
                updated_at
            )
            VALUES (?, ?, ?)
            ON CONFLICT(username) DO UPDATE SET
                history_json = excluded.history_json,
                updated_at = excluded.updated_at
            """,
            (
                current_username,
                json.dumps(items, ensure_ascii=False),
                updated_at,
            ),
        )
        connection.commit()

    return {
        "success": True,
        "username": current_username,
        "saved": len(items),
    }