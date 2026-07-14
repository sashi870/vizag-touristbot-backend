import re
import csv
import os
import requests
import pandas as pd

from rapidfuzz import fuzz

from app.data_loader import (
    beaches,
    cafes,
    restaurants,
    parks,
    temples,
    museums,
    hospitals,
    theaters,
    waterfalls,
    valleys,
    pubs,
    colleges
)

DEFAULT_CONVERSATION_STATE = {
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


def ensure_conversation_state(state=None):
    """Return a validated per-user/session state dictionary.

    The caller owns this dictionary and persists it in SQLite/Redis.
    No mutable conversation data is stored at module level.
    """
    if not isinstance(state, dict):
        state = {}

    for key, default in DEFAULT_CONVERSATION_STATE.items():
        if key not in state:
            state[key] = list(default) if isinstance(default, list) else default

    if not isinstance(state.get("last_results"), list):
        state["last_results"] = []
    if not isinstance(state.get("last_places_list"), list):
        state["last_places_list"] = []
    if not isinstance(state.get("pending_ambiguous_categories"), list):
        state["pending_ambiguous_categories"] = []

    try:
        state["last_index"] = max(0, int(state.get("last_index", 0)))
    except (TypeError, ValueError):
        state["last_index"] = 0

    return state


def state_results_dataframe(state):
    records = state.get("last_results", [])
    if not isinstance(records, list) or not records:
        return pd.DataFrame()
    try:
        return pd.DataFrame(records)
    except Exception:
        return pd.DataFrame()


def store_results_dataframe(state, df):
    if df is None or df.empty:
        state["last_results"] = []
        return

    safe_df = df.reset_index(drop=True).copy()
    safe_df = safe_df.where(pd.notna(safe_df), None)
    state["last_results"] = safe_df.to_dict(orient="records")[:100]

PAGE_SIZE = 30  # show 30 results for heavy categories; beaches are shown fully below
FUZZY_LOCATION_SCORE = 75
STRICT_LOCATION_SCORE = 86

AREA_ALIASES = {
    "mvp": ["mvp", "mvp colony", "mvp double road", "sector 1", "sector 2", "sector 3"],
    "mvp colony": ["mvp", "mvp colony", "mvp double road", "sector 1", "sector 2", "sector 3"],
    "kommadi": ["kommadi", "kapuluppada", "madhurawada", "rushikonda", "yendada"],
    "gajuwaka": ["gajuwaka", "new gajuwaka", "old gajuwaka", "autonagar", "kurmannapalem"],
    "rk beach": ["rk beach", "ramakrishna beach", "beach road", "siripuram", "pandurangapuram"],
    "ramakrishna beach": ["rk beach", "ramakrishna beach", "beach road", "siripuram", "pandurangapuram"],
    "rushikonda": ["rushikonda", "rushikonda beach", "yendada", "sagar nagar", "madhurawada"],
    "nad": ["nad", "nad junction", "gopalapatnam", "airport"],
    "dwaraka nagar": ["dwaraka nagar", "rtc complex", "diamond park"],
    "siripuram": ["siripuram", "waltair", "beach road", "pandurangapuram"],
    "bheemili": ["bheemili", "bheemunipatnam", "tagarapuvalasa", "chittivalasa"],
    "bheemunipatnam": ["bheemili", "bheemunipatnam", "tagarapuvalasa", "chittivalasa"],
}

NEARBY_BEACHES_BY_AREA = {
    "kommadi": ["Kapuluppada Beach", "Rushikonda Beach", "Mangamaripeta Beach", "Thotlakonda Beach", "Bheemunipatnam Beach"],
    "mvp": ["Ramakrishna Beach", "Lawson's Bay Beach", "Rushikonda Beach", "Sagar Nagar Beach"],
    "mvp colony": ["Ramakrishna Beach", "Lawson's Bay Beach", "Rushikonda Beach", "Sagar Nagar Beach"],
    "gajuwaka": ["Gangavaram Beach", "Appikonda Beach", "Yarada Beach", "Ramakrishna Beach"],
    "rk beach": ["Ramakrishna Beach", "Lawson's Bay Beach", "Rushikonda Beach"],
    "ramakrishna beach": ["Ramakrishna Beach", "Lawson's Bay Beach", "Rushikonda Beach"],
    "rushikonda": ["Rushikonda Beach", "Sagar Nagar Beach", "Mangamaripeta Beach", "Kapuluppada Beach"],
    "bheemili": ["Bheemunipatnam Beach", "Mangamaripeta Beach", "Kapuluppada Beach", "Rushikonda Beach"],
    "bheemunipatnam": ["Bheemunipatnam Beach", "Mangamaripeta Beach", "Kapuluppada Beach", "Rushikonda Beach"],
}

EXCLUDED_BY_CATEGORY = {
    "hospitals": ["restaurant", "hotel", "apartment", "college", "school", "food", "kitchen", "ruchulu"],
    "restaurants": ["hospital", "clinic", "college", "school", "apartment"],
    "cafes": ["hospital", "clinic", "college", "school"],
}

REQUIRED_BY_CATEGORY = {
    "hospitals": ["hospital", "clinic", "medical", "doctor", "dental", "eye", "health", "dispensary", "care", "pharmacy"],
}



BASE_DIR = os.path.dirname(os.path.abspath(__file__))
APP_DIR = os.path.abspath(os.path.join(BASE_DIR, ".."))
DATASETS_DIR = os.path.join(APP_DIR, "datasets")

BEACH_NAME_ALIASES = {
    "mutyalammapalem": ["mutyalammapalem", "mutyalampalem", "muthyalammapalem", "muthyalampalem", "mutyala palem", "mutyala m palem"],
    "mutyalampalem": ["mutyalammapalem", "mutyalampalem", "muthyalammapalem", "muthyalampalem", "mutyala palem", "mutyala m palem"],
    "rk": ["rk", "rk beach", "ramakrishna", "ramakrishna beach"],
    "ramakrishna": ["rk", "rk beach", "ramakrishna", "ramakrishna beach"],
    "bheemili": ["bheemili", "bheemunipatnam", "bheemunipatnam beach"],
    "bheemunipatnam": ["bheemili", "bheemunipatnam", "bheemunipatnam beach"],
}


def load_transport_csv_file(possible_filenames):
    """Load a transport CSV from app/datasets using the first filename that exists."""
    for filename in possible_filenames:
        path = os.path.join(DATASETS_DIR, filename)
        if os.path.exists(path):
            try:
                df = pd.read_csv(path, encoding="utf-8-sig", engine="python", on_bad_lines="skip")
            except Exception:
                try:
                    df = pd.read_csv(path, encoding="latin1", engine="python", on_bad_lines="skip")
                except Exception as e:
                    print("TRANSPORT CSV LOAD ERROR:", filename, e)
                    continue

            df.columns = [str(c).strip().replace("\ufeff", "").replace("ï»¿", "").strip().strip('"') for c in df.columns]
            return fix_single_column_csv_df(df)

    return pd.DataFrame()


def normalize_route_text(value):
    value = str(value or "").lower().strip()
    value = value.replace("’", "'")
    value = value.replace("&", " and ")
    value = re.sub(r"[^a-z0-9]+", " ", value)
    value = re.sub(r"\s+", " ", value).strip()
    return value


def normalize_beach_for_match(value):
    value = normalize_route_text(value)
    value = re.sub(r"\bbeaches\b|\bbeach\b", " ", value)
    value = re.sub(r"\bvizag\b|\bvisakhapatnam\b", " ", value)
    value = re.sub(r"\s+", " ", value).strip()
    return value


def expand_beach_alias_terms(value):
    clean = normalize_beach_for_match(value)
    terms = [clean]
    for key, aliases in BEACH_NAME_ALIASES.items():
        if clean == key or key in clean or clean in aliases:
            terms.extend(aliases)
    out = []
    for term in terms:
        term = normalize_beach_for_match(term)
        if term and term not in out:
            out.append(term)
    return out


def extract_route_source_destination(query, state):
    """Extract source and destination from queries like 'bus details from Kommadi to Mutyalammapalem Beach'."""
    q = str(query or "").strip()
    q_low = q.lower()

    patterns = [
        r"(?:bus details|bus route|apsrtc bus|apsrtc|bus|route|how to go)\s+from\s+(.+?)\s+to\s+(.+)$",
        r"from\s+(.+?)\s+to\s+(.+)$",
        r"(?:bus details|bus route|apsrtc bus|apsrtc|bus|route|how to go)\s+(?:to|for)\s+(.+)$",
    ]

    for pattern in patterns:
        match = re.search(pattern, q_low, flags=re.I)
        if match:
            if len(match.groups()) == 2:
                source = clean_location_text(match.group(1)) or match.group(1).strip()
                destination = match.group(2).strip()
            else:
                source = current_location_from_query(q) or state.get("last_location_context")
                destination = match.group(1).strip()

            destination = re.sub(r"\b(bus details|bus route|apsrtc|bus|route|please|pls)\b", " ", destination, flags=re.I)
            destination = re.sub(r"[?.!,]+$", "", destination).strip()
            return source, destination

    return None, None


def current_location_from_query(query):
    q = str(query or "").lower()
    match = re.search(r"\b(?:near|at|in)\s+([a-z ]+)$", q)
    if match:
        return clean_location_text(match.group(1))
    return None


def find_best_beach_bus_rows(bus_df, destination, source=""):
    if bus_df is None or bus_df.empty or not destination:
        return pd.DataFrame()

    beach_col = None
    for col in ["Beach Name", "beach_name", "Beach", "Destination Beach", "Destination", "Place Name", "place_name", "name", "Name"]:
        if col in bus_df.columns:
            beach_col = col
            break

    if not beach_col:
        return pd.DataFrame()

    destination_terms = expand_beach_alias_terms(destination)

    matched_indices = []
    best_score = 0
    best_indices = []

    for idx, row in bus_df.iterrows():
        beach_name = safe_get(row, [beach_col], "")
        row_terms = expand_beach_alias_terms(beach_name)
        row_text_value = normalize_route_text(" ".join(str(v) for v in row.values if pd.notna(v)))

        score = 0
        exact_match = False
        for d_term in destination_terms:
            for r_term in row_terms:
                if d_term and r_term:
                    if d_term == r_term or d_term in r_term or r_term in d_term:
                        exact_match = True
                        score = 100
                    else:
                        score = max(score, fuzz.partial_ratio(d_term, r_term))
            if d_term and d_term in row_text_value:
                exact_match = True
                score = max(score, 96)

        if exact_match or score >= 82:
            matched_indices.append(idx)
        elif score > best_score:
            best_score = score
            best_indices = [idx]
        elif score == best_score:
            best_indices.append(idx)

    if matched_indices:
        matched = bus_df.loc[matched_indices].copy()
    elif best_score >= 74 and best_indices:
        matched = bus_df.loc[best_indices].copy()
    else:
        return pd.DataFrame()

    source_clean = normalize_route_text(source)
    if source_clean and source_clean not in ["current location", "location"]:
        source_matches = []
        for idx, row in matched.iterrows():
            row_text_value = normalize_route_text(" ".join(str(v) for v in row.values if pd.notna(v)))
            if source_clean in row_text_value or fuzz.partial_ratio(source_clean, row_text_value) >= 82:
                source_matches.append(idx)
        if source_matches:
            matched = matched.loc[source_matches]

    return matched.head(5)


def format_apsrtc_bus_details(rows, source, destination):
    if rows is None or rows.empty:
        return [{"message": f"No APSRTC bus details found for {str(destination).title()}."}]

    destination_name = safe_get(rows.iloc[0], ["Beach Name", "Destination Beach", "Destination", "Place Name", "name", "Name"], destination)
    lines = [
        "APSRTC Bus Details",
        f"From: {str(source or 'Current Location').title()}",
        f"To: {destination_name}",
        ""
    ]

    for i, (_, row) in enumerate(rows.iterrows(), start=1):
        route_no = safe_get(row, ["Bus Route No", "Route No", "route_no", "bus_no", "Bus No"], "N/A")
        route_desc = safe_get(row, ["Route Description (From → To)", "Route Description", "Route", "route", "route_description"], "")
        starting = safe_get(row, ["Starting Point", "Start", "source", "Source", "From"], "")
        ending = safe_get(row, ["Ending Point", "End", "destination", "Destination", "To"], "")
        via = safe_get(row, ["Key Stops (Via)", "Via", "via", "Key Stops", "stops"], "")
        fare = safe_get(row, ["Approx Fare (₹)", "Fare", "fare", "Approx Fare", "ticket_price"], "")
        time = safe_get(row, ["Journey Time", "Time", "duration", "Duration"], "")
        frequency = safe_get(row, ["Frequency", "frequency"], "")
        first_bus = safe_get(row, ["First Bus", "first_bus"], "")
        last_bus = safe_get(row, ["Last Bus", "last_bus"], "")
        alight = safe_get(row, ["Alight At (Beach Stop)", "Alight At", "Beach Stop", "bus_stop", "Stop"], "")
        direct = safe_get(row, ["Direct Bus?", "Direct", "direct_bus"], "")
        tips = safe_get(row, ["Last Mile Tips", "Tips", "last_mile", "Last Mile"], "")

        lines.append(f"Option {i}")
        if route_no: lines.append(f"Route No: {route_no}")
        if route_desc: lines.append(f"Route: {route_desc}")
        elif starting or ending: lines.append(f"Route: {starting} → {ending}")
        if via: lines.append(f"Via: {via}")
        if fare: lines.append(f"Approx Fare: ₹{str(fare).replace('₹', '').strip()}")
        if time: lines.append(f"Journey Time: {time}")
        if frequency: lines.append(f"Frequency: {frequency}")
        if first_bus or last_bus: lines.append(f"Timings: {first_bus} to {last_bus}".strip())
        if alight: lines.append(f"Get Down At: {alight}")
        if direct: lines.append(f"Direct Bus: {direct}")
        if tips: lines.append(f"Last Mile Tip: {tips}")
        lines.append("")

    if source and normalize_route_text(source) not in normalize_route_text(" ".join(lines)):
        lines.append(f"Note: I found confirmed APSRTC routes for {destination_name}. If there is no direct bus from {str(source).title()}, first reach the nearest main boarding point shown above and continue from there.")

    return [{"message": "\n".join(lines).strip()}]


def handle_apsrtc_bus_query(query, state):
    q = str(query or "").lower()
    if not any(word in q for word in ["bus", "apsrtc", "route no", "route number"]):
        return None

    # Currently this fixes beach APSRTC lookup, including Mutyalammapalem / Mutyalampalem spelling variations.
    if "beach" not in q and not any(alias in q for alias in ["mutyalammapalem", "mutyalampalem", "rk", "rushikonda", "yarada", "bheemili", "bheemunipatnam", "kapuluppada"]):
        return None

    source, destination = extract_route_source_destination(query, state)
    if not destination:
        return None

    if not source:
        return [{"message": (
            "Please tell me your starting location.\n"
            "Example: Bus details from Gajuwaka to RK Beach"
        )}]

    beach_bus_df = load_transport_csv_file([
        "beachesapsrtc.csv",
        "beachesapsrtc (2).csv",
        "beachesapsrtc(2).csv",
        "beachesapsrtc - Copy.csv",
        "beaches_apsrtc.csv",
        "beach_apsrtc_buses.csv",
        "apstrcbusesbuses.csv",
        "apstrcbusesbuses(4).csv",
    ])

    if beach_bus_df is None or beach_bus_df.empty:
        return [{"message": "Beach APSRTC CSV file was not found in app/datasets. Please keep beachesapsrtc.csv inside backend/app/datasets."}]

    rows = find_best_beach_bus_rows(beach_bus_df, destination, source)
    return format_apsrtc_bus_details(rows, source or "Current Location", destination)


def fix_single_column_csv_df(df):
    if df is None or df.empty:
        return df

    df = df.copy()
    df.columns = [
        str(c).strip().replace("\ufeff", "").replace("ï»¿", "").strip().strip('"')
        for c in df.columns
    ]

    if len(df.columns) != 1:
        return df

    first_col = df.columns[0]

    if "," not in first_col:
        return df

    try:
        headers = next(csv.reader([first_col]))
        fixed_rows = []

        for value in df[first_col].dropna().astype(str).tolist():
            value = value.strip()

            if value.startswith('"') and value.endswith('"'):
                value = value[1:-1]

            value = value.replace('""', '"')
            row = next(csv.reader([value]))

            if len(row) < len(headers):
                row = row + [""] * (len(headers) - len(row))
            elif len(row) > len(headers):
                row = row[:len(headers)]

            fixed_rows.append(row)

        fixed_df = pd.DataFrame(fixed_rows, columns=headers)
        fixed_df.columns = [
            str(c).strip().replace("\ufeff", "").replace("ï»¿", "").strip().strip('"')
            for c in fixed_df.columns
        ]
        return fixed_df

    except Exception as e:
        print("CSV FIX ERROR:", e)
        return df


def ask_ollama(query):
    """Fallback AI answer when the dataset cannot answer directly."""
    try:
        response = requests.post(
            "http://localhost:11434/api/generate",
            json={
                "model": "phi3",
                "prompt": f"""
You are Vizag AI Travel Assistant, a friendly ChatGPT-like travel helper for Visakhapatnam.

Rules:
- Understand normal human questions like greetings, nearby places, budgets, routes, and trip planning.
- Answer clearly in short paragraphs or bullets.
- If the question is about Vizag, beaches, restaurants, hospitals, temples, parks, transport, routes, budgets, safety, or planning, help directly.
- If exact live data is needed, say that details may vary and suggest checking maps/calling the place.
- Do not say you are only a dataset bot.

User question:
{query}
""",
                "stream": False
            },
            timeout=25
        )

        data = response.json()
        answer = data.get("response", "AI not responding.")
        return clean_display_text(answer).replace("<br>", "\n")

    except Exception as e:
        print("OLLAMA ERROR:", e)
        return "I can help with Vizag places, routes, nearby searches and trip planning. Ask me about beaches, hospitals, restaurants, routes, budget, or places to visit in Vizag."


def smart_local_answer(query):
    """Useful ChatGPT-like answers that do not depend on Ollama."""
    q = str(query or "").lower().strip()

    if any(phrase in q for phrase in [
        "what can i do in vizag", "things to do in vizag", "what to do in vizag",
        "places to visit", "trip plan", "plan a trip", "visit in vizag"
    ]):
        return [{
            "message": (
                "You can enjoy Vizag like this:\n"
                "1. Beaches: RK Beach, Rushikonda, Yarada, Bheemili.\n"
                "2. Viewpoints: Kailasagiri, Tenneti Park, Dolphin's Nose.\n"
                "3. Museums: Submarine Museum, Aircraft Museum, Sea Harrier Museum.\n"
                "4. Food: beach-road restaurants, seafood, biryani, cafes.\n"
                "5. Spiritual places: Simhachalam Temple and local temples.\n"
                "Ask me like: 'beaches near Kommadi', 'restaurants near MVP', or 'bus details to RK Beach'."
            )
        }]

    if any(phrase in q for phrase in ["what is vizag famous", "vizag famous for", "about vizag"]):
        return [{
            "message": (
                "Vizag is famous for beaches, hills, ports, seafood, temples, museums, and scenic drives. "
                "Popular spots include RK Beach, Rushikonda Beach, Kailasagiri, Simhachalam Temple, Submarine Museum, and Yarada Beach."
            )
        }]

    if any(phrase in q for phrase in ["best time", "when to visit", "season"]):
        return [{
            "message": "Best time to visit Vizag is usually October to March. Weather is cooler and better for beaches, parks, temples, and sightseeing."
        }]

    if any(phrase in q for phrase in ["safe", "safety", "night safe"]):
        return [{
            "message": "Vizag is generally tourist-friendly, but for safety use main roads at night, avoid isolated beaches after dark, keep emergency contacts, and use trusted transport apps."
        }]

    if any(phrase in q for phrase in ["budget", "cost for trip", "how much money", "trip cost"]):
        return [{
            "message": (
                "For a simple Vizag day trip, keep around ₹500–₹1500 per person depending on food and transport. "
                "Beach visits are mostly low-cost; museums, cabs, cafes and restaurants increase the budget."
            )
        }]

    return None


def extract_name(query, state):
    patterns = [
        r"call me (.+)",
        r"my name is (.+)",
        r"i am (.+)",
        r"i'm (.+)"
    ]

    for pattern in patterns:
        match = re.search(pattern, query.lower())

        if match:
            state["user_name"] = match.group(1).strip().title()
            return [{
                "message": f"Hey {state['user_name']} 😊 Nice to meet you!"
            }]

    return None
def handle_greetings(query, state):
    q = query.lower().strip()

    greetings = [
        "hi", "hii", "hiii", "hello", "helo", "hey", "heyy",
        "good morning", "good afternoon", "good evening", "good night",
        "namaste", "namaskar", "vanakkam", "నమస్తే", "హాయ్", "హలో",
        "नमस्ते", "हाय", "हेलो", "வணக்கம்", "ಹಾಯ್", "ನಮಸ್ಕಾರ"
    ]

    if q in greetings or re.fullmatch(r"(hi+|hello+|hey+)", q):
        return [{
            "message": f"Hello {state['user_name']} 😊 I can help like a normal assistant. Ask me about nearby hospitals, restaurants near an area, beaches between places, routes, budget, or anything about Vizag."
        }]

    return None


def handle_small_talk(query, state):
    q = query.lower().strip()

    if any(word in q for word in ["thanks", "thank you", "tq", "ధన్యవాదాలు", "शुक्रिया"]):
        return [{"message": f"You're welcome {state['user_name']} ❤️"}]

    if any(word in q for word in ["bye", "goodbye", "see you", "బై", "अलविदा"]):
        return [{"message": f"Bye {state['user_name']} 👋 Have a safe Vizag trip!"}]

    if "how are you" in q or "how r u" in q or "మీరు ఎలా" in q:
        return [{"message": f"I'm doing great {state['user_name']} 😊 Tell me what you need in Vizag."}]

    if any(phrase in q for phrase in ["what can you do", "help me", "how can you help", "features"]):
        return [{
            "message": "I can help with beaches, restaurants, cafes, temples, parks, hospitals, theaters, nightlife, nearby searches, route details, budget planning, and general Vizag travel questions."
        }]

    return None


def detect_category(query):
    q = query.lower()

    # IMPORTANT:
    # Check theaters BEFORE restaurants.
    # Also use word-boundary matching so "eat" does not match inside "theaters".
    category_keywords = {
        "theaters": ["theater", "theaters", "theatre", "theatres", "cinema", "cinemas", "movie", "movies", "multiplex", "inox", "pvr", "screen", "show", "talkies"],
        "cafes": ["cafe", "cafes", "coffee", "tea", "bakery", "snacks"],
        "restaurants": ["restaurant", "restaurants", "food", "foods", "dinner", "lunch", "breakfast", "biryani", "meals", "hotel", "dhaba", "tiffin"],
        "parks": ["park", "parks", "garden", "play area"],
        "temples": ["temple", "temples", "mandir", "darshan", "pooja", "god", "deity", "devotional"],
        "museums": ["museum", "museums", "aquarium", "memorial", "aircraft", "submarine", "kursura", "exhibition"],
        "hospitals": ["hospital", "hospitals", "clinic", "clinics", "medical", "healthcare", "doctor", "doctors", "emergency", "nearby hospital", "nearby hospitals"],
        "waterfalls": ["waterfall", "waterfalls", "falls"],
        "valleys": ["valley", "valleys", "hill station"],
        "pubs": ["pub", "pubs", "bar", "bars", "club", "clubs", "nightlife", "lounge", "restobar", "party"],
        "colleges": ["college", "colleges", "university", "engineering college", "campus"],
        "beaches": ["beach", "beaches", "sea", "seashore", "shore", "coast", "coastal"]
    }

    for category, keywords in category_keywords.items():
        for keyword in keywords:
            # Multi-word phrases and normal words must match as words, not substrings.
            if re.search(rf"(?<![a-z0-9]){re.escape(keyword)}(?![a-z0-9])", q):
                return category

    return None

def detect_intent(query):
    q = query.lower()

    if any(word in q for word in ["top", "best", "popular", "famous", "highest rated"]):
        return "top"

    if any(word in q for word in ["cheap", "budget", "low cost", "affordable", "less cost", "under", "below"]):
        return "budget"

    if any(word in q for word in ["near", "nearby", "around", "close to", "at ", "in "]):
        return "nearby"

    if "between" in q:
        return "between"

    return "normal"

def get_category_df(category):
    datasets = {
        "beaches": beaches,
        "cafes": cafes,
        "restaurants": restaurants,
        "parks": parks,
        "temples": temples,
        "museums": museums,
        "hospitals": hospitals,
        "theaters": theaters,
        "waterfalls": waterfalls,
        "valleys": valleys,
        "pubs": pubs,
        "colleges": colleges
    }

    df = datasets.get(category)

    if df is not None:
        df = fix_single_column_csv_df(df)

    return df


def clean_location_text(location):
    location = str(location or "").lower().strip()
    location = re.sub(r"[?.!,]+$", "", location)
    remove_words = [
        "vizag", "visakhapatnam", "please", "pls", "nearby", "near", "around",
        "hospitals", "hospital", "restaurants", "restaurant", "cafes", "cafe",
        "beaches", "beach", "parks", "park", "temples", "temple",
        "museums", "museum", "theaters", "theatre", "theatres", "cinema",
        "show", "find", "tell", "me", "give", "list", "best", "top", "all"
    ]
    for word in remove_words:
        location = re.sub(rf"\b{re.escape(word)}\b", " ", location)
    location = re.sub(r"\s+", " ", location).strip(" ,.-")
    return location or None



def expand_location_terms(location):
    clean = clean_location_text(location) or str(location or "").lower().strip()
    terms = [clean]
    for key, aliases in AREA_ALIASES.items():
        if clean == key or clean in aliases or key in clean:
            terms.extend(aliases)
    # unique preserve order
    out = []
    for t in terms:
        t = str(t or "").strip().lower()
        if t and t not in out:
            out.append(t)
    return out


def extract_between_locations(query):
    q = query.lower().strip()
    patterns = [
        r"between\s+(.+?)\s+(?:and|to)\s+(.+)$",
        r"from\s+(.+?)\s+to\s+(.+)$"
    ]
    for pattern in patterns:
        match = re.search(pattern, q)
        if match:
            first = clean_location_text(match.group(1))
            second = clean_location_text(match.group(2))
            if first and second:
                return first, second
    return None, None


def extract_location(query):
    q = query.lower().strip()

    # Handles: nearby hospitals at MVP, restaurants near RK Beach, cafes in Siripuram
    patterns = [
        r"(?:nearby|near|around|close to|at|in)\s+(.+)$",
        r"(?:from)\s+(.+)$"
    ]

    for pattern in patterns:
        match = re.search(pattern, q)
        if match:
            location = clean_location_text(match.group(1))
            if location and location not in ["vizag", "visakhapatnam"]:
                return location

    return None


def row_text(row):
    return " ".join(str(value).lower() for value in row.values if pd.notna(value))


def find_nearby_places(df, location):
    if df is None or df.empty or not location:
        return df

    terms = expand_location_terms(location)
    matched_rows = []

    for _, row in df.iterrows():
        full_text = row_text(row)
        best_score = max([fuzz.partial_ratio(term, full_text) for term in terms] or [0])
        exact = any(term in full_text for term in terms)

        # Area searches must be stricter to avoid MVP returning Bheemili.
        if exact or best_score >= STRICT_LOCATION_SCORE:
            matched_rows.append(row)

    if matched_rows:
        return pd.DataFrame(matched_rows)

    return pd.DataFrame()



def find_between_places(df, place_a, place_b):
    if df is None or df.empty:
        return df

    first = find_nearby_places(df, place_a)
    second = find_nearby_places(df, place_b)

    frames = []
    if first is not None and not first.empty:
        frames.append(first)
    if second is not None and not second.empty:
        frames.append(second)

    if frames:
        combined = pd.concat(frames, ignore_index=True).drop_duplicates()
        return combined

    # Do not return unrelated full dataset for between searches.
    return pd.DataFrame()

def sort_top_places(df):
    if df.empty:
        return df

    rating_col = None

    for col in ["rating", "Rating", "totalScore", "TotalScore", "score", "Score"]:
        if col in df.columns:
            rating_col = col
            break

    if rating_col:
        df[rating_col] = pd.to_numeric(df[rating_col], errors="coerce").fillna(0)
        return df.sort_values(by=rating_col, ascending=False)

    return df


def safe_get(row, keys, default=""):
    for key in keys:
        if key in row and pd.notna(row[key]):
            value = str(row[key]).strip()

            if value and value.lower() != "nan":
                return value

    return default


def get_category_text(row):
    category_values = []

    category_keys = [
        "categories",
        "category",
        "Category",
        "categoryName",
        "Category Name",
        "museumType",
        "museum_type",
        "hospitalType",
        "hospital_type",
        "screenType",
        "screen_type",
        "categories/0",
        "categories/1",
        "categories/2",
        "categories/3",
        "categories/4",
        "categories/5",
        "categories/6",
        "categories/7",
        "categories/8",
        "categories/9"
    ]

    seen = set()
    for key in category_keys:
        value = safe_get(row, [key], "")

        if value:
            for part in str(value).split(","):
                clean = part.strip()
                low = clean.lower()
                if clean and low not in seen:
                    seen.add(low)
                    category_values.append(clean)

    return ", ".join(category_values)


def clean_text(value):
    return (
        str(value)
        .lower()
        .replace("beach", "")
        .replace("restaurant", "")
        .replace("restaurants", "")
        .replace("cafe", "")
        .replace("cafes", "")
        .replace("park", "")
        .replace("parks", "")
        .replace("garden", "")
        .replace("temple", "")
        .replace("temples", "")
        .replace("mandir", "")
        .replace("museum", "")
        .replace("museums", "")
        .replace("aquarium", "")
        .replace("memorial", "")
        .replace("aircraft", "")
        .replace("submarine", "")
        .replace("hospital", "")
        .replace("hospitals", "")
        .replace("clinic", "")
        .replace("medical", "")
        .replace("healthcare", "")
        .replace("pub", "")
        .replace("pubs", "")
        .replace("bar", "")
        .replace("bars", "")
        .replace("club", "")
        .replace("clubs", "")
        .replace("lounge", "")
        .replace("nightlife", "")
        .replace("theater", "")
        .replace("theaters", "")
        .replace("theatre", "")
        .replace("theatres", "")
        .replace("cinema", "")
        .replace("cinemas", "")
        .replace("movie", "")
        .replace("movies", "")
        .replace("multiplex", "")
        .replace("talkies", "")
        .replace("inox", "")
        .replace("pvr", "")
        .replace("rk", "ramakrishna")
        .replace("&", "and")
        .replace("'", "")
        .replace("-", " ")
        .replace("_", " ")
        .strip()
    )


def is_general_category_query(query, category):
    query = query.lower().strip()

    general_queries = {
        "beaches": [
            "beach",
            "beaches",
            "vizag beaches",
            "beaches in vizag",
            "all beaches",
            "vizag beach"
        ],
        "restaurants": [
            "restaurant",
            "restaurants",
            "restaurants in vizag",
            "restaurant in vizag",
            "vizag restaurants",
            "food in vizag",
            "best restaurants",
            "top restaurants"
        ],
        "cafes": [
            "cafe",
            "cafes",
            "cafes in vizag",
            "vizag cafes"
        ],
        "parks": [
            "park",
            "parks",
            "parks in vizag",
            "vizag parks",
            "park in vizag",
            "all parks",
            "best parks",
            "top parks"
        ],
        "temples": [
            "temple",
            "temples",
            "temples in vizag",
            "temple in vizag",
            "vizag temples",
            "all temples",
            "best temples",
            "top temples"
        ],
        "museums": [
            "museum",
            "museums",
            "museums in vizag",
            "museum in vizag",
            "vizag museums",
            "all museums",
            "best museums",
            "top museums"
        ],
        "hospitals": [
            "hospital",
            "hospitals",
            "hospitals in vizag",
            "hospital in vizag",
            "vizag hospitals",
            "all hospitals",
            "best hospitals",
            "top hospitals",
            "clinics in vizag"
        ],
        "theaters": [
            "theater",
            "theaters",
            "theatre",
            "theatres",
            "cinema",
            "cinemas",
            "movie theaters",
            "movie theatres",
            "movies",
            "movies in vizag",
            "theaters in vizag",
            "theatres in vizag",
            "cinemas in vizag",
            "vizag theaters",
            "vizag theatres",
            "all theaters",
            "all theatres",
            "best theaters",
            "best theatres",
            "top theaters",
            "top theatres"
        ],
        "pubs": [
            "pub",
            "pubs",
            "bar",
            "bars",
            "club",
            "clubs",
            "nightlife",
            "lounge",
            "pubs in vizag",
            "bars in vizag",
            "clubs in vizag",
            "nightlife in vizag",
            "best pubs",
            "top pubs",
            "best bars",
            "top bars"
        ]
    }

    return query in general_queries.get(category, [])


def get_place_name(row):
    return safe_get(
        row,
        [
            "name",
            "Name",
            "title",
            "Title",
            "place_name",
            "Place Name",

            "restaurant_name",
            "Restaurant Name",

            "cafe_name",
            "Cafe Name",

            "museum_name",
            "Museum Name",

            "park_name",
            "Park Name",

            "temple_name",
            "Temple Name",

            "hospital_name",
            "Hospital Name",

            "theatreName",
            "theaterName",
            "Theatre Name",
            "Theater Name",
            "theatre_name",
            "theater_name",
            "cinema_name",
            "Cinema Name",

            "college_name",
            "College Name",

            "pub_name",
            "Pub Name"
        ],
        "Unknown Place"
    )


def search_single_place(df, query, category):
    if df is None or df.empty:
        return pd.DataFrame()

    clean_query = clean_text(query)
    matched_rows = []

    for _, row in df.iterrows():
        place_name = get_place_name(row)

        aliases = safe_get(
            row,
            [
                "aliases",
                "Aliases",
                "alias",
                "Alias"
            ],
            ""
        )

        full_text = f"{place_name} {aliases}"
        clean_full_text = clean_text(full_text)

        score = fuzz.partial_ratio(clean_query, clean_full_text)

        if (
            clean_query in clean_full_text
            or clean_full_text in clean_query
            or score >= 82
        ):
            matched_rows.append(row)

    if matched_rows:
        return pd.DataFrame(matched_rows)

    return pd.DataFrame()



def clean_display_text(value):
    """Remove noisy CSV artifacts from text shown in cards."""
    text = str(value or "")
    text = re.sub(r"https?://\S+", "", text)
    text = re.sub(r"www\.\S+", "", text)
    text = re.sub(r"query_place_id\s*=\s*[^,\s]+", "", text, flags=re.I)
    text = re.sub(r"\+91[\s\-]*\d[\d\s\-]{7,}\d", "", text)
    text = re.sub(r"\b\d+\.0\b", "", text)
    text = re.sub(r"\s*,\s*,+", ", ", text)
    text = re.sub(r"\s+", " ", text).strip(" ,.-")
    return text

def is_valid_category_row(row, category):
    text = row_text(row)
    name = get_place_name(row).lower()
    combined = f"{name} {text}"

    for bad in EXCLUDED_BY_CATEGORY.get(category, []):
        if bad in combined:
            return False

    required = REQUIRED_BY_CATEGORY.get(category, [])
    if required and not any(word in combined for word in required):
        return False

    return True


def filter_valid_category_rows(df, category):
    # Do not over-filter theaters because theater CSV column names vary a lot.
    # Otherwise "theaters in vizag" may return no records.
    if category == "theaters":
        return df

    if df is None or df.empty:
        return df
    valid_rows = []
    for _, row in df.iterrows():
        if is_valid_category_row(row, category):
            valid_rows.append(row)
    return pd.DataFrame(valid_rows) if valid_rows else pd.DataFrame()


def filter_beaches_by_area(df, location):
    clean = clean_location_text(location)
    wanted = NEARBY_BEACHES_BY_AREA.get(clean or "")
    if df is None or df.empty or not wanted:
        return pd.DataFrame()

    rows = []
    wanted_clean = [clean_text(x) for x in wanted]
    for _, row in df.iterrows():
        name = get_place_name(row)
        name_clean = clean_text(name)
        if any(w in name_clean or name_clean in w for w in wanted_clean):
            rows.append(row)
    return pd.DataFrame(rows) if rows else pd.DataFrame()



def format_places(df, category, location=None, more=False, state=None):
    state = ensure_conversation_state(state)

    df = fix_single_column_csv_df(df)
    df = filter_valid_category_rows(df, category)

    if df is None or df.empty:
        return [{
            "message": f"No {category} dataset found."
        }]

    if not more:
        state["last_category"] = category
        store_results_dataframe(state, df)
        state["last_index"] = 0

    last_results_df = state_results_dataframe(state)
    start = state["last_index"]

    # IMPORTANT SPEED FIX:
    # Beaches are a small list, so show all beaches.
    # Restaurants/cafes and other categories may contain 100+ rows; returning all
    # makes localtunnel/backend slow and causes "Backend failed".
    if category == "beaches":
        end = len(last_results_df)
    else:
        end = start + PAGE_SIZE

    places = last_results_df.iloc[start:end]

    if places.empty:
        return [{
            "message": f"Sorry {state['user_name']} 😅 No more results found."
        }]

    state["last_index"] = end

    if location:
        intro = f"Here are popular {category} near {location.title()} 😊"
    else:
        intro = f"Here are popular {category} in Vizag 😊"

    results = [{
        "message": intro
    }]

    displayed_place_names = []
    if location:
        state["last_location_context"] = location

    added_places = set()

    for _, row in places.iterrows():
        place_name = get_place_name(row)

        if place_name == "Unknown Place":
            continue

        if place_name.lower() in added_places:
            continue

        added_places.add(place_name.lower())
        displayed_place_names.append(place_name)

        rating = safe_get(
            row,
            [
                "rating",
                "Rating",
                "totalScore",
                "TotalScore",
                "score",
                "Score"
            ],
            "N/A"
        )

        map_url = safe_get(
            row,
            [
                "google_maps_url",
                "googleMapsUrl",
                "map_url",
                "url",
                "URL"
            ],
            "#"
        )

        image_url = safe_get(
            row,
            [
                "image_url",
                "Image URL",
                "image",
                "Image",
                "photo_url",
                "Photo URL"
            ],
            ""
        )

        street = safe_get(
            row,
            [
                "street",
                "Street",
                "address",
                "Address",
                "location",
                "Location",
                "Area/Location",
                "area_location",
                "Area Location"
            ],
            ""
        )

        city = safe_get(
            row,
            [
                "city",
                "City"
            ],
            ""
        )

        description = safe_get(
            row,
            [
                "description",
                "Description",
                "about",
                "About",
                "speciality",
                "Speciality"
            ],
            ""
        )

        opening_time = safe_get(
            row,
            [
                "openingTime",
                "Opening Time",
                "opening_time",
                "timings",
                "Timings",
                "morningShow"
            ],
            ""
        )

        closing_time = safe_get(
            row,
            [
                "closingTime",
                "Closing Time",
                "closing_time",
                "secondShow",
                "lateNightShow"
            ],
            ""
        )

        entry_fee = safe_get(
            row,
            [
                "entryFee",
                "Entry Fee",
                "entry_fee",
                "ticketPriceRange"
            ],
            ""
        )

        expected_budget = safe_get(
            row,
            [
                "expectedBudget",
                "Expected Budget",
                "expected_budget"
            ],
            ""
        )

        categories = get_category_text(row)

        if description:
            final_description = description

        elif categories and street:
            final_description = (
                f"{place_name} is famous for {categories}. Located at {street}, {city}."
            )

        elif categories:
            final_description = (
                f"{place_name} is famous for {categories}."
            )

        elif street:
            final_description = (
                f"{place_name} is located at {street}, {city}."
            )

        else:
            final_description = (
                f"{place_name} is a popular {category[:-1]} place in Vizag."
            )

        final_description = clean_display_text(final_description)

        if category in ["parks", "temples", "museums", "hospitals", "theaters"]:
            extra_lines = []

            if opening_time or closing_time:
                if closing_time:
                    extra_lines.append(f"Timings: {opening_time} - {closing_time}")
                else:
                    extra_lines.append(f"Timings: {opening_time}")

            if entry_fee:
                if category == "theaters":
                    extra_lines.append(f"Ticket Price: {entry_fee}")
                else:
                    extra_lines.append(f"Entry Fee: {entry_fee}")

            if expected_budget:
                extra_lines.append(f"Expected Budget: {expected_budget}")

            if extra_lines:
                final_description = final_description + "<br>" + "<br>".join(extra_lines)

        speech_text = (
            f"{place_name}. "
            f"{str(final_description).replace('<br>', '. ')}"
        )

        results.append({
            "name": place_name,
            "description": final_description,
            "rating": rating,
            "map_url": map_url,
            "image": image_url,
            "speech_text": speech_text
        })

    if displayed_place_names:
        state["last_places_list"] = displayed_place_names
        state["last_place_name"] = displayed_place_names[0]

    return results


def ordinal_to_index(query):
    q = str(query or "").lower()
    mapping = {
        "first": 0, "1st": 0, "one": 0, "1": 0,
        "second": 1, "2nd": 1, "two": 1, "2": 1,
        "third": 2, "3rd": 2, "three": 2, "3": 2,
        "fourth": 3, "4th": 3, "four": 3, "4": 3,
        "fifth": 4, "5th": 4, "five": 4, "5": 4,
    }
    for word, index in mapping.items():
        if re.search(rf"\b{re.escape(word)}\b", q):
            return index
    return None


def handle_conversation_followup(query, state):
    state = ensure_conversation_state(state)
    last_results_df = state_results_dataframe(state)
    last_category = state.get("last_category")
    last_place_name = state.get("last_place_name")

    q = str(query or "").lower().strip()

    if not q:
        return None

    # User says: first one / second one / tell me about first one
    if any(word in q for word in ["first", "second", "third", "fourth", "fifth", "1st", "2nd", "3rd", "4th", "5th"]):
        index = ordinal_to_index(q)
        if index is not None and last_results_df is not None and last_category and index < len(last_results_df):
            return format_places(last_results_df.iloc[[index]], last_category, state=state)

    # User says: tell me about it / details / more details
    if any(phrase in q for phrase in [
        "tell me about it", "tell me more", "more about it", "details", "detail",
        "about this", "about it", "explain it", "what about it"
    ]):
        if last_place_name:
            return [{
                "message": (
                    f"Sure. You were asking about {last_place_name}. "
                    f"You can click Details for speciality information, or ask me bus details, walking details, or bike auto cab details for {last_place_name}."
                )
            }]

    # User says: bus details / how to go / route / walking / cab, without repeating place name
    if any(phrase in q for phrase in [
        "bus details", "bus route", "how to go", "how can i go", "route", "walking",
        "walk", "cab", "auto", "bike", "transport", "directions"
    ]):
        if last_place_name:
            return [{
                "message": (
                    f"Okay. I understood you mean {last_place_name}. "
                    f"Use the transport buttons below the place card, or ask: Bus details to {last_place_name}, Walking details to {last_place_name}, or Bike Auto Cab details to {last_place_name}."
                )
            }]

    # User says only category after greeting
    if q in ["yes", "ok", "okay", "sure"]:
        if last_category:
            return [{"message": f"Sure 😊 Do you want top {last_category}, nearby {last_category}, or transport details for a place?"}]

    return None


def get_recommendations(query, language="English", state=None):
    """Return recommendations plus updated per-session state.

    Conversation state is supplied by the caller and must be persisted by the
    API layer. No user-specific state is stored in module-level variables.
    """
    state = ensure_conversation_state(state)

    original_query = str(query or "").strip()
    query = original_query.lower().strip()

    if not query:
        return [{"message": "Please ask me anything about Vizag 😊"}], state

    response = extract_name(original_query, state)
    if response:
        return response, state

    response = handle_greetings(original_query, state)
    if response:
        return response, state

    response = handle_small_talk(original_query, state)
    if response:
        return response, state

    response = smart_local_answer(original_query)
    if response:
        return response, state

    response = handle_conversation_followup(original_query, state)
    if response:
        return response, state

    response = handle_apsrtc_bus_query(original_query, state)
    if response:
        return response, state

    # Pagination: user can say more / next / show more.
    if any(word in query for word in ["more", "next", "show more", "another", "load more"]):
        last_category = state.get("last_category")
        last_results_df = state_results_dataframe(state)
        if last_category and not last_results_df.empty:
            return format_places(
                last_results_df,
                last_category,
                more=True,
                state=state,
            ), state
        return [{
            "message": "Tell me a category first, like restaurants in Vizag or hospitals near MVP."
        }], state

    category = detect_category(query)

    if category:
        df = get_category_df(category)

        if df is None or df.empty:
            return [{"message": f"No {category} dataset found."}], state

        df = filter_valid_category_rows(df, category)
        if df is None or df.empty:
            return [{"message": f"No clean {category} records found in dataset."}], state

        # Between-place query: hospitals between Gajuwaka and NAD, beaches between Kommadi and Bheemili, etc.
        place_a, place_b = extract_between_locations(query)
        if place_a and place_b:
            between_df = find_between_places(df, place_a, place_b)
            intro_location = f"{place_a.title()} and {place_b.title()}"
            return format_places(
                between_df,
                category,
                intro_location,
                state=state,
            ), state

        # Specific place query first, but do not mistakenly treat area queries as place names.
        location = extract_location(query)
        if location:
            state["last_location_context"] = location
        is_general = is_general_category_query(query, category) or bool(location)

        if not is_general:
            single_df = search_single_place(df, query, category)
            if not single_df.empty:
                return format_places(
                    single_df.head(1),
                    category,
                    state=state,
                ), state

        if location:
            if category == "beaches":
                nearby_df = filter_beaches_by_area(df, location)
                if nearby_df is None or nearby_df.empty:
                    nearby_df = find_nearby_places(df, location)
            else:
                nearby_df = find_nearby_places(df, location)

            if nearby_df is not None and not nearby_df.empty:
                df = nearby_df
            else:
                return [{
                    "message": (
                        f"I could not find exact {category} near {location.title()} in my CSV. "
                        f"Try another nearby area name, or ask '{category} in Vizag' to see all available results."
                    )
                }], state

        intent = detect_intent(query)
        if intent == "top":
            df = sort_top_places(df)

        return format_places(df, category, location, state=state), state

    # If user asks a normal ChatGPT-like question, use AI fallback.
    ai_response = ask_ollama(original_query)
    return [{"message": ai_response}], state



# ------------------- Ambiguous Place Detection -------------------
from rapidfuzz import fuzz

CATEGORIES = ["beaches", "restaurants", "cafes", "theaters", "parks", "temples", "museums", "hospitals", "pubs"]

def detect_ambiguous_place(query):
    """Check if a place name matches multiple categories using fuzzy matching."""
    matched_categories = []

    query_clean = clean_text(query)

    for category in CATEGORIES:
        df = get_category_df(category)
        if df is None or df.empty:
            continue

        for _, row in df.iterrows():
            place_name = get_place_name(row)
            aliases = safe_get(row, ["aliases", "Aliases", "alias", "Alias"], "")
            full_text = f"{place_name} {aliases}"
            clean_full_text = clean_text(full_text)
            score = fuzz.partial_ratio(query_clean, clean_full_text)
            if score >= 82:  # fuzzy threshold
                matched_categories.append(category)
                break  # only need one match per category

    return matched_categories


def get_recommendations_with_ambiguity(query, language="English", state=None):
    """Check ambiguous place names using the caller's per-session state."""
    state = ensure_conversation_state(state)
    ambiguous_categories = detect_ambiguous_place(query)

    if len(ambiguous_categories) > 1:
        state["pending_ambiguous_query"] = str(query or "").strip()
        state["pending_ambiguous_categories"] = ambiguous_categories
        categories_str = ", ".join(ambiguous_categories)
        return [{
            "message": (
                f"I found multiple types of places named '{query}'. "
                f"Please clarify which one you mean: {categories_str}."
            )
        }], state

    if len(ambiguous_categories) == 1:
        category = ambiguous_categories[0]
        df = get_category_df(category)
        single_df = search_single_place(df, query, category)
        if not single_df.empty:
            return format_places(
                single_df.head(1),
                category,
                state=state,
            ), state

    return get_recommendations(query, language, state=state)


def get_recommendations_with_session(query, language="English", state=None):
    """Resolve ambiguous follow-ups without any module-level session state."""
    state = ensure_conversation_state(state)
    query_clean = str(query or "").strip()

    pending_query = state.get("pending_ambiguous_query")
    pending_categories = state.get("pending_ambiguous_categories", [])

    if pending_query and pending_categories:
        user_response = query_clean.lower()
        clarified_categories = [
            category
            for category in pending_categories
            if category.lower() in user_response
        ]

        if clarified_categories:
            category = clarified_categories[0]
            df = get_category_df(category)
            single_df = search_single_place(df, pending_query, category)
            state["pending_ambiguous_query"] = None
            state["pending_ambiguous_categories"] = []

            if not single_df.empty:
                return format_places(
                    single_df.head(1),
                    category,
                    state=state,
                ), state
        else:
            return [{
                "message": (
                    "Please specify one of these categories: "
                    + ", ".join(pending_categories)
                )
            }], state

    ambiguous_categories = detect_ambiguous_place(query_clean)

    if len(ambiguous_categories) > 1:
        state["pending_ambiguous_query"] = query_clean
        state["pending_ambiguous_categories"] = ambiguous_categories
        return [{
            "message": (
                f"I found multiple types of places named '{query_clean}'. "
                "Please clarify which one you mean: "
                + ", ".join(ambiguous_categories)
                + "."
            )
        }], state

    if len(ambiguous_categories) == 1:
        category = ambiguous_categories[0]
        df = get_category_df(category)
        single_df = search_single_place(df, query_clean, category)
        if not single_df.empty:
            return format_places(
                single_df.head(1),
                category,
                state=state,
            ), state

    return get_recommendations(query_clean, language, state=state)