from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DB_PATH = Path(__file__).resolve().parent.parent / "tourist_users.db"

DEFAULT_CONVERSATION_STATE: dict[str, Any] = {
    "user_name": "Traveler",
    "last_category": None,
    "last_results": [],
    "last_index": 0,
    "last_place_name": None,
    "last_places_list": [],
    "last_location_context": None,
    "pending_ambiguous_query": None,
    "pending_ambiguous_categories": [],
}


def get_db_connection() -> sqlite3.Connection:
    """Create a configured SQLite connection for one unit of work."""
    connection = sqlite3.connect(DB_PATH, timeout=15)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("PRAGMA busy_timeout = 15000")
    return connection


def init_database() -> None:
    """Create all application tables and indexes when they do not exist."""
    with get_db_connection() as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS chat_history (
                username TEXT PRIMARY KEY,
                history_json TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY (username) REFERENCES users(username) ON DELETE CASCADE
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS reviews (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL,
                place_name TEXT NOT NULL,
                category TEXT NOT NULL DEFAULT '',
                rating INTEGER NOT NULL CHECK (rating BETWEEN 1 AND 5),
                review TEXT NOT NULL,
                visited_date TEXT NOT NULL DEFAULT '',
                helpful INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL,
                FOREIGN KEY (username) REFERENCES users(username) ON DELETE CASCADE
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS conversation_state (
                state_key TEXT PRIMARY KEY,
                state_json TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_reviews_place ON reviews(place_name)"
        )
        connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_reviews_user_created "
            "ON reviews(username, created_at)"
        )
        connection.commit()


def default_conversation_state() -> dict[str, Any]:
    """Return a fresh conversation state without shared mutable lists."""
    return {
        key: list(value) if isinstance(value, list) else value
        for key, value in DEFAULT_CONVERSATION_STATE.items()
    }


def _sanitize_conversation_state(state: Any) -> dict[str, Any]:
    safe_state = default_conversation_state()

    if isinstance(state, dict):
        for key in safe_state:
            if key in state:
                safe_state[key] = state[key]

    if not isinstance(safe_state["last_results"], list):
        safe_state["last_results"] = []
    if not isinstance(safe_state["last_places_list"], list):
        safe_state["last_places_list"] = []
    if not isinstance(safe_state["pending_ambiguous_categories"], list):
        safe_state["pending_ambiguous_categories"] = []

    safe_state["last_results"] = safe_state["last_results"][:100]
    safe_state["last_places_list"] = safe_state["last_places_list"][:100]
    safe_state["pending_ambiguous_categories"] = (
        safe_state["pending_ambiguous_categories"][:20]
    )

    try:
        safe_state["last_index"] = max(0, int(safe_state["last_index"]))
    except (TypeError, ValueError):
        safe_state["last_index"] = 0

    return safe_state


def load_conversation_state(state_key: str) -> dict[str, Any]:
    """Load one session state, returning defaults for missing or invalid rows."""
    with get_db_connection() as connection:
        row = connection.execute(
            "SELECT state_json FROM conversation_state WHERE state_key = ?",
            (state_key,),
        ).fetchone()

    if row is None:
        return default_conversation_state()

    try:
        stored = json.loads(row["state_json"])
    except (TypeError, json.JSONDecodeError):
        return default_conversation_state()

    return _sanitize_conversation_state(stored)


def save_conversation_state(state_key: str, state: Any) -> None:
    """Persist a bounded and JSON-safe conversation state."""
    safe_state = _sanitize_conversation_state(state)
    payload = json.dumps(safe_state, ensure_ascii=False, default=str)

    if len(payload.encode("utf-8")) > 512_000:
        safe_state["last_results"] = []
        payload = json.dumps(safe_state, ensure_ascii=False, default=str)

    with get_db_connection() as connection:
        connection.execute(
            """
            INSERT INTO conversation_state (state_key, state_json, updated_at)
            VALUES (?, ?, ?)
            ON CONFLICT(state_key) DO UPDATE SET
                state_json = excluded.state_json,
                updated_at = excluded.updated_at
            """,
            (
                state_key,
                payload,
                datetime.now(timezone.utc).isoformat(),
            ),
        )
        connection.commit()