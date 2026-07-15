from __future__ import annotations

import traceback

from fastapi import APIRouter

from app.data.csv_loader import (
    fix_single_column_csv_df,
    load_csv,
    load_first_existing_csv,
    safe_get,
)
from app.services.translation_service import localize_response


router = APIRouter(tags=["transport"])


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





@router.get("/transport")
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


@router.get("/walking")
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


@router.get("/rapido")
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