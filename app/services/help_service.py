from app.data_loader import helpdesk_places
import pandas as pd


# LOAD BEACH DETAILS CSV
beaches_data = pd.read_csv(
    "datasets/vizag_beaches.csv"
)


def get_place_details(place_name):

    place_name = place_name.lower().strip()

    # SEARCH BASIC HELP DESK DATA
    for _, row in helpdesk_places.iterrows():

        name = str(row["name"]).lower()

        if place_name in name:

            # DEFAULT RESPONSE
            response = {
                "name": row["name"],
                "description": row["description"],
                "map_url": row["map_url"]
            }

            # SEARCH EXTRA BEACH DATA
            for _, beach in beaches_data.iterrows():

                beach_name = str(
                    beach["Beach Name"]
                ).lower()

                if place_name in beach_name:

                    response["speciality"] = beach.get(
                        "Speciality",
                        "N/A"
                    )

                    response["famous_for"] = beach.get(
                        "Famous For",
                        "N/A"
                    )

                    response["activities"] = beach.get(
                        "Activities",
                        "N/A"
                    )

                    response["best_season"] = beach.get(
                        "Best Season",
                        "N/A"
                    )

                    response["crowd_level"] = beach.get(
                        "Crowd Level",
                        "N/A"
                    )

                    response["ideal_for"] = beach.get(
                        "Ideal For",
                        "N/A"
                    )

                    response["water_safety"] = beach.get(
                        "Water Safety",
                        "N/A"
                    )

                    response["water_sports"] = beach.get(
                        "Water Sports Available",
                        "N/A"
                    )

                    response["open_hours"] = beach.get(
                        "Open Hours",
                        "N/A"
                    )

                    response["entry_fee"] = beach.get(
                        "Entry Fee (INR)",
                        "Free"
                    )

                    response["landmark"] = beach.get(
                        "Nearest Landmark",
                        "N/A"
                    )

                    response["distance_from_city"] = beach.get(
                        "Distance from City Centre (km)",
                        "N/A"
                    )

                    break

            return response

    return {
        "name": "Place Not Found",
        "description": "Sorry, no details available.",
        "map_url": "#"
    }