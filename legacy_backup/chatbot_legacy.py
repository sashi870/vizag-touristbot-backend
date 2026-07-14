from app.data_loader import *
import requests
import re
import pandas as pd
from bs4 import BeautifulSoup
from rapidfuzz import fuzz

# --------------------------------
# Global username
# --------------------------------
user_name = "Traveler"

# --------------------------------
# Pagination variables
# --------------------------------
last_category = None
last_results = None
last_index = 0
PAGE_SIZE = 5


# --------------------------------
# Save user's name
# --------------------------------
def extract_name(query):

    global user_name

    patterns = [
        r"call me (.+)",
        r"my name is (.+)",
        r"i am (.+)",
        r"i'm (.+)"
    ]

    for pattern in patterns:

        match = re.search(pattern, query.lower())

        if match:

            user_name = match.group(1).strip().title()

            return [{
                "message":
                f"Hey {user_name} 😊 Nice to meet you!"
            }]

    return None


# --------------------------------
# Greetings
# --------------------------------
def handle_greetings(query):

    greetings = [
        "hi",
        "hello",
        "hey",
        "good morning",
        "good evening",
        "namaste"
    ]

    if query.lower() in greetings:

        return [{
            "message":
            f"Hello {user_name} 😊 Ask me about places in Vizag."
        }]

    return None


# --------------------------------
# Small talk
# --------------------------------
def handle_small_talk(query):

    query = query.lower()

    if "how are you" in query:

        return [{
            "message":
            f"I'm doing great {user_name} 😊"
        }]

    elif "thanks" in query or "thank you" in query:

        return [{
            "message":
            f"You're welcome {user_name} ❤️"
        }]

    elif "bye" in query:

        return [{
            "message":
            f"Bye {user_name} 👋"
        }]

    return None


# --------------------------------
# Extract location
# --------------------------------
def extract_location(query):

    query = query.lower().strip()

    generic_locations = [
        "vizag",
        "visakhapatnam",
        "vizag city"
    ]

    if " in " in query:

        location = query.split(" in ")[1].strip()

        if location in generic_locations:
            return None

        return location

    elif " near " in query:

        location = query.split(" near ")[1].strip()

        if location in generic_locations:
            return None

        return location

    elif " around " in query:

        location = query.split(" around ")[1].strip()

        if location in generic_locations:
            return None

        return location

    elif " close to " in query:

        location = query.split(" close to ")[1].strip()

        if location in generic_locations:
            return None

        return location

    return None


# --------------------------------
# Get dataset
# --------------------------------
def get_dataset(category):

    datasets = {

        "restaurants": restaurants,
        "cafes": cafes,
        "beaches": beaches,
        "parks": parks,
        "waterfalls": waterfalls,
        "valleys": valleys,
        "pubs": pubs,
        "hospitals": hospitals,
        "colleges": colleges,
        "theaters": theaters,
        "hotels": hotels
    }

    return datasets.get(category)


# --------------------------------
# Detect category
# --------------------------------
def detect_category(query):

    query = query.lower()

    categories = {

        "restaurants": [
            "restaurant",
            "restaurants",
            "food"
        ],

        "cafes": [
            "cafe",
            "cafes",
            "coffee"
        ],

        "beaches": [
            "beach",
            "beaches"
        ],

        "parks": [
            "park",
            "parks"
        ],

        "waterfalls": [
            "waterfall",
            "waterfalls"
        ],

        "valleys": [
            "valley",
            "valleys"
        ],

        "pubs": [
            "pub",
            "bar",
            "club"
        ],

        "hospitals": [
            "hospital",
            "hospitals"
        ],

        "colleges": [
            "college",
            "colleges"
        ],

        "theaters": [
            "theater",
            "theaters",
            "movie",
            "cinema"
        ],

        "hotels": [
            "hotel",
            "hotels"
        ]
    }

    for category, keywords in categories.items():

        for keyword in keywords:

            if keyword in query:
                return category

    return None


# --------------------------------
# Detect intent
# --------------------------------
def detect_intent(query):

    query = query.lower()

    if "top" in query or "best" in query:
        return "top"

    elif "cheap" in query or "budget" in query:
        return "budget"

    return "normal"


# --------------------------------
# Search dataset
# --------------------------------
def search_dataset(df, location):

    if location is None:
        return df

    location = location.lower()

    # Fast direct filtering
    filtered = df[
        df.astype(str)
        .apply(
            lambda row:
            row.str.lower()
            .str.contains(location)
            .any(),
            axis=1
        )
    ]

    if not filtered.empty:
        return filtered

    # Fuzzy fallback
    matched_rows = []

    for _, row in df.iterrows():

        full_text = " ".join(
            str(value).lower()
            for value in row.values
        )

        score = fuzz.partial_ratio(
            location,
            full_text
        )

        if score >= 70:
            matched_rows.append(row)

    if matched_rows:
        return pd.DataFrame(matched_rows)

    return pd.DataFrame()


# --------------------------------
# Sort top places
# --------------------------------
def sort_top_places(df):

    if df.empty:
        return df

    if "rating" in df.columns:

        df["rating"] = pd.to_numeric(
            df["rating"],
            errors="coerce"
        ).fillna(0)

        return df.sort_values(
            by="rating",
            ascending=False
        )

    return df


# --------------------------------
# Sort budget places
# --------------------------------
def sort_budget_places(df):

    if "price_level" in df.columns:

        return df.sort_values(
            by="price_level",
            ascending=True
        )

    return df


# --------------------------------
# Google fallback scraping
# --------------------------------
def scrape_places(query):

    search_query = query.replace(" ", "+")

    url = f"https://www.google.com/search?q={search_query}+vizag"

    headers = {
        "User-Agent": "Mozilla/5.0"
    }

    try:

        response = requests.get(
            url,
            headers=headers,
            timeout=10
        )

        if response.status_code != 200:
            return []

        soup = BeautifulSoup(
            response.text,
            "html.parser"
        )

        results = []
        seen = set()

        listings = soup.find_all("h3")

        for item in listings:

            name = item.get_text(strip=True)

            if name and name not in seen:

                seen.add(name)

                results.append({

                    "name": name,
                    "rating": "N/A",
                    "map_url": "#"
                })

            if len(results) == 5:
                break

        return results

    except Exception as e:

        print("Scraping Error:", e)

        return []


# --------------------------------
# Format results
# --------------------------------
def format_results(df, category, location=None):

    global last_results
    global last_index
    global last_category

    last_results = df
    last_index = PAGE_SIZE
    last_category = category

    results = []

    if location:

        results.append({
            "message":
            f"Here are the best {category} near {location} 😊"
        })

    else:

        results.append({
            "message":
            f"Here are popular {category} in Vizag 😊"
        })

    for _, row in df.head(PAGE_SIZE).iterrows():

        results.append({

            "name":
            row.get("title", "Unknown Place"),

            "description":
            row.get(
                "description",
                "Popular place in Vizag"
            ),

            "rating":
            row.get("rating", "N/A"),

            "map_url":
            row.get("url", "#"),

            "image":
            row.get("image", "")
        })

    return results


# --------------------------------
# Show more results
# --------------------------------
def show_more_results():

    global last_results
    global last_index

    if last_results is None:

        return [{
            "message":
            "No previous search found 😊"
        }]

    next_df = last_results.iloc[
        last_index:last_index + PAGE_SIZE
    ]

    if next_df.empty:

        return [{
            "message":
            "No more places found 😊"
        }]

    last_index += PAGE_SIZE

    results = []

    for _, row in next_df.iterrows():

        results.append({

            "name":
            row.get("title", "Unknown Place"),

            "description":
            row.get(
                "description",
                "Popular place in Vizag"
            ),

            "rating":
            row.get("rating", "N/A"),

            "map_url":
            row.get("url", "#"),

            "image":
            row.get("image", "")
        })

    return results


# --------------------------------
# Ollama AI fallback
# --------------------------------
def generate_ai_response(user_query):

    prompt = f"""
You are a Vizag tourism assistant.

User:
{user_query}

Assistant:
"""

    try:

        response = requests.post(

            "http://localhost:11434/api/generate",

            json={

                "model": "llama3",

                "prompt": prompt,

                "stream": False
            }
        )

        result = response.json()

        return result["response"]

    except:

        return (
            f"Hi {user_name} 😊 "
            f"Ollama server not running."
        )


# --------------------------------
# Main chatbot function
# --------------------------------
def get_recommendations(query):

    query = query.lower().strip()

    # Name
    name_response = extract_name(query)

    if name_response:
        return name_response

    # Greetings
    greeting_response = handle_greetings(query)

    if greeting_response:
        return greeting_response

    # Small talk
    small_talk_response = handle_small_talk(query)

    if small_talk_response:
        return small_talk_response

    # More results
    if any(word in query for word in [

        "more",
        "next",
        "show more",
        "another"

    ]):

        return show_more_results()

    # Detect category
    category = detect_category(query)

    if category:

        location = extract_location(query)

        df = get_dataset(category)

        if df is not None:

            filtered_df = search_dataset(
                df,
                location
            )

            # Detect intent
            intent = detect_intent(query)

            if intent == "top":
                filtered_df = sort_top_places(filtered_df)

            elif intent == "budget":
                filtered_df = sort_budget_places(filtered_df)

            # Dataset results
            if not filtered_df.empty:

                return format_results(
                    filtered_df,
                    category,
                    location
                )

            # Scraping fallback
            scraped_results = scrape_places(query)

            if scraped_results:

                return [{
                    "message":
                    f"No exact dataset match found. Found these online 😊"
                }] + scraped_results

            # Fallback dataset
            return format_results(df, category)

    # AI fallback
    ai_response = generate_ai_response(query)

    return [{
        "message": ai_response
    }]