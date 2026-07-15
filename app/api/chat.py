from __future__ import annotations

import inspect
import re
import traceback

from fastapi import APIRouter, HTTPException, status

from app.core.database import (
    load_conversation_state,
    save_conversation_state,
)
from app.schemas import (
    ChatRequest,
    TranslateTextRequest,
)
from app.services.recommendation_service import get_recommendations
from app.services.translation_service import (
    localize_only_plain_messages,
    localize_response,
    normalize_language,
    translate_text_backend,
    translate_to_english_backend,
)

router = APIRouter(tags=["chat"])


def _validate_session_id(session_id: str) -> str:
    session_id = str(session_id or "").strip()
    if not re.fullmatch(r"[A-Za-z0-9._:-]{16,128}", session_id):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                "session_id must be 16 to 128 characters and contain only "
                "letters, numbers, dot, underscore, colon, or hyphen."
            ),
        )
    return session_id


@router.post("/translate_text")
async def translate_text_api(data: TranslateTextRequest):
    language = normalize_language(getattr(data, "language", "English"))
    text = getattr(data, "text", "") or ""
    try:
        return {
            "text": await translate_text_backend(text, language),
            "language": language,
        }
    except Exception:
        traceback.print_exc()
        return {"text": text, "language": language}


@router.post("/chat")
async def chat(data: ChatRequest):
    original_query = (
        getattr(data, "original_query", "")
        or data.query
        or ""
    ).strip()
    query = (data.query or "").strip()
    language = normalize_language(getattr(data, "language", "English"))
    session_id = _validate_session_id(data.session_id)
    state_key = f"session:{session_id}"

    if not query and not original_query:
        return await localize_response(
            {"recommendations": [{"message": "Please enter something 😊"}]},
            language,
        )

    try:
        query_for_backend = query

        if language != "English":
            query_for_backend = await translate_to_english_backend(
                original_query or query
            )

        if query and re.search(r"[A-Za-z]", query):
            query_for_backend = query

        conversation_state = load_conversation_state(state_key)

        parameters = inspect.signature(get_recommendations).parameters
        if "state" in parameters:
            service_result = await get_recommendations(
                query_for_backend,
                language=language,
                state=conversation_state,
            )
        else:
            service_result = await get_recommendations(
                query_for_backend,
                language=language,
            )

        updated_state = conversation_state
        if (
            isinstance(service_result, tuple)
            and len(service_result) == 2
            and isinstance(service_result[1], dict)
        ):
            recommendations, updated_state = service_result
        else:
            recommendations = service_result

        save_conversation_state(state_key, updated_state)

        result = {
            "recommendations": recommendations,
            "language": language,
            "understood_query": query_for_backend,
            "session_id": session_id,
        }

        return await localize_only_plain_messages(result, language)

    except HTTPException:
        raise
    except Exception:
        traceback.print_exc()
        return await localize_response(
            {"recommendations": [{"message": "Server Error 😢"}]},
            language,
        )