from __future__ import annotations

import re
import traceback

from fastapi import APIRouter

from app.data.csv_loader import (
    fix_single_column_csv_df,
    load_first_existing_csv,
    safe_get,
)
from app.services.translation_service import localize_response


router = APIRouter(tags=["details"])


speciality_files = {
    "beach": load_first_existing_csv([
        "beaches_speciality_budget.csv",
        "cleaned_vizag_beaches_combined(1).csv",
        "cleaned_vizag_beaches_combined.csv",
    ]),
    "restaurant": load_first_existing_csv([
        "restaurants_speciality_budget.csv",
    ]),
    "cafe": load_first_existing_csv([
        "cafes_speciality_budget.csv",
    ]),
    "temple": load_first_existing_csv([
        "temples_speciality_budget.csv",
        "temples_speciality_budget(1).csv",
    ]),
    "theater": load_first_existing_csv([
        "theaters_speciality_budget.csv",
        "theaters_speciality_budget(1).csv",
    ]),
    "park": load_first_existing_csv([
        "parks_speciality_budget.csv",
        "park_speciality_budget.csv",
        "aaa26e15-8b64-463e-8531-cd3bc8b0e8a1.csv",
    ]),
    "museum": load_first_existing_csv([
        "museum_speciality_budget.csv",
        "museums_speciality_budget.csv",
    ]),
    "hospital": load_first_existing_csv([
        "hospital_speciality_budget.csv",
        "hospitals_speciality_budget.csv",
        "8d178e25-97a8-465e-b947-8fcc530ff08d.csv",
    ]),
}


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
        "vizag", "visakhapatnam", "andhra", "pradesh",
    }
    tokens = normalize_detail_text(text).split()
    return [token for token in tokens if token and token not in stop_words]


def detect_detail_place_types(place):
    words = normalize_detail_text(place).split()

    if any(word in words for word in [
        "hospital", "hospitals", "clinic", "clinics", "medical",
        "healthcare", "dispensary", "pharmacy", "center",
    ]):
        return ["hospital"]

    if any(word in words for word in ["temple", "temples", "mandir", "devasthanam"]):
        return ["temple"]

    if any(word in words for word in ["beach", "beaches"]):
        return ["beach"]

    if any(word in words for word in ["park", "parks", "garden"]):
        return ["park"]

    if any(word in words for word in ["museum", "museums", "aquarium", "memorial"]):
        return ["museum"]

    if any(word in words for word in [
        "theater", "theatre", "cinema", "multiplex", "pvr", "inox",
    ]):
        return ["theater"]

    if any(word in words for word in ["cafe", "coffee", "bakery"]):
        return ["cafe"]

    if any(word in words for word in [
        "pub", "bar", "club", "lounge", "restobar", "brewery",
    ]):
        return ["pub"]

    if any(word in words for word in [
        "restaurant", "food", "biryani", "dhaba", "kitchen", "meals",
    ]):
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

    place_tokens = detail_tokens(place)
    row_tokens = detail_tokens(row_name)
    alias_tokens = detail_tokens(aliases)

    if not place_tokens or not row_tokens:
        return False

    place_set = set(place_tokens)
    row_set = set(row_tokens)
    alias_set = set(alias_tokens)

    if place_set.issubset(row_set):
        return True

    if alias_set and place_set.issubset(alias_set):
        return True

    if len(row_tokens) >= 2 and row_set.issubset(place_set):
        return True

    shorter, longer = sorted([place_norm, row_norm], key=len)
    return len(shorter) >= 12 and shorter in longer


def get_speciality_place_name(row):
    return safe_get(row, [
        "beach_name", "Beach Name",
        "Restaurant Name", "restaurant_name",
        "Cafe Name", "cafe_name",
        "Temple Name", "temple_name",
        "Park Name", "park_name",
        "Museum Name", "museum_name",
        "Hospital_Name", "Hospital Name", "hospital_name",
        "medical_centre_name", "Medical Centre Name",
        "Theater Name", "Theatre Name", "theater_name", "theatre_name",
        "theatreName", "theaterName",
        "name", "Name", "title", "Title", "place_name", "Place Name",
    ])


def get_speciality_aliases(row):
    return safe_get(row, [
        "aliases", "Aliases", "alias", "Alias",
        "Beach Alias", "beach_alias",
    ])


def clean_detail_value(value):
    value = "" if value is None else str(value).strip()
    if not value or value.lower() == "nan":
        return ""
    value = value.replace("â‚¹", "₹").replace("â€“", "–").replace("â€”", "—")
    return re.sub(r"\s+", " ", value).strip()


def first_value(row, keys, default=""):
    return clean_detail_value(safe_get(row, keys, default))


def clean_detail_label(label):
    label = "" if label is None else str(label).strip()
    return re.sub(r"^[^A-Za-z0-9]+\s*", "", label).strip()


def add_detail_line(lines, label, value):
    value = clean_detail_value(value)
    label = clean_detail_label(label)
    if value and label:
        lines.append(f"{label}: {value}")


def build_speciality_details(place_type, row, matched_rows=None):
    matched_rows = matched_rows or [row]
    place_name = get_speciality_place_name(row)

    speciality = first_value(row, [
        "Speciality", "speciality", "Specialty", "specialty",
        "beach_speciality", "Famous For", "famous_for",
    ], "No specialities found")
    category = first_value(row, ["Category", "category", "categories", "categories/0"])
    description = first_value(row, ["description", "Description", "about", "About"])
    address = first_value(row, [
        "Address", "address", "street", "Street", "Area", "area",
        "location", "Location",
    ])
    city = first_value(row, ["City", "city"])
    budget = first_value(row, [
        "Expected Budget Range",
        "Expected Budget (per person)",
        "Expected Budget (per person / family)",
        "expected_budget", "Expected Budget", "price_range_inr",
        "Ticket Price Range", "Budget", "Expected_Budget_INR_Lakhs",
        "Expected Budget INR Lakhs",
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

    best_time = first_value(row, [
        "Best Time to Visit", "best_time_to_visit", "Best Time",
    ])

    lines = []
    add_detail_line(lines, "Speciality", speciality)
    add_detail_line(lines, "Category", category)
    add_detail_line(lines, "Description", description)
    add_detail_line(lines, "Location", ", ".join(
        value for value in [address, city] if value
    ))
    add_detail_line(lines, "Expected Budget", budget)
    add_detail_line(lines, "Timings", timings)
    add_detail_line(lines, "Best Time", best_time)

    if place_type == "beach":
        add_detail_line(lines, "Item to Purchase", first_value(row, ["item_to_purchase"]))
        add_detail_line(lines, "Where to Buy", first_value(row, ["where_to_buy"]))
        add_detail_line(lines, "Water Sports", first_value(row, ["water_sports_available"]))
        add_detail_line(lines, "Food Available", first_value(row, ["food_available"]))
        add_detail_line(lines, "Family Friendly", first_value(row, ["family_friendly"]))
        add_detail_line(lines, "Safety Level", first_value(row, ["safety_level"]))
        add_detail_line(lines, "Crowd Level", first_value(row, ["crowd_level"]))

        purchase_items = []
        for match_row in matched_rows:
            item = first_value(match_row, ["item_to_purchase"])
            price = first_value(match_row, ["price_range_inr"])
            if item:
                purchase_items.append(f"{item}" + (f" ({price})" if price else ""))

        unique_items = list(dict.fromkeys(purchase_items))
        if unique_items:
            add_detail_line(lines, "Local Items", "; ".join(unique_items[:6]))

    elif place_type in {"restaurant", "cafe"}:
        add_detail_line(lines, "Best For", first_value(row, [
            "Best For", "bestFor", "best_for",
        ]))
        add_detail_line(lines, "Reviews", first_value(row, [
            "Reviews Count", "reviews_count",
        ]))

    elif place_type == "temple":
        add_detail_line(lines, "Main Deity", first_value(row, [
            "Main Deity", "mainDeity", "mainGod", "Main God",
        ]))
        add_detail_line(lines, "Darshan Fee", first_value(row, [
            "Darshan Fee", "darshanFee",
        ]))
        add_detail_line(lines, "Special Darshan / Archana Fee", first_value(row, [
            "Special Darshan / Archana Fee", "Special Darshan", "specialDarshanFee",
        ]))
        add_detail_line(lines, "Festivals", first_value(row, [
            "Festivals Celebrated", "festivals",
        ]))
        add_detail_line(lines, "Dress Code", first_value(row, ["Dress Code", "dressCode"]))
        add_detail_line(lines, "Parking", first_value(row, ["Parking", "parking"]))
        add_detail_line(lines, "Photography", first_value(row, [
            "Photography Allowed", "photography_allowed",
        ]))
        add_detail_line(lines, "Nearby Attractions", first_value(row, [
            "Nearby Attractions", "nearbyAttractions",
        ]))

    elif place_type == "theater":
        add_detail_line(lines, "Screen Type", first_value(row, ["Screen Type", "screenType"]))
        add_detail_line(lines, "Audio System", first_value(row, ["Audio System", "audioSystem"]))
        add_detail_line(lines, "Ticket Price", first_value(row, [
            "Ticket Price Range", "ticketPriceRange",
        ]))
        add_detail_line(lines, "Average Food Cost", first_value(row, ["Average Food Cost"]))
        add_detail_line(lines, "Food Availability", first_value(row, ["Food Availability"]))
        add_detail_line(lines, "Famous Food", first_value(row, ["Famous Food Items"]))
        add_detail_line(lines, "Best For", first_value(row, ["Best For", "bestFor"]))
        add_detail_line(lines, "Seating Type", first_value(row, ["Seating Type"]))
        add_detail_line(lines, "Parking", first_value(row, ["Parking"]))
        add_detail_line(lines, "Online Booking", first_value(row, ["Online Booking"]))
        add_detail_line(lines, "Crowd Level", first_value(row, ["Crowd Level"]))
        add_detail_line(lines, "Nearby Attractions", first_value(row, ["Nearby Attractions"]))

    elif place_type in {"park", "museum"}:
        add_detail_line(lines, "Best For", first_value(row, [
            "Best For", "bestFor", "best_for",
        ]))
        add_detail_line(lines, "Ticket Price", first_value(row, [
            "Ticket Price Range", "ticketPriceRange", "entryFee", "Entry Fee",
        ]))
        add_detail_line(lines, "Average Food Cost", first_value(row, ["Average Food Cost"]))
        add_detail_line(lines, "Food Availability", first_value(row, ["Food Availability"]))
        add_detail_line(lines, "Famous Food", first_value(row, ["Famous Food Items"]))
        add_detail_line(lines, "Crowd Level", first_value(row, [
            "Crowd Level", "crowdLevel",
        ]))

    elif place_type == "hospital":
        hospital_specialty = first_value(row, [
            "Specialty", "specialty", "Speciality", "speciality",
        ])
        hospital_budget = first_value(row, [
            "Expected_Budget_INR_Lakhs", "Expected Budget INR Lakhs",
            "Expected Budget", "expected_budget",
        ])
        hospital_city = first_value(row, ["City", "city"])
        hospital_state = first_value(row, ["State", "state"])

        add_detail_line(lines, "Specialty", hospital_specialty)
        if hospital_budget:
            if (
                "lakh" in hospital_budget.lower()
                or "₹" in hospital_budget
                or "rs" in hospital_budget.lower()
            ):
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
        "google_maps_url", "googleMapsUrl", "map_url", "url", "URL",
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
    search_order = preferred_types or list(speciality_files.keys())

    for place_type in search_order:
        dataframe = speciality_files.get(place_type)
        if dataframe is None or dataframe.empty:
            continue

        dataframe = fix_single_column_csv_df(dataframe)
        matched_rows = []

        for _, row in dataframe.iterrows():
            row_name = get_speciality_place_name(row)
            aliases = get_speciality_aliases(row)

            if row_name and speciality_match(place, row_name, aliases):
                matched_rows.append(row)

        if matched_rows:
            return build_speciality_details(
                place_type,
                matched_rows[0],
                matched_rows,
            )

    return {
        "name": place.title(),
        "rating": "N/A",
        "details": "No specialities found.",
        "map_url": "#",
        "specialities": [],
    }


@router.get("/details")
async def details_endpoint(
    place: str,
    category: str = "",
    language: str = "English",
):
    del category

    try:
        return await localize_response(
            get_speciality_details(place),
            language,
        )
    except Exception as exc:
        traceback.print_exc()
        return await localize_response(
            {
                "name": place,
                "rating": "N/A",
                "details": "Server error while loading details.",
                "map_url": "#",
                "specialities": [],
                "error": str(exc),
            },
            language,
        )


@router.get("/help")
async def help_desk(place: str, language: str = "English"):
    try:
        return await localize_response(
            get_speciality_details(place),
            language,
        )
    except Exception:
        traceback.print_exc()
        return await localize_response(
            {
                "name": place.title(),
                "rating": "N/A",
                "details": "Server error.",
                "map_url": "#",
                "specialities": [],
            },
            language,
        )