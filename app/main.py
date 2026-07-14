from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse

import pandas as pd
import traceback
import os
import sqlite3
import re
import json
import inspect
from datetime import datetime, timezone

from app.services.recommendation_service import get_recommendations
from app.services.translation_service import (
    localize_only_plain_messages,
    localize_response,
    normalize_language,
    translate_text_backend,
    translate_to_english_backend,
)
from app.auth import (
    create_access_token,
    get_current_username,
    hash_password,
    verify_password,
)

from app.schemas import (
    AuthRequest,
    ChatMessage,
    ChatRequest,
    HistoryRequest,
    TranslateTextRequest,
)

from app.core.database import (
    get_db_connection as _db,
    init_database as _init_database,
    load_conversation_state,
    save_conversation_state,
)

from app.data.csv_loader import (
    fix_single_column_csv_df,
    load_csv,
    load_first_existing_csv,
    safe_get,
)

from app.api.reviews import router as reviews_router

BASE_DIR = os.path.dirname(os.path.abspath(__file__))


# ============================================================
# WALKING FALLBACK / ROUTE TIP
# If walking CSV has no record or blank walking distance/time,
# return a traveller-friendly route tip instead of empty output.
# ============================================================
def _clean_transport_value(value):
    value = "" if value is None else str(value).strip()
    if not value:
        return ""
    bad_values = {
        "nan", "none", "null", "na", "n/a", "not available",
        "notavailable", "-", "--", "_"
    }
    if value.lower().replace(" ", "") in bad_values:
        return ""
    return value


def has_useful_walking_details(item):
    """True only when a walking record has real walking distance/time data.

    Route tips alone are not treated as walking details. This prevents outputs like:
    Distance: Not available km, Walking Time: Not recommended, Steps: N/A.
    """
    if not isinstance(item, dict):
        return False

    distance = _clean_transport_value(
        item.get("walking_distance") or item.get("current_distance_km")
    )
    time = _clean_transport_value(item.get("walking_time"))
    steps = _clean_transport_value(item.get("steps"))
    calories = _clean_transport_value(item.get("calories"))

    bad_time_words = ["not recommended", "notrecommended", "not available", "n/a", "na"]
    if time.lower().replace(" ", "") in bad_time_words:
        time = ""

    bad_distance_words = ["not recommended", "notrecommended", "not available", "n/a", "na"]
    if distance.lower().replace(" ", "") in bad_distance_words:
        distance = ""

    return bool(distance or time or steps or calories)


def build_walking_route_tip(place):
    place_name = str(place or "this destination").strip() or "this destination"
    return {
        "place_type": "route_tip",
        "place_name": place_name,
        "only_route_tip": True,
        "route_tip": (
            "🚶 Route Tip\n\n"
            f"Walking information is currently unavailable for {place_name}.\n\n"
            "Recommended travel options:\n\n"
            "🚌 APSRTC Bus – Budget Friendly\n"
            "🏍️ Rapido Bike – Fast & Affordable\n"
            "🚕 Auto – Convenient\n"
            "🚖 Cab – Comfortable for Families"
        ),
    }

beaches_df = load_csv("beaches.csv")
beach_apsrtc_df = fix_single_column_csv_df(load_first_existing_csv(["beachesapsrtc.csv", "beachesapsrtc(2).csv"]))
beach_walk_df = fix_single_column_csv_df(load_first_existing_csv(["beacheswalk.csv", "beacheswalk(2).csv"]))
beach_rapido_df = fix_single_column_csv_df(load_first_existing_csv(["beachesrapido.csv", "beachesrapido(2).csv"]))

restaurant_apsrtc_df = fix_single_column_csv_df(load_first_existing_csv(["restuarantsapsrtc.csv", "restaurantsapsrtc.csv", "restaurants_apsrtc_buses.csv"]))
restaurant_walk_df = fix_single_column_csv_df(load_first_existing_csv(["restaurants-walk.csv", "restaurants_walk.csv", "restaurants_walking.csv"]))
restaurant_rapido_df = fix_single_column_csv_df(load_first_existing_csv(["restaurants-rapido.csv", "restaurants_rapido.csv"]))

# Cafe transport CSVs were not loaded before. Details/cards worked, but Bus/Walk/Rapido for cafes failed.
cafe_apsrtc_df = fix_single_column_csv_df(load_first_existing_csv(["cafeapsrtcbuses.csv", "cafeapsrtcbuses(2).csv", "cafe_apsrtc_buses.csv"]))
cafe_walk_df = fix_single_column_csv_df(load_first_existing_csv(["cafe_walking.csv", "cafe_walking(2).csv", "cafes_walking.csv"]))
cafe_rapido_df = fix_single_column_csv_df(load_first_existing_csv(["caferapido.csv", "caferapido(2).csv", "cafe_rapido.csv", "cafes_rapido.csv"]))

parks_df = load_csv("parks.csv")
park_apsrtc_df = fix_single_column_csv_df(load_first_existing_csv(["park_apsrtc_buses.csv", "parks_apsrtc_buses.csv"]))
park_walk_df = fix_single_column_csv_df(load_first_existing_csv(["park_walking.csv", "parks_walking.csv"]))
park_rapido_df = fix_single_column_csv_df(load_first_existing_csv(["park_rapido.csv", "parks_rapido.csv"]))

temples_df = load_csv("temples.csv")
temple_apsrtc_df = fix_single_column_csv_df(load_first_existing_csv(["temple_apsrtc_buses.csv", "temples_apsrtc_buses.csv"]))
temple_walk_df = fix_single_column_csv_df(load_first_existing_csv(["temple_walking.csv", "temples_walking.csv"]))
temple_rapido_df = fix_single_column_csv_df(load_first_existing_csv(["temple_rapido.csv", "temples_rapido.csv"]))

museums_df = load_csv("Museum.csv")
museum_apsrtc_df = fix_single_column_csv_df(load_first_existing_csv(["museum_apsrtc_buses.csv", "museums_apsrtc_buses.csv"]))
museum_walk_df = fix_single_column_csv_df(load_first_existing_csv(["museum_walking.csv", "museums_walking.csv"]))
museum_rapido_df = fix_single_column_csv_df(load_first_existing_csv(["museum_rapido.csv", "museums_rapido.csv"]))

hospitals_df = fix_single_column_csv_df(load_csv("hospitals.csv"))
hospital_apsrtc_df = fix_single_column_csv_df(load_first_existing_csv(["hospital_apsrtc_buses.csv", "hospital_apsrtc_buses(1).csv", "hospitals_apsrtc_buses.csv"]))
hospital_walk_df = fix_single_column_csv_df(load_first_existing_csv(["hospital_walking.csv", "hospital_walking(1).csv", "hospitals_walking.csv"]))
hospital_rapido_df = fix_single_column_csv_df(load_first_existing_csv(["hospital_rapido.csv", "hospital_rapido(1).csv", "hospitals_rapido.csv"]))

theaters_df = fix_single_column_csv_df(load_csv("theaters.csv"))
theater_apsrtc_df = fix_single_column_csv_df(load_first_existing_csv(["theater_apsrtc_buses.csv", "theater_apsrtc_buses .csv", "theaters_apsrtc_buses.csv"]))
theater_walk_df = fix_single_column_csv_df(load_first_existing_csv(["theater_walking.csv", "theaters_walking.csv"]))
theater_rapido_df = fix_single_column_csv_df(load_first_existing_csv(["theater_rapido.csv", "theaters_rapido.csv"]))

pubs_df = fix_single_column_csv_df(load_csv("pubs.csv"))
pub_apsrtc_df = fix_single_column_csv_df(load_first_existing_csv(["pubs_apsrtc_buses.csv", "pubs_apsrtc_buses(2).csv"]))
pub_walk_df = fix_single_column_csv_df(load_first_existing_csv(["pubs_walking.csv", "pubs_walking(1).csv"]))
pub_rapido_df = fix_single_column_csv_df(load_first_existing_csv(["pubs_rapido.csv", "pubs_rapido(2).csv"]))


# ============================================================
# SPECIALITY / BUDGET CSV FILES FOR DETAILS BUTTON
# Put these files inside: backend/app/datasets/
# Supported names are included so your uploaded filenames also work.
# ============================================================

speciality_files = {
    "beach": load_first_existing_csv([
        "beaches_speciality_budget.csv",
        "cleaned_vizag_beaches_combined(1).csv",
        "cleaned_vizag_beaches_combined.csv"
    ]),
    "restaurant": load_first_existing_csv([
        "restaurants_speciality_budget.csv"
    ]),
    "cafe": load_first_existing_csv([
        "cafes_speciality_budget.csv"
    ]),
    "temple": load_first_existing_csv([
        "temples_speciality_budget.csv",
        "temples_speciality_budget(1).csv"
    ]),
    "theater": load_first_existing_csv([
        "theaters_speciality_budget.csv",
        "theaters_speciality_budget(1).csv"
    ]),
    "park": load_first_existing_csv([
        "parks_speciality_budget.csv",
        "park_speciality_budget.csv",
        "aaa26e15-8b64-463e-8531-cd3bc8b0e8a1.csv"
    ]),
    "museum": load_first_existing_csv([
        "museum_speciality_budget.csv",
        "museums_speciality_budget.csv"
    ]),
    "hospital": load_first_existing_csv([
        "hospital_speciality_budget.csv",
        "hospitals_speciality_budget.csv",
        "8d178e25-97a8-465e-b947-8fcc530ff08d.csv"
    ]),
}



app = FastAPI(title="Vizag AI Travel Assistant")
app.include_router(reviews_router)




_init_database()


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


def _validate_username(username: str) -> str:
    username = username.strip()
    if not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]{3,19}", username):
        raise HTTPException(
            status_code=400,
            detail="Username must be 4 to 20 characters, start with a letter, and contain only letters, numbers, or underscore.",
        )
    return username


def _validate_password(password: str) -> None:
    if len(password) < 8 or len(password) > 128:
        raise HTTPException(status_code=400, detail="Password must be 8 to 128 characters long.")
    if not re.search(r"[A-Z]", password):
        raise HTTPException(status_code=400, detail="Password must contain at least one uppercase letter.")
    if not re.search(r"[a-z]", password):
        raise HTTPException(status_code=400, detail="Password must contain at least one lowercase letter.")
    if not re.search(r"[0-9]", password):
        raise HTTPException(status_code=400, detail="Password must contain at least one number.")
    if not re.search(r"[^A-Za-z0-9]", password):
        raise HTTPException(status_code=400, detail="Password must contain at least one special character.")


@app.middleware("http")
async def limit_request_size(request: Request, call_next):
    content_length = request.headers.get("content-length")

    if content_length is not None:
        try:
            request_size = int(content_length)
        except ValueError:
            return JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                content={"detail": "Invalid Content-Length header."},
            )

        if request_size < 0:
            return JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                content={"detail": "Invalid Content-Length header."},
            )

        if request_size > 1_048_576:
            return JSONResponse(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                content={"detail": "Request body exceeds the 1 MB limit."},
            )

    return await call_next(request)


@app.post("/auth/register", status_code=status.HTTP_201_CREATED)
def register_user(payload: AuthRequest):
    username = _validate_username(payload.username)
    _validate_password(payload.password)
    try:
        secure_hash = hash_password(payload.password)
        with _db() as conn:
            conn.execute(
                "INSERT INTO users (username, password_hash, created_at) VALUES (?, ?, ?)",
                (username, secure_hash, datetime.now(timezone.utc).isoformat()),
            )
            conn.commit()
    except sqlite3.IntegrityError as exc:
        raise HTTPException(status_code=409, detail="This username is already registered. Please login.") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"success": True, "username": username, "message": "Registration successful. Please login."}


@app.post("/auth/login")
def login_user(payload: AuthRequest):
    username = payload.username.strip()
    with _db() as conn:
        row = conn.execute(
            "SELECT username, password_hash FROM users WHERE username = ?",
            (username,),
        ).fetchone()
    if row is None or not verify_password(payload.password, row["password_hash"]):
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


@app.get("/history")
def get_history(current_username: str = Depends(get_current_username)):
    with _db() as conn:
        row = conn.execute(
            "SELECT history_json FROM chat_history WHERE username = ?",
            (current_username,),
        ).fetchone()
    history = []
    if row is not None:
        try:
            decoded = json.loads(row["history_json"])
            history = decoded if isinstance(decoded, list) else []
        except json.JSONDecodeError:
            history = []
    return {"username": current_username, "history": history}


@app.post("/history")
def save_history(payload: HistoryRequest, current_username: str = Depends(get_current_username)):
    items = [item.model_dump() for item in payload.history]
    with _db() as conn:
        conn.execute(
            """
            INSERT INTO chat_history (username, history_json, updated_at)
            VALUES (?, ?, ?)
            ON CONFLICT(username) DO UPDATE SET
                history_json = excluded.history_json,
                updated_at = excluded.updated_at
            """,
            (current_username, json.dumps(items, ensure_ascii=False), datetime.now(timezone.utc).isoformat()),
        )
        conn.commit()
    return {"success": True, "username": current_username, "saved": len(items)}


allowed_origins = [
    value.strip()
    for value in os.getenv(
        "ALLOWED_ORIGINS",
        "http://localhost:3000,http://localhost:5173,http://localhost:8080",
    ).split(",")
    if value.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "Accept"],
)

FRONTEND_DIR = os.path.abspath(os.path.join(BASE_DIR, "../../frontend"))
# Mount frontend static files only when the frontend folder exists.
# This prevents backend startup errors during Render/API-only deployment.
if os.path.isdir(FRONTEND_DIR):
    app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")


# Conversation voice mode is handled by frontend; backend continues to process each spoken query normally.






@app.get("/")
async def serve_frontend():
    index_path = os.path.join(FRONTEND_DIR, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return {"message": "Vizag AI Travel Assistant backend is running", "docs": "/docs"}


@app.post("/translate_text")
async def translate_text_api(data: TranslateTextRequest):
    language = normalize_language(getattr(data, "language", "English"))
    text = getattr(data, "text", "") or ""
    try:
        return {"text": await translate_text_backend(text, language), "language": language}
    except Exception:
        traceback.print_exc()
        return {"text": text, "language": language}


@app.post("/chat")
async def chat(data: ChatRequest):
    original_query = (getattr(data, "original_query", "") or data.query or "").strip()
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
            query_for_backend = await translate_to_english_backend(original_query or query)

        if query and re.search(r"[A-Za-z]", query):
            query_for_backend = query

        conversation_state = load_conversation_state(state_key)

        # Backward-compatible bridge:
        # - current recommendation_service.py continues to run until it is updated;
        # - the secure version should accept `state=` and return
        #   `(recommendations, updated_state)`.
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


def clean_name(text):
    return (
        str(text)
        .lower()
        .replace("beach", "")
        .replace("restaurant", "")
        .replace("restaurants", "")
        .replace("park", "")
        .replace("parks", "")
        .replace("garden", "")
        .replace("temple", "")
        .replace("temples", "")
        .replace("mandir", "")
        .replace("museum", "")
        .replace("museums", "")
        .replace("hospital", "")
        .replace("hospitals", "")
        .replace("pub", "")
        .replace("pubs", "")
        .replace("bar", "")
        .replace("bars", "")
        .replace("club", "")
        .replace("clubs", "")
        .replace("lounge", "")
        .replace("nightlife", "")
        .replace("brewery", "")
        .replace("restobar", "")
        .replace("resto", "")
        .replace("nightclub", "")
        .replace("cafe", "")
        .replace("kitchen", "")
        .replace("vizag", "")
        .replace("visakhapatnam", "")
        .replace("clinic", "")
        # Keep "medical" for places like "Medical Centre IIM Visakhapatnam"
        .replace("healthcare", "")
        .replace("centre", "center")
        .replace("theater", "")
        .replace("theaters", "")
        .replace("theatre", "")
        .replace("theatres", "")
        .replace("cinema", "")
        .replace("cinemas", "")
        .replace("movie", "")
        .replace("movies", "")
        .replace("multiplex", "")
        .replace("inox", "")
        .replace("pvr", "")
        .replace("aquarium", "")
        .replace("memorial", "")
        .replace("bar", "")
        .replace("(rk)", "")
        .replace("rk", "ramakrishna")
        .replace("&", "and")
        .replace("'", "")
        .replace('"', "")
        .replace(",", "")
        .replace(".", "")
        .replace("-", "")
        .replace("_", "")
        .replace(" ", "")
        .strip()
    )


def strict_match(place, value):
    place_key = clean_name(place)
    value_key = clean_name(value)

    if not place_key or not value_key:
        return False

    return place_key == value_key or place_key in value_key or value_key in place_key


# Strict matching only for Details/Speciality CSVs.
# Do NOT use the loose strict_match() here, because it can wrongly match:
# "Hanuman Temple" -> "Noodles Hanumanthu"
# "G1 Hospitals" -> "G"
def normalize_detail_text(text):
    value = str(text or "").lower()
    value = value.replace("&", " and ")
    value = value.replace("(rk)", " ramakrishna ")
    value = re.sub(r"\brk\b", "ramakrishna", value)
    value = value.replace("centre", "center")
    value = value.replace("visakhapatnam", "vizag")
    value = re.sub(r"[^a-z0-9]+", " ", value)
    value = re.sub(r"\s+", " ", value).strip()
    return value


def detail_tokens(text):
    stop_words = {
        "the", "and", "in", "at", "near", "opp", "opposite",
        "vizag", "visakhapatnam", "andhra", "pradesh"
    }
    tokens = normalize_detail_text(text).split()
    return [token for token in tokens if token and token not in stop_words]


def detect_detail_place_types(place):
    q = normalize_detail_text(place)

    if any(word in q.split() for word in ["hospital", "hospitals", "clinic", "clinics", "medical", "healthcare", "dispensary", "pharmacy", "center"]):
        return ["hospital"]

    if any(word in q.split() for word in ["temple", "temples", "mandir", "devasthanam"]):
        return ["temple"]

    if any(word in q.split() for word in ["beach", "beaches"]):
        return ["beach"]

    if any(word in q.split() for word in ["park", "parks", "garden"]):
        return ["park"]

    if any(word in q.split() for word in ["museum", "museums", "aquarium", "memorial"]):
        return ["museum"]

    if any(word in q.split() for word in ["theater", "theatre", "cinema", "multiplex", "pvr", "inox"]):
        return ["theater"]

    if any(word in q.split() for word in ["cafe", "coffee", "bakery"]):
        return ["cafe"]

    if any(word in q.split() for word in ["pub", "bar", "club", "lounge", "restobar", "brewery"]):
        return ["pub"]

    if any(word in q.split() for word in ["restaurant", "food", "biryani", "dhaba", "kitchen", "meals"]):
        return ["restaurant"]

    return []


def speciality_match(place, row_name, aliases=""):
    place_norm = normalize_detail_text(place)
    row_norm = normalize_detail_text(row_name)
    alias_norm = normalize_detail_text(aliases)

    if not place_norm or not row_norm:
        return False

    if place_norm == row_norm or (alias_norm and place_norm == alias_norm):
        return True

    # Compare meaningful tokens instead of raw substring.
    # This prevents "hanuman" matching "hanumanthu" and "g1" matching "g".
    place_tokens = detail_tokens(place)
    row_tokens = detail_tokens(row_name)
    alias_tokens = detail_tokens(aliases)

    if not place_tokens or not row_tokens:
        return False

    place_set = set(place_tokens)
    row_set = set(row_tokens)
    alias_set = set(alias_tokens)

    if place_set and place_set.issubset(row_set):
        return True

    if alias_set and place_set.issubset(alias_set):
        return True

    # Allow row name subset only when it has enough useful tokens.
    # Avoid row "G" matching "G1 Hospitals".
    if len(row_tokens) >= 2 and row_set.issubset(place_set):
        return True

    # Fuzzy containment only for long normalized names.
    shorter, longer = sorted([place_norm, row_norm], key=len)
    if len(shorter) >= 12 and shorter in longer:
        return True

    return False


def get_beach_name(row):
    return safe_get(row, ["Beach Name", "To (Beach)", "beach_name", "to_beach", "name", "Name"])


def get_beach_alias(row):
    return safe_get(row, ["Beach Alias", "beach_alias", "alias", "aliases"])


def get_restaurant_name(row):
    return safe_get(row, ["restaurant_name", "Restaurant Name", "restaurant", "Restaurant", "name", "Name", "title"])


def get_park_name(row):
    return safe_get(row, ["park_name", "Park Name", "park", "Park", "name", "Name", "title", "place_name", "Place Name"])


def get_temple_name(row):
    return safe_get(row, ["temple_name", "Temple Name", "title", "Title", "name", "Name", "place_name", "Place Name"])


def get_museum_name(row):
    return safe_get(row, ["museum_name", "Museum Name", "title", "Title", "name", "Name", "place_name", "Place Name"])



def get_cafe_name(row):
    return safe_get(row, [
        "cafe_name",
        "Cafe Name",
        "cafe",
        "Cafe",
        "title",
        "Title",
        "name",
        "Name",
        "place_name",
        "Place Name"
    ])


def is_cafe_query(place):
    for df in [cafe_apsrtc_df, cafe_walk_df, cafe_rapido_df]:
        if df.empty:
            continue

        for _, row in df.iterrows():
            if strict_match(place, get_cafe_name(row)):
                return True

    place_lower = str(place).lower()
    return (
        "cafe" in place_lower
        or "cafes" in place_lower
        or "coffee" in place_lower
        or "bakery" in place_lower
    )




def get_hospital_name(row):
    return safe_get(row, [
        "hospital_name",
        "Hospital Name",
        "hospital",
        "Hospital",
        "medical_centre_name",
        "Medical Centre Name",
        "medical_center_name",
        "Medical Center Name",
        "health_centre_name",
        "Health Centre Name",
        "destination_name",
        "Destination Name",
        "to_place",
        "To Place",
        "place",
        "Place",
        "title",
        "Title",
        "name",
        "Name",
        "place_name",
        "Place Name"
    ])


def is_hospital_query(place):
    for df in [hospitals_df, hospital_apsrtc_df, hospital_walk_df, hospital_rapido_df]:
        if df.empty:
            continue

        for _, row in df.iterrows():
            if strict_match(place, get_hospital_name(row)):
                return True

    place_lower = str(place).lower()

    return (
        "hospital" in place_lower
        or "hospitals" in place_lower
        or "clinic" in place_lower
        or "clinics" in place_lower
        or "medical" in place_lower
        or "medical centre" in place_lower
        or "medical center" in place_lower
        or "healthcare" in place_lower
        or "health centre" in place_lower
        or "health center" in place_lower
        or "dispensary" in place_lower
        or "pharmacy" in place_lower
    )




def get_theater_name(row):
    return safe_get(row, [
        "theatreName",
        "theater_name",
        "theatre_name",
        "Theater Name",
        "Theatre Name",
        "theater",
        "theatre",
        "title",
        "Title",
        "name",
        "Name",
        "place_name",
        "Place Name"
    ])


def is_theater_query(place):
    for df in [theaters_df, theater_apsrtc_df, theater_walk_df, theater_rapido_df]:
        if df.empty:
            continue

        for _, row in df.iterrows():
            if strict_match(place, get_theater_name(row)):
                return True

    place_lower = str(place).lower()

    return (
        "theater" in place_lower
        or "theaters" in place_lower
        or "theatre" in place_lower
        or "theatres" in place_lower
        or "cinema" in place_lower
        or "cinemas" in place_lower
        or "movie" in place_lower
        or "movies" in place_lower
        or "multiplex" in place_lower
        or "inox" in place_lower
        or "pvr" in place_lower
    )


def is_beach_query(place):
    for df in [beaches_df, beach_apsrtc_df, beach_walk_df, beach_rapido_df]:
        if df.empty:
            continue
        for _, row in df.iterrows():
            if strict_match(place, get_beach_name(row)) or strict_match(place, get_beach_alias(row)):
                return True
    return "beach" in str(place).lower()


def is_restaurant_query(place):
    place_lower = str(place).lower()
    if any(word in place_lower for word in [
        "pub", "bar", "club", "lounge", "nightclub", "restobar", "brewery", "cafe", "coffee", "bakery"
    ]):
        return False

    for df in [restaurant_apsrtc_df, restaurant_walk_df, restaurant_rapido_df]:
        if df.empty:
            continue
        for _, row in df.iterrows():
            if strict_match(place, get_restaurant_name(row)):
                return True
    return False


def is_park_query(place):
    for df in [parks_df, park_apsrtc_df, park_walk_df, park_rapido_df]:
        if df.empty:
            continue
        for _, row in df.iterrows():
            if strict_match(place, get_park_name(row)):
                return True
    return "park" in str(place).lower()


def is_temple_query(place):
    for df in [temples_df, temple_apsrtc_df, temple_walk_df, temple_rapido_df]:
        if df.empty:
            continue
        for _, row in df.iterrows():
            if strict_match(place, get_temple_name(row)):
                return True
    return "temple" in str(place).lower() or "mandir" in str(place).lower()


def is_museum_query(place):
    for df in [museums_df, museum_apsrtc_df, museum_walk_df, museum_rapido_df]:
        if df.empty:
            continue
        for _, row in df.iterrows():
            if strict_match(place, get_museum_name(row)):
                return True

    place_lower = str(place).lower()
    return "museum" in place_lower or "aquarium" in place_lower or "memorial" in place_lower

def get_pub_name(row):
    return safe_get(row, [
        "pub_name",
        "Pub Name",
        "title",
        "Title",
        "name",
        "Name",
        "place_name",
        "Place Name"
    ])


def is_pub_query(place):
    for df in [pubs_df, pub_apsrtc_df, pub_walk_df, pub_rapido_df]:
        if df.empty:
            continue

        for _, row in df.iterrows():
            if strict_match(place, get_pub_name(row)):
                return True

    place_lower = str(place).lower()
    return (
        "pub" in place_lower
        or "pubs" in place_lower
        or "bar" in place_lower
        or "bars" in place_lower
        or "club" in place_lower
        or "clubs" in place_lower
        or "lounge" in place_lower
        or "nightclub" in place_lower
        or "nightlife" in place_lower
        or "restobar" in place_lower
        or "brewery" in place_lower
    )




# ============================================================
# DETAILS BUTTON SPECIALITY MATCHING
# ============================================================

def get_speciality_place_name(row):
    return safe_get(row, [
        "beach_name", "Beach Name",
        "Restaurant Name", "restaurant_name",
        "Cafe Name", "cafe_name",
        "Temple Name", "temple_name",
        "Park Name", "park_name",
        "Museum Name", "museum_name",
        "Hospital_Name", "Hospital Name", "hospital_name", "medical_centre_name", "Medical Centre Name",
        "Theater Name", "Theatre Name", "theater_name", "theatre_name", "theatreName", "theaterName",
        "name", "Name", "title", "Title", "place_name", "Place Name"
    ])


def get_speciality_aliases(row):
    return safe_get(row, [
        "aliases", "Aliases", "alias", "Alias",
        "Beach Alias", "beach_alias"
    ])


def clean_detail_value(value):
    value = "" if value is None else str(value).strip()
    if not value or value.lower() == "nan":
        return ""
    value = value.replace("â‚¹", "₹").replace("â€“", "–").replace("â€”", "—")
    value = re.sub(r"\s+", " ", value).strip()
    return value


def first_value(row, keys, default=""):
    return clean_detail_value(safe_get(row, keys, default))


def clean_detail_label(label):
    """Remove emojis/symbols from detail labels so Help Desk details look clean."""
    label = "" if label is None else str(label).strip()
    # Remove common emoji/symbol prefixes without changing the actual text.
    label = re.sub(r"^[^A-Za-z0-9]+\s*", "", label).strip()
    return label


def add_detail_line(lines, label, value):
    value = clean_detail_value(value)
    label = clean_detail_label(label)
    if value and label:
        lines.append(f"{label}: {value}")


def build_speciality_details(place_type, row, matched_rows=None):
    matched_rows = matched_rows or [row]

    place_name = get_speciality_place_name(row)

    speciality = first_value(row, [
        "Speciality", "speciality", "Specialty", "specialty", "beach_speciality",
        "Famous For", "famous_for"
    ], "No specialities found")

    category = first_value(row, [
        "Category", "category", "categories", "categories/0"
    ])

    description = first_value(row, [
        "description", "Description", "about", "About"
    ])

    address = first_value(row, [
        "Address", "address", "street", "Street", "Area", "area", "location", "Location"
    ])

    city = first_value(row, ["City", "city"])

    budget = first_value(row, [
        "Expected Budget Range",
        "Expected Budget (per person)",
        "Expected Budget (per person / family)",
        "expected_budget",
        "Expected Budget",
        "price_range_inr",
        "Ticket Price Range",
        "Budget",
        "Expected_Budget_INR_Lakhs",
        "Expected Budget INR Lakhs"
    ])

    if not budget:
        budget_min = first_value(row, ["Budget Min (INR)", "budget_min"])
        budget_max = first_value(row, ["Budget Max (INR)", "budget_max"])
        if budget_min and budget_max:
            budget = f"₹{budget_min} - ₹{budget_max}"

    opening_time = first_value(row, ["Opening Time", "openingTime", "opening_time"])
    closing_time = first_value(row, ["Closing Time", "closingTime", "closing_time"])
    timings = first_value(row, ["opening_hours", "Opening Hours", "Timings", "timings"])
    if not timings and (opening_time or closing_time):
        timings = f"{opening_time} - {closing_time}".strip(" -")

    best_time = first_value(row, ["Best Time to Visit", "best_time_to_visit", "Best Time"])

    lines = []
    add_detail_line(lines, "Speciality", speciality)
    add_detail_line(lines, "Category", category)
    add_detail_line(lines, "Description", description)
    add_detail_line(lines, "Location", ", ".join([x for x in [address, city] if x]))
    add_detail_line(lines, "Expected Budget", budget)
    add_detail_line(lines, "Timings", timings)
    add_detail_line(lines, "Best Time", best_time)

    # Category specific useful fields
    if place_type == "beach":
        add_detail_line(lines, "Item to Purchase", first_value(row, ["item_to_purchase"]))
        add_detail_line(lines, "Where to Buy", first_value(row, ["where_to_buy"]))
        add_detail_line(lines, "Water Sports", first_value(row, ["water_sports_available"]))
        add_detail_line(lines, "Food Available", first_value(row, ["food_available"]))
        add_detail_line(lines, "Family Friendly", first_value(row, ["family_friendly"]))
        add_detail_line(lines, "Safety Level", first_value(row, ["safety_level"]))
        add_detail_line(lines, "Crowd Level", first_value(row, ["crowd_level"]))

        # Beaches file can have multiple rows for same beach purchase items.
        purchase_items = []
        for match_row in matched_rows:
            item = first_value(match_row, ["item_to_purchase"])
            price = first_value(match_row, ["price_range_inr"])
            if item:
                purchase_items.append(f"{item}" + (f" ({price})" if price else ""))
        if purchase_items:
            unique_items = []
            for item in purchase_items:
                if item not in unique_items:
                    unique_items.append(item)
            add_detail_line(lines, "Local Items", "; ".join(unique_items[:6]))

    elif place_type == "restaurant":
        add_detail_line(lines, "Best For", first_value(row, ["Best For", "bestFor", "best_for"]))
        add_detail_line(lines, "Reviews", first_value(row, ["Reviews Count", "reviews_count"]))

    elif place_type == "cafe":
        add_detail_line(lines, "Best For", first_value(row, ["Best For", "bestFor", "best_for"]))
        add_detail_line(lines, "Reviews", first_value(row, ["Reviews Count", "reviews_count"]))

    elif place_type == "temple":
        add_detail_line(lines, "Main Deity", first_value(row, ["Main Deity", "mainDeity", "mainGod", "Main God"]))
        add_detail_line(lines, "Darshan Fee", first_value(row, ["Darshan Fee", "darshanFee"]))
        add_detail_line(lines, "Special Darshan / Archana Fee", first_value(row, ["Special Darshan / Archana Fee", "Special Darshan", "specialDarshanFee"]))
        add_detail_line(lines, "Festivals", first_value(row, ["Festivals Celebrated", "festivals"]))
        add_detail_line(lines, "Dress Code", first_value(row, ["Dress Code", "dressCode"]))
        add_detail_line(lines, "Parking", first_value(row, ["Parking", "parking"]))
        add_detail_line(lines, "Photography", first_value(row, ["Photography Allowed", "photography_allowed"]))
        add_detail_line(lines, "Nearby Attractions", first_value(row, ["Nearby Attractions", "nearbyAttractions"]))

    elif place_type == "theater":
        add_detail_line(lines, "Screen Type", first_value(row, ["Screen Type", "screenType"]))
        add_detail_line(lines, "Audio System", first_value(row, ["Audio System", "audioSystem"]))
        add_detail_line(lines, "Ticket Price", first_value(row, ["Ticket Price Range", "ticketPriceRange"]))
        add_detail_line(lines, "Average Food Cost", first_value(row, ["Average Food Cost"]))
        add_detail_line(lines, "Food Availability", first_value(row, ["Food Availability"]))
        add_detail_line(lines, "Famous Food", first_value(row, ["Famous Food Items"]))
        add_detail_line(lines, "Best For", first_value(row, ["Best For", "bestFor"]))
        add_detail_line(lines, "Seating Type", first_value(row, ["Seating Type"]))
        add_detail_line(lines, "Parking", first_value(row, ["Parking"]))
        add_detail_line(lines, "Online Booking", first_value(row, ["Online Booking"]))
        add_detail_line(lines, "Crowd Level", first_value(row, ["Crowd Level"]))
        add_detail_line(lines, "Nearby Attractions", first_value(row, ["Nearby Attractions"]))

    elif place_type == "park":
        add_detail_line(lines, "Best For", first_value(row, ["Best For", "bestFor", "best_for"]))
        add_detail_line(lines, "Ticket Price", first_value(row, ["Ticket Price Range", "ticketPriceRange", "entryFee", "Entry Fee"]))
        add_detail_line(lines, "Average Food Cost", first_value(row, ["Average Food Cost"]))
        add_detail_line(lines, "Food Availability", first_value(row, ["Food Availability"]))
        add_detail_line(lines, "Famous Food", first_value(row, ["Famous Food Items"]))
        add_detail_line(lines, "Crowd Level", first_value(row, ["Crowd Level", "crowdLevel"]))

    elif place_type == "museum":
        add_detail_line(lines, "Best For", first_value(row, ["Best For", "bestFor", "best_for"]))
        add_detail_line(lines, "Ticket Price", first_value(row, ["Ticket Price Range", "ticketPriceRange", "entryFee", "Entry Fee"]))
        add_detail_line(lines, "Average Food Cost", first_value(row, ["Average Food Cost"]))
        add_detail_line(lines, "Food Availability", first_value(row, ["Food Availability"]))
        add_detail_line(lines, "Famous Food", first_value(row, ["Famous Food Items"]))
        add_detail_line(lines, "Crowd Level", first_value(row, ["Crowd Level", "crowdLevel"]))

    elif place_type == "hospital":
        # Hospital speciality file columns:
        # Hospital_Name, City, State, Specialty, Expected_Budget_INR_Lakhs
        hospital_specialty = first_value(row, ["Specialty", "specialty", "Speciality", "speciality"])
        hospital_budget = first_value(row, ["Expected_Budget_INR_Lakhs", "Expected Budget INR Lakhs", "Expected Budget", "expected_budget"])
        hospital_city = first_value(row, ["City", "city"])
        hospital_state = first_value(row, ["State", "state"])

        add_detail_line(lines, "Specialty", hospital_specialty)
        if hospital_budget:
            if "lakh" in hospital_budget.lower() or "₹" in hospital_budget or "rs" in hospital_budget.lower():
                add_detail_line(lines, "Expected Budget", hospital_budget)
            else:
                add_detail_line(lines, "Expected Budget", f"₹{hospital_budget} Lakhs")
        add_detail_line(lines, "City", hospital_city)
        add_detail_line(lines, "State", hospital_state)

    details = "\n\n".join(lines) if lines else "No specialities found."

    specialities = []
    for value in [speciality, budget, category, best_time]:
        value = clean_detail_value(value)
        if value and value not in specialities:
            specialities.append(value)

    rating = first_value(row, ["Rating", "rating", "totalScore", "score"], "N/A")

    map_url = first_value(row, [
        "google_maps_url", "googleMapsUrl", "map_url", "url", "URL"
    ])
    if not map_url:
        map_url = f"https://www.google.com/maps/search/{place_name.replace(' ', '+')}"

    return {
        "name": place_name,
        "rating": rating,
        "details": details,
        "map_url": map_url,
        "specialities": specialities,
    }


def get_speciality_details(place):
    """Search uploaded speciality CSVs by place name.
    Uses strict category-aware matching to avoid mixing wrong details.
    Example fixed:
    - Hanuman Temple will not match Noodles Hanumanthu.
    - G1 Hospitals will not match a restaurant row named G.
    """
    place = "" if place is None else str(place).strip()

    if not place:
        return {
            "name": "",
            "rating": "N/A",
            "details": "No specialities found.",
            "map_url": "#",
            "specialities": [],
        }

    preferred_types = detect_detail_place_types(place)

    if preferred_types:
        search_order = preferred_types
    else:
        search_order = list(speciality_files.keys())

    for place_type in search_order:
        df = speciality_files.get(place_type)

        if df is None or df.empty:
            continue

        df = fix_single_column_csv_df(df)
        matched_rows = []

        for _, row in df.iterrows():
            row_name = get_speciality_place_name(row)
            aliases = get_speciality_aliases(row)

            if not row_name:
                continue

            if speciality_match(place, row_name, aliases):
                matched_rows.append(row)

        if matched_rows:
            return build_speciality_details(place_type, matched_rows[0], matched_rows)

    return {
        "name": place.title(),
        "rating": "N/A",
        "details": "No specialities found.",
        "map_url": "#",
        "specialities": [],
    }


@app.get("/details")
async def details_endpoint(place: str, category: str = "", language: str = "English"):
    """Details button API used by Flutter.
    Reads the speciality/budget CSVs from backend/app/datasets and returns clean details.
    The category parameter is accepted for Flutter compatibility.
    """
    try:
        speciality_result = get_speciality_details(place)
        return await localize_response(speciality_result, language)
    except Exception as e:
        traceback.print_exc()
        return await localize_response({
            "name": place,
            "rating": "N/A",
            "details": "Server error while loading details.",
            "map_url": "#",
            "specialities": [],
            "error": str(e),
        }, language)


@app.get("/help")
async def help_desk(place: str, language: str = "English"):
    try:
        # Details button now uses uploaded speciality/budget CSV files first.
        # If a place is not found in those CSVs, return "No specialities found".
        speciality_result = get_speciality_details(place)
        return await localize_response(speciality_result, language)

        for _, row in beaches_df.iterrows():
            beach_name = get_beach_name(row)

            if not strict_match(place, beach_name):
                continue

            speciality = safe_get(row, ["Speciality", "speciality"])
            unique_feature = safe_get(row, ["Unique Feature", "unique_feature"])
            beach_type = safe_get(row, ["Type", "type"])
            famous_for = safe_get(row, ["Famous For", "famous_for"])
            ideal_for = safe_get(row, ["Ideal For", "ideal_for"])
            activities = safe_get(row, ["Activities", "activities"])
            nearest_landmark = safe_get(row, ["Nearest Landmark", "nearest_landmark"])
            best_season = safe_get(row, ["Best Season", "best_season"])
            crowd_level = safe_get(row, ["Crowd Level", "crowd_level"])

            details = f"""
🏖 Speciality: {speciality}

⭐ Unique Feature: {unique_feature}

🌊 Type: {beach_type}

🔥 Famous For: {famous_for}

🎯 Ideal For: {ideal_for}

🎡 Activities: {activities}

☀ Best Season: {best_season}

👥 Crowd Level: {crowd_level}

📍 Nearest Landmark: {nearest_landmark}
"""

            return await localize_response({
                "name": beach_name,
                "rating": safe_get(row, ["rating", "Rating"], "4.5"),
                "details": details,
                "map_url": f"https://www.google.com/maps/search/{beach_name.replace(' ', '+')}",
                "specialities": [speciality, famous_for, activities],
            }, language)

        for _, row in parks_df.iterrows():
            park_name = get_park_name(row)

            if not strict_match(place, park_name):
                continue

            speciality = safe_get(row, ["Speciality", "speciality", "category", "Category"])
            location = safe_get(row, ["Area/Location", "area_location", "location", "Location", "address", "Address"])
            opening_time = safe_get(row, ["openingTime", "opening_time", "Opening Time"])
            closing_time = safe_get(row, ["closingTime", "closing_time", "Closing Time"])
            entry_fee = safe_get(row, ["entryFee", "entry_fee", "Entry Fee"])
            expected_budget = safe_get(row, ["expectedBudget", "expected_budget", "Expected Budget"])

            details = f"""
🌳 Speciality: {speciality}

📍 Location: {location}

🕒 Timings: {opening_time} - {closing_time}

🎟 Entry Fee: {entry_fee}

💰 Expected Budget: {expected_budget}
"""

            return await localize_response({
                "name": park_name,
                "rating": safe_get(row, ["rating", "Rating", "totalScore", "score"], "N/A"),
                "details": details,
                "map_url": safe_get(row, ["googleMapsUrl", "google_maps_url", "map_url", "url"], f"https://www.google.com/maps/search/{park_name.replace(' ', '+')}"),
                "specialities": [speciality, location, entry_fee],
            }, language)

        for _, row in temples_df.iterrows():
            temple_name = get_temple_name(row)

            if not strict_match(place, temple_name):
                continue

            main_god = safe_get(row, ["mainGod", "main_god", "Main God"])
            speciality = safe_get(row, ["speciality", "Speciality"])
            location = safe_get(row, ["street", "Street", "location", "Location", "address", "Address"])
            opening_time = safe_get(row, ["openingTime", "opening_time", "Opening Time"])
            closing_time = safe_get(row, ["closingTime", "closing_time", "Closing Time"])
            timing_details = safe_get(row, ["timingDetails", "timing_details", "Timings"])
            darshan_fee = safe_get(row, ["darshanFee", "darshan_fee", "Entry Fee", "entryFee"])
            special_darshan = safe_get(row, ["specialDarshanFee", "special_darshan_fee"])
            dress_code = safe_get(row, ["dressCode", "dress_code"])
            best_time = safe_get(row, ["bestTimeToVisit", "best_time_to_visit"])
            festivals = safe_get(row, ["festivalsCelebrated", "festivals"])
            parking = safe_get(row, ["parkingAvailability", "parking"])
            crowd = safe_get(row, ["crowdLevel", "crowd_level"])
            nearby = safe_get(row, ["nearbyAttractions", "nearby_attractions"])

            details = f"""
🛕 Main God: {main_god}

✨ Speciality: {speciality}

📍 Location: {location}

🕒 Timings: {timing_details if timing_details else opening_time + " - " + closing_time}

🎟 Darshan Fee: {darshan_fee}

🙏 Special Darshan: {special_darshan}

👗 Dress Code: {dress_code}

🌟 Best Time: {best_time}

🎉 Festivals: {festivals}

🚗 Parking: {parking}

👥 Crowd Level: {crowd}

📌 Nearby Attractions: {nearby}
"""

            return await localize_response({
                "name": temple_name,
                "rating": safe_get(row, ["rating", "Rating", "totalScore", "score"], "N/A"),
                "details": details,
                "map_url": safe_get(row, ["googleMapsUrl", "google_maps_url", "map_url", "url"], f"https://www.google.com/maps/search/{temple_name.replace(' ', '+')}"),
                "specialities": [main_god, speciality, best_time],
            }, language)

        for _, row in museums_df.iterrows():
            museum_name = get_museum_name(row)

            if not strict_match(place, museum_name):
                continue

            speciality = safe_get(row, ["speciality", "Speciality", "description", "Description", "about", "About"])
            location = safe_get(row, ["street", "Street", "location", "Location", "address", "Address", "museum_area"])
            opening_time = safe_get(row, ["openingTime", "opening_time", "Opening Time", "timings", "Timings"])
            closing_time = safe_get(row, ["closingTime", "closing_time", "Closing Time"])
            entry_fee = safe_get(row, ["entryFee", "entry_fee", "Entry Fee"])
            expected_budget = safe_get(row, ["expectedBudget", "expected_budget", "Expected Budget"])
            category = safe_get(row, ["category", "Category", "categories/0"])

            details = f"""
🏛 Category: {category}

✨ Speciality: {speciality}

📍 Location: {location}

🕒 Timings: {opening_time} - {closing_time}

🎟 Entry Fee: {entry_fee}

💰 Expected Budget: {expected_budget}
"""

            return await localize_response({
                "name": museum_name,
                "rating": safe_get(row, ["rating", "Rating", "totalScore", "score"], "N/A"),
                "details": details,
                "map_url": safe_get(row, ["googleMapsUrl", "google_maps_url", "map_url", "url"], f"https://www.google.com/maps/search/{museum_name.replace(' ', '+')}"),
                "specialities": [category, speciality, location],
            }, language)

        for _, row in hospitals_df.iterrows():
            hospital_name = get_hospital_name(row)

            if not strict_match(place, hospital_name):
                continue

            speciality = safe_get(row, ["speciality", "Speciality", "description", "Description", "about", "About", "categoryName", "category"])
            location = safe_get(row, ["street", "Street", "location", "Location", "address", "Address", "hospital_area"])
            phone = safe_get(row, ["phone", "Phone", "contact", "Contact"])
            website = safe_get(row, ["website", "Website"])
            category = safe_get(row, ["categoryName", "Category", "categories/0", "hospitalType", "hospital_type"])

            details = f"""
🏥 Category: {category}

✨ Speciality: {speciality}

📍 Location: {location}

☎ Phone: {phone}

🌐 Website: {website}
"""

            return await localize_response({
                "name": hospital_name,
                "rating": safe_get(row, ["rating", "Rating", "totalScore", "score"], "N/A"),
                "details": details,
                "map_url": safe_get(row, ["googleMapsUrl", "google_maps_url", "map_url", "url", "URL"], f"https://www.google.com/maps/search/{hospital_name.replace(' ', '+')}"),
                "specialities": [category, speciality, location],
            }, language)

        for _, row in theaters_df.iterrows():
            theater_name = get_theater_name(row)

            if not strict_match(place, theater_name):
                continue

            speciality = safe_get(row, ["speciality", "Speciality", "description", "Description", "about", "About"])
            location = safe_get(row, ["street", "Street", "location", "Location", "address", "Address", "theater_area", "theatre_area"])
            category = safe_get(row, ["categoryName", "Category", "categories/0", "screenType", "screen_type"])
            screen_type = safe_get(row, ["screenType", "screen_type", "Screen Type"])
            audio = safe_get(row, ["audioSystem", "audio_system", "Audio System"])
            ticket_price = safe_get(row, ["ticketPriceRange", "ticket_price_range", "ticket_price", "Ticket Price"])
            best_for = safe_get(row, ["bestFor", "best_for", "Best For"])
            expected_budget = safe_get(row, ["expectedBudget", "expected_budget", "Expected Budget"])

            details = f"""
🎬 Category: {category}

✨ Speciality: {speciality}

📍 Location: {location}

🖥 Screen Type: {screen_type}

🔊 Audio System: {audio}

🎟 Ticket Price: {ticket_price}

🎯 Best For: {best_for}

💰 Expected Budget: {expected_budget}
"""

            return await localize_response({
                "name": theater_name,
                "rating": safe_get(row, ["rating", "Rating", "totalScore", "score"], "N/A"),
                "details": details,
                "map_url": safe_get(row, ["googleMapsUrl", "google_maps_url", "map_url", "url", "URL"], f"https://www.google.com/maps/search/{theater_name.replace(' ', '+')}"),
                "specialities": [category, speciality, location],
            }, language)

        for _, row in pubs_df.iterrows():
            pub_name = get_pub_name(row)

            if not strict_match(place, pub_name):
                continue

            speciality = safe_get(row, ["speciality", "Speciality", "description", "Description", "about", "About"])
            location = safe_get(row, ["street", "Street", "location", "Location", "address", "Address", "pub_area", "area"])
            category = safe_get(row, ["categoryName", "Category", "categories/0", "categories", "type"])
            website = safe_get(row, ["website", "Website"])
            expected_budget = safe_get(row, ["expectedBudget", "expected_budget", "Expected Budget", "priceRange", "budget"])
            best_for = safe_get(row, ["bestFor", "best_for", "Best For"])

            details = f"""
🍻 Category: {category}

✨ Speciality: {speciality}

📍 Location: {location}

🌐 Website: {website}

🎯 Best For: {best_for}

💰 Expected Budget: {expected_budget}
"""

            return await localize_response({
                "name": pub_name,
                "rating": safe_get(row, ["rating", "Rating", "totalScore", "score"], "N/A"),
                "details": details,
                "map_url": safe_get(row, ["googleMapsUrl", "google_maps_url", "map_url", "url", "URL"], f"https://www.google.com/maps/search/{pub_name.replace(' ', '+')}"),
                "specialities": [category, speciality, location],
            }, language)

        return await localize_response({
            "name": place.title(),
            "rating": "N/A",
            "details": "Place not found.",
            "map_url": "#",
            "specialities": [],
        }, language)

    except Exception:
        traceback.print_exc()
        return await localize_response({
            "name": place.title(),
            "rating": "N/A",
            "details": "Server error.",
            "map_url": "#",
            "specialities": [],
        }, language)

@app.get("/transport")
async def get_transport_data(place: str = "", language: str = "English"):
    try:
        buses = []

        if is_beach_query(place):
            for _, row in beach_apsrtc_df.iterrows():
                beach_name = get_beach_name(row)
                if not strict_match(place, beach_name):
                    continue
                buses.append({
                    "place_type": "beach",
                    "beach_name": beach_name,
                    "route_no": safe_get(row, ["Bus Route No", "route_no"]),
                    "route": safe_get(row, ["Route Description (From → To)", "route"]),
                    "start": safe_get(row, ["Starting Point", "start"]),
                    "end": safe_get(row, ["Ending Point", "destination", "end"]),
                    "via": safe_get(row, ["Key Stops (Via)", "via"]),
                    "fare": safe_get(row, ["Approx Fare (₹)", "fare"]),
                    "time": safe_get(row, ["Journey Time", "time"]),
                    "frequency": safe_get(row, ["Frequency", "frequency"]),
                    "first_bus": safe_get(row, ["First Bus", "first_bus"]),
                    "last_bus": safe_get(row, ["Last Bus", "last_bus"]),
                    "alight_at": safe_get(row, ["Alight At (Beach Stop)", "alight_at"]),
                    "direct_bus": safe_get(row, ["Direct Bus?", "direct_bus"]),
                    "last_mile_tips": safe_get(row, ["Last Mile Tips", "last_mile_tips"]),
                })

        elif is_pub_query(place):
            for _, row in pub_apsrtc_df.iterrows():
                pub_name = get_pub_name(row)

                if not strict_match(place, pub_name):
                    continue

                buses.append({
                    "place_type": "pub",
                    "pub_name": pub_name,
                    "route_no": safe_get(row, ["bus_number", "Bus Route No", "route_no"]),
                    "route": safe_get(row, ["description", "Route Description (From → To)", "route"]),
                    "start": safe_get(row, ["source_area", "Starting Point", "start"]),
                    "end": safe_get(row, ["pub_area", "Ending Point", "destination", "end"]),
                    "via": safe_get(row, ["major_stops", "Key Stops (Via)", "via"]),
                    "fare": safe_get(row, ["ticket_price", "Approx Fare (₹)", "fare"]),
                    "time": safe_get(row, ["estimated_duration", "Journey Time", "time"]),
                    "frequency": safe_get(row, ["frequency_minutes", "Frequency", "frequency"]),
                    "first_bus": safe_get(row, ["first_bus", "First Bus"]),
                    "last_bus": safe_get(row, ["last_bus", "Last Bus"]),
                    "alight_at": safe_get(row, ["nearest_bus_stop", "Alight At (Pub Stop)", "alight_at"]),
                    "direct_bus": safe_get(row, ["tourist_friendly", "Direct Bus?", "direct_bus"]),
                    "last_mile_tips": "Walk " + safe_get(row, ["walking_distance_from_stop_km"], "0") + " km from stop",
                })


        elif is_cafe_query(place):
            for _, row in cafe_apsrtc_df.iterrows():
                cafe_name = get_cafe_name(row)

                if not strict_match(place, cafe_name):
                    continue

                buses.append({
                    "place_type": "cafe",
                    "cafe_name": cafe_name,
                    "route_no": safe_get(row, ["bus_number", "Bus Route No", "route_no"]),
                    "route": safe_get(row, ["description", "Route Description (From → To)", "route"]),
                    "start": safe_get(row, ["source_area", "Starting Point", "start"]),
                    "end": safe_get(row, ["cafe_area", "Ending Point", "destination", "end"]),
                    "via": safe_get(row, ["major_stops", "Key Stops (Via)", "via"]),
                    "fare": safe_get(row, ["ticket_price", "Approx Fare (₹)", "fare"]),
                    "time": safe_get(row, ["estimated_duration", "Journey Time", "time"]),
                    "frequency": safe_get(row, ["frequency_minutes", "Frequency", "frequency"]),
                    "first_bus": safe_get(row, ["first_bus", "First Bus"]),
                    "last_bus": safe_get(row, ["last_bus", "Last Bus"]),
                    "alight_at": safe_get(row, ["nearest_bus_stop", "Alight At (Cafe Stop)", "alight_at"]),
                    "direct_bus": safe_get(row, ["tourist_friendly", "Direct Bus?", "direct_bus"]),
                    "last_mile_tips": "Walk " + safe_get(row, ["walking_distance_from_stop_km"], "0") + " km from stop",
                })


        elif is_restaurant_query(place):
            for _, row in restaurant_apsrtc_df.iterrows():
                restaurant_name = get_restaurant_name(row)
                if not strict_match(place, restaurant_name):
                    continue
                buses.append({
                    "place_type": "restaurant",
                    "restaurant_name": restaurant_name,
                    "route_no": safe_get(row, ["bus_number"]),
                    "route": safe_get(row, ["description"]),
                    "start": safe_get(row, ["source_area"]),
                    "end": safe_get(row, ["restaurant_area"]),
                    "via": safe_get(row, ["major_stops"]),
                    "fare": safe_get(row, ["ticket_price"]),
                    "time": safe_get(row, ["estimated_duration"]),
                    "frequency": safe_get(row, ["frequency_minutes"]),
                    "first_bus": safe_get(row, ["first_bus"]),
                    "last_bus": safe_get(row, ["last_bus"]),
                    "alight_at": safe_get(row, ["nearest_bus_stop"]),
                    "direct_bus": safe_get(row, ["tourist_friendly"]),
                    "last_mile_tips": "Walk " + safe_get(row, ["walking_distance_from_stop_km"], "0") + " km from stop",
                })

        elif is_park_query(place):
            for _, row in park_apsrtc_df.iterrows():
                park_name = get_park_name(row)
                if not strict_match(place, park_name):
                    continue
                buses.append({
                    "place_type": "park",
                    "park_name": park_name,
                    "route_no": safe_get(row, ["bus_number", "Bus Route No", "route_no"]),
                    "route": safe_get(row, ["description", "Route Description (From → To)", "route"]),
                    "start": safe_get(row, ["source_area", "Starting Point", "start"]),
                    "end": safe_get(row, ["park_area", "Ending Point", "destination", "end"]),
                    "via": safe_get(row, ["major_stops", "Key Stops (Via)", "via"]),
                    "fare": safe_get(row, ["ticket_price", "Approx Fare (₹)", "fare"]),
                    "time": safe_get(row, ["estimated_duration", "Journey Time", "time"]),
                    "frequency": safe_get(row, ["frequency_minutes", "Frequency", "frequency"]),
                    "first_bus": safe_get(row, ["first_bus", "First Bus"]),
                    "last_bus": safe_get(row, ["last_bus", "Last Bus"]),
                    "alight_at": safe_get(row, ["nearest_bus_stop", "Alight At (Park Stop)", "alight_at"]),
                    "direct_bus": safe_get(row, ["tourist_friendly", "Direct Bus?", "direct_bus"]),
                    "last_mile_tips": "Walk " + safe_get(row, ["walking_distance_from_stop_km"], "0") + " km from stop",
                })

        elif is_temple_query(place):
            for _, row in temple_apsrtc_df.iterrows():
                temple_name = get_temple_name(row)
                if not strict_match(place, temple_name):
                    continue
                buses.append({
                    "place_type": "temple",
                    "temple_name": temple_name,
                    "route_no": safe_get(row, ["bus_number", "Bus Route No", "route_no"]),
                    "route": safe_get(row, ["description", "Route Description (From → To)", "route"]),
                    "start": safe_get(row, ["source_area", "Starting Point", "start"]),
                    "end": safe_get(row, ["temple_area", "Ending Point", "destination", "end"]),
                    "via": safe_get(row, ["major_stops", "Key Stops (Via)", "via"]),
                    "fare": safe_get(row, ["ticket_price", "Approx Fare (₹)", "fare"]),
                    "time": safe_get(row, ["estimated_duration", "Journey Time", "time"]),
                    "frequency": safe_get(row, ["frequency_minutes", "Frequency", "frequency"]),
                    "first_bus": safe_get(row, ["first_bus", "First Bus"]),
                    "last_bus": safe_get(row, ["last_bus", "Last Bus"]),
                    "alight_at": safe_get(row, ["nearest_bus_stop", "Alight At (Temple Stop)", "alight_at"]),
                    "direct_bus": safe_get(row, ["tourist_friendly", "Direct Bus?", "direct_bus"]),
                    "last_mile_tips": "Walk " + safe_get(row, ["walking_distance_from_stop_km"], "0") + " km from stop",
                })

        elif is_museum_query(place):
            for _, row in museum_apsrtc_df.iterrows():
                museum_name = get_museum_name(row)
                if not strict_match(place, museum_name):
                    continue
                buses.append({
                    "place_type": "museum",
                    "museum_name": museum_name,
                    "route_no": safe_get(row, ["bus_number", "Bus Route No", "route_no"]),
                    "route": safe_get(row, ["description", "Route Description (From → To)", "route"]),
                    "start": safe_get(row, ["source_area", "Starting Point", "start"]),
                    "end": safe_get(row, ["museum_area", "Ending Point", "destination", "end"]),
                    "via": safe_get(row, ["major_stops", "Key Stops (Via)", "via"]),
                    "fare": safe_get(row, ["ticket_price", "Approx Fare (₹)", "fare"]),
                    "time": safe_get(row, ["estimated_duration", "Journey Time", "time"]),
                    "frequency": safe_get(row, ["frequency_minutes", "Frequency", "frequency"]),
                    "first_bus": safe_get(row, ["first_bus", "First Bus"]),
                    "last_bus": safe_get(row, ["last_bus", "Last Bus"]),
                    "alight_at": safe_get(row, ["nearest_bus_stop", "Alight At (Museum Stop)", "alight_at"]),
                    "direct_bus": safe_get(row, ["tourist_friendly", "Direct Bus?", "direct_bus"]),
                    "last_mile_tips": "Walk " + safe_get(row, ["walking_distance_from_stop_km"], "0") + " km from stop",
                })

        elif is_hospital_query(place):
            for _, row in hospital_apsrtc_df.iterrows():
                hospital_name = get_hospital_name(row)

                if not strict_match(place, hospital_name):
                    continue

                buses.append({
                    "place_type": "hospital",
                    "hospital_name": hospital_name,
                    "route_no": safe_get(row, ["bus_number", "Bus Route No", "route_no"]),
                    "route": safe_get(row, ["description", "Route Description (From → To)", "route"]),
                    "start": safe_get(row, ["source_area", "Starting Point", "start"]),
                    "end": safe_get(row, ["hospital_area", "Ending Point", "destination", "end"]),
                    "via": safe_get(row, ["major_stops", "Key Stops (Via)", "via"]),
                    "fare": safe_get(row, ["ticket_price", "Approx Fare (₹)", "fare"]),
                    "time": safe_get(row, ["estimated_duration", "Journey Time", "time"]),
                    "frequency": safe_get(row, ["frequency_minutes", "Frequency", "frequency"]),
                    "first_bus": safe_get(row, ["first_bus", "First Bus"]),
                    "last_bus": safe_get(row, ["last_bus", "Last Bus"]),
                    "alight_at": safe_get(row, ["nearest_bus_stop", "Alight At (Hospital Stop)", "alight_at"]),
                    "direct_bus": safe_get(row, ["emergency_friendly", "tourist_friendly", "Direct Bus?", "direct_bus"]),
                    "last_mile_tips": "Walk " + safe_get(row, ["walking_distance_from_stop_km"], "0") + " km from stop",
                })


        elif is_theater_query(place):
            for _, row in theater_apsrtc_df.iterrows():
                theater_name = get_theater_name(row)

                if not strict_match(place, theater_name):
                    continue

                buses.append({
                    "place_type": "theater",
                    "theater_name": theater_name,
                    "route_no": safe_get(row, ["bus_number", "Bus Route No", "route_no"]),
                    "route": safe_get(row, ["description", "Route Description (From → To)", "route"]),
                    "start": safe_get(row, ["source_area", "Starting Point", "start"]),
                    "end": safe_get(row, ["theater_area", "theatre_area", "Ending Point", "destination", "end"]),
                    "via": safe_get(row, ["major_stops", "Key Stops (Via)", "via"]),
                    "fare": safe_get(row, ["ticket_price", "Approx Fare (₹)", "fare"]),
                    "time": safe_get(row, ["estimated_duration", "Journey Time", "time"]),
                    "frequency": safe_get(row, ["frequency_minutes", "Frequency", "frequency"]),
                    "first_bus": safe_get(row, ["first_bus", "First Bus"]),
                    "last_bus": safe_get(row, ["last_bus", "Last Bus"]),
                    "alight_at": safe_get(row, ["nearest_bus_stop", "Alight At (Theater Stop)", "alight_at"]),
                    "direct_bus": safe_get(row, ["tourist_friendly", "Direct Bus?", "direct_bus"]),
                    "last_mile_tips": "Walk " + safe_get(row, ["walking_distance_from_stop_km"], "0") + " km from stop",
                })


        return await localize_response({"buses": buses}, language)

    except Exception as e:
        traceback.print_exc()
        return await localize_response({"buses": [], "error": str(e)}, language)


@app.get("/walking")
async def get_walking_data(place: str = "", language: str = "English"):
    try:
        walking_details = []

        if is_beach_query(place):
            for _, row in beach_walk_df.iterrows():
                beach_name = get_beach_name(row)
                beach_alias = get_beach_alias(row)
                if not (strict_match(place, beach_name) or strict_match(place, beach_alias)):
                    continue
                walking_details.append({
                    "place_type": "beach",
                    "from_locality": safe_get(row, ["From (Locality)", "from_locality"]),
                    "zone": safe_get(row, ["Zone", "zone"]),
                    "beach_name": beach_name,
                    "beach_alias": beach_alias,
                    "walking_distance": safe_get(row, ["Walking Distance (km)", "walking_distance_km"]),
                    "walking_time": safe_get(row, ["Walking Time", "walking_time"]),
                    "walking_speed": safe_get(row, ["Walking Speed (avg)", "walking_speed"]),
                    "steps": safe_get(row, ["Approx Steps", "steps"]),
                    "calories": safe_get(row, ["Approx Calories Burned", "calories"]),
                    "feasibility": safe_get(row, ["Walk Feasibility", "feasibility"]),
                    "best_time": safe_get(row, ["Best Time to Walk", "best_time"]),
                    "route_tip": safe_get(row, ["Walking Route Tip", "route_tip"]),
                    "rapido_bike_if_far": safe_get(row, ["Rapido Bike Fare (₹) – if too far"]),
                    "rapido_auto_if_far": safe_get(row, ["Rapido Auto Fare (₹) – if too far"]),
                    "rapido_cab_if_far": safe_get(row, ["Rapido Cab Fare (₹) – if too far"]),
                })

        elif is_pub_query(place):
            for _, row in pub_walk_df.iterrows():
                pub_name = get_pub_name(row)

                if not strict_match(place, pub_name):
                    continue

                walking_details.append({
                    "place_type": "pub",
                    "pub_name": pub_name,
                    "from_locality": safe_get(row, ["source_area", "source_place", "From (Locality)", "from_locality"]),
                    "zone": safe_get(row, ["pub_area", "Zone", "zone"]),
                    "beach_alias": safe_get(row, ["nearest_landmarks", "destination_landmark", "alias"]),
                    "walking_distance": safe_get(row, ["distance_km", "walking_distance_km", "Walking Distance (km)"]),
                    "walking_time": safe_get(row, ["estimated_walk_duration", "estimated_walk_time_minutes", "Walking Time"]),
                    "walking_speed": "",
                    "steps": "",
                    "calories": "",
                    "feasibility": safe_get(row, ["walking_difficulty", "safe_for_tourists", "Walk Feasibility"]),
                    "best_time": safe_get(row, ["best_time_to_walk", "Best Time to Walk"]),
                    "route_tip": safe_get(row, ["best_walking_route", "walking_direction_steps", "Walking Route Tip"]),
                    "rapido_bike_if_far": "",
                    "rapido_auto_if_far": "",
                    "rapido_cab_if_far": "",
                })


        elif is_cafe_query(place):
            for _, row in cafe_walk_df.iterrows():
                cafe_name = get_cafe_name(row)

                if not strict_match(place, cafe_name):
                    continue

                walking_details.append({
                    "place_type": "cafe",
                    "cafe_name": cafe_name,
                    "from_locality": safe_get(row, ["source_place", "source_area", "From (Locality)", "from_locality"]),
                    "zone": safe_get(row, ["cafe_area", "Zone", "zone"]),
                    "beach_alias": safe_get(row, ["destination_landmark", "nearest_landmarks", "alias"]),
                    "walking_distance": safe_get(row, ["walking_distance_km", "distance_km", "Walking Distance (km)"]),
                    "walking_time": safe_get(row, ["estimated_walk_time_minutes", "estimated_walk_duration", "Walking Time"]),
                    "walking_speed": "",
                    "steps": "",
                    "calories": "",
                    "feasibility": safe_get(row, ["safe_for_tourists", "walking_difficulty", "Walk Feasibility"]),
                    "best_time": safe_get(row, ["best_time_to_walk", "Best Time to Walk"]),
                    "route_tip": safe_get(row, ["walking_direction_steps", "best_walking_route", "Walking Route Tip"]),
                    "rapido_bike_if_far": "",
                    "rapido_auto_if_far": "",
                    "rapido_cab_if_far": "",
                })


        elif is_restaurant_query(place):
            for _, row in restaurant_walk_df.iterrows():
                restaurant_name = get_restaurant_name(row)
                if not strict_match(place, restaurant_name):
                    continue
                walking_details.append({
                    "place_type": "restaurant",
                    "restaurant_name": restaurant_name,
                    "from_locality": safe_get(row, ["source_place"]),
                    "zone": safe_get(row, ["restaurant_area"]),
                    "beach_alias": safe_get(row, ["destination_landmark"]),
                    "walking_distance": safe_get(row, ["walking_distance_km"]),
                    "walking_time": safe_get(row, ["estimated_walk_time_minutes"]),
                    "walking_speed": "",
                    "steps": "",
                    "calories": "",
                    "feasibility": safe_get(row, ["safe_for_tourists"]),
                    "best_time": safe_get(row, ["best_time_to_walk"]),
                    "route_tip": safe_get(row, ["walking_direction_steps"]),
                    "rapido_bike_if_far": "",
                    "rapido_auto_if_far": "",
                    "rapido_cab_if_far": "",
                })

        elif is_park_query(place):
            for _, row in park_walk_df.iterrows():
                park_name = get_park_name(row)
                if not strict_match(place, park_name):
                    continue
                walking_details.append({
                    "place_type": "park",
                    "park_name": park_name,
                    "from_locality": safe_get(row, ["source_place", "From (Locality)", "from_locality"]),
                    "zone": safe_get(row, ["park_area", "Zone", "zone"]),
                    "beach_alias": safe_get(row, ["destination_landmark", "park_alias", "alias"]),
                    "walking_distance": safe_get(row, ["walking_distance_km", "Walking Distance (km)"]),
                    "walking_time": safe_get(row, ["estimated_walk_time_minutes", "Walking Time"]),
                    "walking_speed": safe_get(row, ["walking_speed", "Walking Speed (avg)"]),
                    "steps": safe_get(row, ["steps", "Approx Steps"]),
                    "calories": safe_get(row, ["calories", "Approx Calories Burned"]),
                    "feasibility": safe_get(row, ["safe_for_tourists", "Walk Feasibility"]),
                    "best_time": safe_get(row, ["best_time_to_walk", "Best Time to Walk"]),
                    "route_tip": safe_get(row, ["walking_direction_steps", "Walking Route Tip"]),
                    "rapido_bike_if_far": "",
                    "rapido_auto_if_far": "",
                    "rapido_cab_if_far": "",
                })

        elif is_temple_query(place):
            for _, row in temple_walk_df.iterrows():
                temple_name = get_temple_name(row)
                if not strict_match(place, temple_name):
                    continue
                walking_details.append({
                    "place_type": "temple",
                    "temple_name": temple_name,
                    "from_locality": safe_get(row, ["source_area", "source_place", "From (Locality)", "from_locality"]),
                    "zone": safe_get(row, ["temple_area", "Zone", "zone"]),
                    "beach_alias": safe_get(row, ["nearest_landmarks", "destination_landmark", "alias"]),
                    "walking_distance": safe_get(row, ["distance_km", "walking_distance_km", "Walking Distance (km)"]),
                    "walking_time": safe_get(row, ["estimated_walk_duration", "estimated_walk_time_minutes", "Walking Time"]),
                    "walking_speed": "",
                    "steps": "",
                    "calories": "",
                    "feasibility": safe_get(row, ["walking_difficulty", "safe_for_tourists", "Walk Feasibility"]),
                    "best_time": safe_get(row, ["best_time_to_walk", "Best Time to Walk"]),
                    "route_tip": safe_get(row, ["best_walking_route", "walking_direction_steps", "Walking Route Tip"]),
                    "rapido_bike_if_far": "",
                    "rapido_auto_if_far": "",
                    "rapido_cab_if_far": "",
                })

        elif is_museum_query(place):
            for _, row in museum_walk_df.iterrows():
                museum_name = get_museum_name(row)
                if not strict_match(place, museum_name):
                    continue
                walking_details.append({
                    "place_type": "museum",
                    "museum_name": museum_name,
                    "from_locality": safe_get(row, ["source_place", "source_area", "From (Locality)", "from_locality"]),
                    "zone": safe_get(row, ["museum_area", "Zone", "zone"]),
                    "beach_alias": safe_get(row, ["destination_landmark", "nearest_landmarks", "alias"]),
                    "walking_distance": safe_get(row, ["walking_distance_km", "distance_km", "Walking Distance (km)"]),
                    "walking_time": safe_get(row, ["estimated_walk_time_minutes", "estimated_walk_duration", "Walking Time"]),
                    "walking_speed": "",
                    "steps": "",
                    "calories": "",
                    "feasibility": safe_get(row, ["safe_for_tourists", "walking_difficulty", "Walk Feasibility"]),
                    "best_time": safe_get(row, ["best_time_to_walk", "Best Time to Walk"]),
                    "route_tip": safe_get(row, ["walking_direction_steps", "best_walking_route", "Walking Route Tip"]),
                    "rapido_bike_if_far": "",
                    "rapido_auto_if_far": "",
                    "rapido_cab_if_far": "",
                })

        elif is_hospital_query(place):
            for _, row in hospital_walk_df.iterrows():
                hospital_name = get_hospital_name(row)

                if not strict_match(place, hospital_name):
                    continue

                walking_details.append({
                    "place_type": "hospital",
                    "hospital_name": hospital_name,
                    "from_locality": safe_get(row, ["source_area", "source_place", "From (Locality)", "from_locality"]),
                    "zone": safe_get(row, ["hospital_area", "Zone", "zone"]),
                    "beach_alias": safe_get(row, ["nearest_landmarks", "destination_landmark", "alias"]),
                    "walking_distance": safe_get(row, ["distance_km", "walking_distance_km", "Walking Distance (km)"]),
                    "walking_time": safe_get(row, ["estimated_walk_duration", "estimated_walk_time_minutes", "Walking Time"]),
                    "walking_speed": "",
                    "steps": "",
                    "calories": "",
                    "feasibility": safe_get(row, ["walking_difficulty", "safe_for_tourists", "Walk Feasibility"]),
                    "best_time": safe_get(row, ["best_time_to_walk", "Best Time to Walk"]),
                    "route_tip": safe_get(row, ["best_walking_route", "walking_direction_steps", "Walking Route Tip"]),
                    "rapido_bike_if_far": "",
                    "rapido_auto_if_far": safe_get(row, ["emergency_alternative_transport"]),
                    "rapido_cab_if_far": safe_get(row, ["emergency_alternative_transport"]),
                })


        elif is_theater_query(place):
            for _, row in theater_walk_df.iterrows():
                theater_name = get_theater_name(row)

                if not strict_match(place, theater_name):
                    continue

                walking_details.append({
                    "place_type": "theater",
                    "theater_name": theater_name,
                    "from_locality": safe_get(row, ["source_area", "source_place", "From (Locality)", "from_locality"]),
                    "zone": safe_get(row, ["theater_area", "theatre_area", "Zone", "zone"]),
                    "beach_alias": safe_get(row, ["nearest_landmarks", "destination_landmark", "alias"]),
                    "walking_distance": safe_get(row, ["distance_km", "walking_distance_km", "Walking Distance (km)"]),
                    "walking_time": safe_get(row, ["estimated_walk_duration", "estimated_walk_time_minutes", "Walking Time"]),
                    "walking_speed": "",
                    "steps": "",
                    "calories": "",
                    "feasibility": safe_get(row, ["walking_difficulty", "safe_for_tourists", "Walk Feasibility"]),
                    "best_time": safe_get(row, ["best_time_to_walk", "Best Time to Walk"]),
                    "route_tip": safe_get(row, ["best_walking_route", "walking_direction_steps", "Walking Route Tip"]),
                    "rapido_bike_if_far": "",
                    "rapido_auto_if_far": "",
                    "rapido_cab_if_far": "",
                })


        # If there is no walking row OR the matched row has blank walking data,
        # show only a clean route tip instead of empty/failed walking details.
        if not walking_details or not any(has_useful_walking_details(item) for item in walking_details):
            walking_details = [build_walking_route_tip(place)]

        return await localize_response({"walking": walking_details}, language)

    except Exception as e:
        traceback.print_exc()
        return await localize_response({"walking": [], "error": str(e)}, language)


@app.get("/rapido")
async def get_rapido_data(place: str = "", language: str = "English"):
    try:
        rapido_details = []

        if is_beach_query(place):
            for _, row in beach_rapido_df.iterrows():
                beach_name = get_beach_name(row)
                beach_alias = get_beach_alias(row)
                if not (strict_match(place, beach_name) or strict_match(place, beach_alias)):
                    continue
                rapido_details.append({
                    "place_type": "beach",
                    "from_locality": safe_get(row, ["From (Locality)", "from_locality"]),
                    "zone": safe_get(row, ["Zone", "zone"]),
                    "beach_name": beach_name,
                    "beach_alias": beach_alias,
                    "approx_distance": safe_get(row, ["Approx Distance (km)", "distance_km"]),
                    "bike_base_fare": safe_get(row, ["Rapido Bike – Base Fare (₹)"]),
                    "bike_per_km": safe_get(row, ["Rapido Bike – Per km (₹)"]),
                    "bike_day_fare": safe_get(row, ["Rapido Bike – Day Fare (₹)", "rapido_bike_price"]),
                    "bike_night_fare": safe_get(row, ["Rapido Bike – Night Fare (₹)"]),
                    "bike_time": safe_get(row, ["Rapido Bike – Est. Travel Time", "estimated_duration"]),
                    "auto_base_fare": safe_get(row, ["Rapido Auto – Base Fare (₹)"]),
                    "auto_per_km": safe_get(row, ["Rapido Auto – Per km (₹)"]),
                    "auto_day_fare": safe_get(row, ["Rapido Auto – Day Fare (₹)", "auto_price"]),
                    "auto_night_fare": safe_get(row, ["Rapido Auto – Night Fare (₹)"]),
                    "auto_time": safe_get(row, ["Rapido Auto – Est. Travel Time", "estimated_duration"]),
                    "cab_base_fare": safe_get(row, ["Rapido Cab – Base Fare (₹)"]),
                    "cab_per_km": safe_get(row, ["Rapido Cab – Per km (₹)"]),
                    "cab_day_fare": safe_get(row, ["Rapido Cab – Day Fare (₹)", "cab_price"]),
                    "cab_night_fare": safe_get(row, ["Rapido Cab – Night Fare (₹)"]),
                    "cab_time": safe_get(row, ["Rapido Cab – Est. Travel Time", "estimated_duration"]),
                    "cheapest_option": safe_get(row, ["Cheapest Option", "best_transport_option"]),
                    "day_fare_summary": safe_get(row, ["Day Fare Summary (Bike/Auto/Cab)", "description"]),
                    "rapido_app": safe_get(row, ["Rapido App"]),
                })

        elif is_pub_query(place):
            for _, row in pub_rapido_df.iterrows():
                pub_name = get_pub_name(row)

                if not strict_match(place, pub_name):
                    continue

                rapido_details.append({
                    "place_type": "pub",
                    "pub_name": pub_name,
                    "from_locality": safe_get(row, ["source_area", "From (Locality)", "from_locality"]),
                    "zone": safe_get(row, ["pub_area", "Zone", "zone"]),
                    "beach_alias": safe_get(row, ["nearest_landmarks", "alias"]),
                    "approx_distance": safe_get(row, ["distance_km", "Approx Distance (km)"]),
                    "bike_base_fare": "",
                    "bike_per_km": "",
                    "bike_day_fare": safe_get(row, ["rapido_bike_price", "Rapido Bike – Day Fare (₹)"]),
                    "bike_night_fare": "",
                    "bike_time": safe_get(row, ["estimated_duration", "Rapido Bike – Est. Travel Time"]),
                    "auto_base_fare": "",
                    "auto_per_km": "",
                    "auto_day_fare": safe_get(row, ["auto_price", "Rapido Auto – Day Fare (₹)"]),
                    "auto_night_fare": "",
                    "auto_time": safe_get(row, ["estimated_duration", "Rapido Auto – Est. Travel Time"]),
                    "cab_base_fare": "",
                    "cab_per_km": "",
                    "cab_day_fare": safe_get(row, ["cab_price", "Rapido Cab – Day Fare (₹)"]),
                    "cab_night_fare": "",
                    "cab_time": safe_get(row, ["estimated_duration", "Rapido Cab – Est. Travel Time"]),
                    "cheapest_option": safe_get(row, ["best_transport_option", "Cheapest Option"]),
                    "day_fare_summary": safe_get(row, ["description", "Day Fare Summary (Bike/Auto/Cab)"]),
                    "rapido_app": "",
                })


        elif is_cafe_query(place):
            for _, row in cafe_rapido_df.iterrows():
                cafe_name = get_cafe_name(row)

                if not strict_match(place, cafe_name):
                    continue

                rapido_details.append({
                    "place_type": "cafe",
                    "cafe_name": cafe_name,
                    "from_locality": safe_get(row, ["source_area", "From (Locality)", "from_locality"]),
                    "zone": safe_get(row, ["cafe_area", "Zone", "zone"]),
                    "beach_alias": safe_get(row, ["nearest_landmarks", "alias"]),
                    "approx_distance": safe_get(row, ["distance_km", "Approx Distance (km)"]),
                    "bike_base_fare": "",
                    "bike_per_km": "",
                    "bike_day_fare": safe_get(row, ["rapido_bike_price", "Rapido Bike – Day Fare (₹)"]),
                    "bike_night_fare": "",
                    "bike_time": safe_get(row, ["estimated_duration", "Rapido Bike – Est. Travel Time"]),
                    "auto_base_fare": "",
                    "auto_per_km": "",
                    "auto_day_fare": safe_get(row, ["auto_price", "Rapido Auto – Day Fare (₹)"]),
                    "auto_night_fare": "",
                    "auto_time": safe_get(row, ["estimated_duration", "Rapido Auto – Est. Travel Time"]),
                    "cab_base_fare": "",
                    "cab_per_km": "",
                    "cab_day_fare": safe_get(row, ["cab_price", "Rapido Cab – Day Fare (₹)"]),
                    "cab_night_fare": "",
                    "cab_time": safe_get(row, ["estimated_duration", "Rapido Cab – Est. Travel Time"]),
                    "cheapest_option": safe_get(row, ["best_transport_option", "Cheapest Option"]),
                    "day_fare_summary": safe_get(row, ["description", "Day Fare Summary (Bike/Auto/Cab)"]),
                    "rapido_app": "",
                })


        elif is_restaurant_query(place):
            for _, row in restaurant_rapido_df.iterrows():
                restaurant_name = get_restaurant_name(row)
                if not strict_match(place, restaurant_name):
                    continue
                rapido_details.append({
                    "place_type": "restaurant",
                    "restaurant_name": restaurant_name,
                    "from_locality": safe_get(row, ["source_area"]),
                    "zone": safe_get(row, ["restaurant_area"]),
                    "beach_alias": safe_get(row, ["nearest_landmarks"]),
                    "approx_distance": safe_get(row, ["distance_km"]),
                    "bike_base_fare": "",
                    "bike_per_km": "",
                    "bike_day_fare": safe_get(row, ["rapido_bike_price"]),
                    "bike_night_fare": "",
                    "bike_time": safe_get(row, ["estimated_duration"]),
                    "auto_base_fare": "",
                    "auto_per_km": "",
                    "auto_day_fare": safe_get(row, ["auto_price"]),
                    "auto_night_fare": "",
                    "auto_time": safe_get(row, ["estimated_duration"]),
                    "cab_base_fare": "",
                    "cab_per_km": "",
                    "cab_day_fare": safe_get(row, ["cab_price"]),
                    "cab_night_fare": "",
                    "cab_time": safe_get(row, ["estimated_duration"]),
                    "cheapest_option": safe_get(row, ["best_transport_option"]),
                    "day_fare_summary": safe_get(row, ["description"]),
                    "rapido_app": "",
                })

        elif is_park_query(place):
            for _, row in park_rapido_df.iterrows():
                park_name = get_park_name(row)
                if not strict_match(place, park_name):
                    continue
                rapido_details.append({
                    "place_type": "park",
                    "park_name": park_name,
                    "from_locality": safe_get(row, ["source_area", "From (Locality)", "from_locality"]),
                    "zone": safe_get(row, ["park_area", "Zone", "zone"]),
                    "beach_alias": safe_get(row, ["nearest_landmarks", "park_alias", "alias"]),
                    "approx_distance": safe_get(row, ["distance_km", "Approx Distance (km)"]),
                    "bike_base_fare": "",
                    "bike_per_km": "",
                    "bike_day_fare": safe_get(row, ["rapido_bike_price", "Rapido Bike – Day Fare (₹)"]),
                    "bike_night_fare": "",
                    "bike_time": safe_get(row, ["estimated_duration", "Rapido Bike – Est. Travel Time"]),
                    "auto_base_fare": "",
                    "auto_per_km": "",
                    "auto_day_fare": safe_get(row, ["auto_price", "Rapido Auto – Day Fare (₹)"]),
                    "auto_night_fare": "",
                    "auto_time": safe_get(row, ["estimated_duration", "Rapido Auto – Est. Travel Time"]),
                    "cab_base_fare": "",
                    "cab_per_km": "",
                    "cab_day_fare": safe_get(row, ["cab_price", "Rapido Cab – Day Fare (₹)"]),
                    "cab_night_fare": "",
                    "cab_time": safe_get(row, ["estimated_duration", "Rapido Cab – Est. Travel Time"]),
                    "cheapest_option": safe_get(row, ["best_transport_option", "Cheapest Option"]),
                    "day_fare_summary": safe_get(row, ["description", "Day Fare Summary (Bike/Auto/Cab)"]),
                    "rapido_app": "",
                })

        elif is_temple_query(place):
            for _, row in temple_rapido_df.iterrows():
                temple_name = get_temple_name(row)
                if not strict_match(place, temple_name):
                    continue
                rapido_details.append({
                    "place_type": "temple",
                    "temple_name": temple_name,
                    "from_locality": safe_get(row, ["source_area", "From (Locality)", "from_locality"]),
                    "zone": safe_get(row, ["temple_area", "Zone", "zone"]),
                    "beach_alias": safe_get(row, ["nearest_landmarks", "alias"]),
                    "approx_distance": safe_get(row, ["distance_km", "Approx Distance (km)"]),
                    "bike_base_fare": "",
                    "bike_per_km": "",
                    "bike_day_fare": safe_get(row, ["rapido_bike_price", "Rapido Bike – Day Fare (₹)"]),
                    "bike_night_fare": "",
                    "bike_time": safe_get(row, ["estimated_duration", "Rapido Bike – Est. Travel Time"]),
                    "auto_base_fare": "",
                    "auto_per_km": "",
                    "auto_day_fare": safe_get(row, ["auto_price", "Rapido Auto – Day Fare (₹)"]),
                    "auto_night_fare": "",
                    "auto_time": safe_get(row, ["estimated_duration", "Rapido Auto – Est. Travel Time"]),
                    "cab_base_fare": "",
                    "cab_per_km": "",
                    "cab_day_fare": safe_get(row, ["cab_price", "Rapido Cab – Day Fare (₹)"]),
                    "cab_night_fare": "",
                    "cab_time": safe_get(row, ["estimated_duration", "Rapido Cab – Est. Travel Time"]),
                    "cheapest_option": safe_get(row, ["best_transport_option", "Cheapest Option"]),
                    "day_fare_summary": safe_get(row, ["description", "Day Fare Summary (Bike/Auto/Cab)"]),
                    "rapido_app": "",
                })

        elif is_museum_query(place):
            for _, row in museum_rapido_df.iterrows():
                museum_name = get_museum_name(row)
                if not strict_match(place, museum_name):
                    continue
                rapido_details.append({
                    "place_type": "museum",
                    "museum_name": museum_name,
                    "from_locality": safe_get(row, ["source_area", "From (Locality)", "from_locality"]),
                    "zone": safe_get(row, ["museum_area", "Zone", "zone"]),
                    "beach_alias": safe_get(row, ["nearest_landmarks", "alias"]),
                    "approx_distance": safe_get(row, ["distance_km", "Approx Distance (km)"]),
                    "bike_base_fare": "",
                    "bike_per_km": "",
                    "bike_day_fare": safe_get(row, ["rapido_bike_price", "Rapido Bike – Day Fare (₹)"]),
                    "bike_night_fare": "",
                    "bike_time": safe_get(row, ["estimated_duration", "Rapido Bike – Est. Travel Time"]),
                    "auto_base_fare": "",
                    "auto_per_km": "",
                    "auto_day_fare": safe_get(row, ["auto_price", "Rapido Auto – Day Fare (₹)"]),
                    "auto_night_fare": "",
                    "auto_time": safe_get(row, ["estimated_duration", "Rapido Auto – Est. Travel Time"]),
                    "cab_base_fare": "",
                    "cab_per_km": "",
                    "cab_day_fare": safe_get(row, ["cab_price", "Rapido Cab – Day Fare (₹)"]),
                    "cab_night_fare": "",
                    "cab_time": safe_get(row, ["estimated_duration", "Rapido Cab – Est. Travel Time"]),
                    "cheapest_option": safe_get(row, ["best_transport_option", "Cheapest Option"]),
                    "day_fare_summary": safe_get(row, ["description", "Day Fare Summary (Bike/Auto/Cab)"]),
                    "rapido_app": "",
                })

        elif is_hospital_query(place):
            for _, row in hospital_rapido_df.iterrows():
                hospital_name = get_hospital_name(row)

                if not strict_match(place, hospital_name):
                    continue

                rapido_details.append({
                    "place_type": "hospital",
                    "hospital_name": hospital_name,
                    "from_locality": safe_get(row, ["source_area", "From (Locality)", "from_locality"]),
                    "zone": safe_get(row, ["hospital_area", "Zone", "zone"]),
                    "beach_alias": safe_get(row, ["nearest_landmarks", "alias"]),
                    "approx_distance": safe_get(row, ["distance_km", "Approx Distance (km)"]),
                    "bike_base_fare": "",
                    "bike_per_km": "",
                    "bike_day_fare": safe_get(row, ["rapido_bike_price", "Rapido Bike – Day Fare (₹)"]),
                    "bike_night_fare": "",
                    "bike_time": safe_get(row, ["estimated_duration", "Rapido Bike – Est. Travel Time"]),
                    "auto_base_fare": "",
                    "auto_per_km": "",
                    "auto_day_fare": safe_get(row, ["auto_price", "Rapido Auto – Day Fare (₹)"]),
                    "auto_night_fare": "",
                    "auto_time": safe_get(row, ["estimated_duration", "Rapido Auto – Est. Travel Time"]),
                    "cab_base_fare": "",
                    "cab_per_km": "",
                    "cab_day_fare": safe_get(row, ["cab_price", "Rapido Cab – Day Fare (₹)"]),
                    "cab_night_fare": "",
                    "cab_time": safe_get(row, ["estimated_duration", "Rapido Cab – Est. Travel Time"]),
                    "cheapest_option": safe_get(row, ["best_transport_option", "Cheapest Option"]),
                    "day_fare_summary": safe_get(row, ["description", "Day Fare Summary (Bike/Auto/Cab)"]),
                    "rapido_app": "",
                })


        elif is_theater_query(place):
            for _, row in theater_rapido_df.iterrows():
                theater_name = get_theater_name(row)

                if not strict_match(place, theater_name):
                    continue

                rapido_details.append({
                    "place_type": "theater",
                    "theater_name": theater_name,
                    "from_locality": safe_get(row, ["source_area", "From (Locality)", "from_locality"]),
                    "zone": safe_get(row, ["theater_area", "theatre_area", "Zone", "zone"]),
                    "beach_alias": safe_get(row, ["nearest_landmarks", "alias"]),
                    "approx_distance": safe_get(row, ["distance_km", "Approx Distance (km)"]),
                    "bike_base_fare": "",
                    "bike_per_km": "",
                    "bike_day_fare": safe_get(row, ["rapido_bike_price", "Rapido Bike – Day Fare (₹)"]),
                    "bike_night_fare": "",
                    "bike_time": safe_get(row, ["estimated_duration", "Rapido Bike – Est. Travel Time"]),
                    "auto_base_fare": "",
                    "auto_per_km": "",
                    "auto_day_fare": safe_get(row, ["auto_price", "Rapido Auto – Day Fare (₹)"]),
                    "auto_night_fare": "",
                    "auto_time": safe_get(row, ["estimated_duration", "Rapido Auto – Est. Travel Time"]),
                    "cab_base_fare": "",
                    "cab_per_km": "",
                    "cab_day_fare": safe_get(row, ["cab_price", "Rapido Cab – Day Fare (₹)"]),
                    "cab_night_fare": "",
                    "cab_time": safe_get(row, ["estimated_duration", "Rapido Cab – Est. Travel Time"]),
                    "cheapest_option": safe_get(row, ["best_transport_option", "Cheapest Option"]),
                    "day_fare_summary": safe_get(row, ["description", "Day Fare Summary (Bike/Auto/Cab)"]),
                    "rapido_app": "",
                })


        return await localize_response({"rapido": rapido_details}, language)

    except Exception as e:
        traceback.print_exc()
        return await localize_response({"rapido": [], "error": str(e)}, language)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
    )