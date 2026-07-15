from __future__ import annotations

import re
import sqlite3
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, status

from app.auth import create_access_token, hash_password, verify_password
from app.core.database import get_db_connection
from app.schemas import AuthRequest


router = APIRouter(prefix="/auth", tags=["authentication"])


def _validate_username(username: str) -> str:
    username = username.strip()

    if not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]{3,19}", username):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "Username must be 4 to 20 characters, start with a letter, "
                "and contain only letters, numbers, or underscore."
            ),
        )

    return username


def _validate_password(password: str) -> None:
    if len(password) < 8 or len(password) > 128:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password must be 8 to 128 characters long.",
        )

    if not re.search(r"[A-Z]", password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password must contain at least one uppercase letter.",
        )

    if not re.search(r"[a-z]", password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password must contain at least one lowercase letter.",
        )

    if not re.search(r"[0-9]", password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password must contain at least one number.",
        )

    if not re.search(r"[^A-Za-z0-9]", password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password must contain at least one special character.",
        )


@router.post("/register", status_code=status.HTTP_201_CREATED)
def register_user(payload: AuthRequest):
    username = _validate_username(payload.username)
    _validate_password(payload.password)

    try:
        secure_hash = hash_password(payload.password)

        with get_db_connection() as connection:
            connection.execute(
                """
                INSERT INTO users (username, password_hash, created_at)
                VALUES (?, ?, ?)
                """,
                (
                    username,
                    secure_hash,
                    datetime.now(timezone.utc).isoformat(),
                ),
            )
            connection.commit()

    except sqlite3.IntegrityError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This username is already registered. Please login.",
        ) from exc

    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    return {
        "success": True,
        "username": username,
        "message": "Registration successful. Please login.",
    }


@router.post("/login")
def login_user(payload: AuthRequest):
    username = payload.username.strip()

    with get_db_connection() as connection:
        row = connection.execute(
            """
            SELECT username, password_hash
            FROM users
            WHERE username = ?
            """,
            (username,),
        ).fetchone()

    if row is None or not verify_password(
        payload.password,
        row["password_hash"],
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = create_access_token(row["username"])

    return {
        "success": True,
        "access_token": token,
        "token_type": "bearer",
        "username": row["username"],
        "message": "Login successful.",
    }