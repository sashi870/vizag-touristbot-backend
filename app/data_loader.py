import pandas as pd

# import pandas as pd

# import pandas as pd


def load_csv(path):

    try:
        return pd.read_csv(path, encoding="utf-8")

    except UnicodeDecodeError:
        return pd.read_csv(path, encoding="latin1")

    except FileNotFoundError:
        print(f"File not found: {path}")
        return pd.DataFrame()


# Load datasets from app/datasets folder

beaches = load_csv("app/datasets/beaches.csv")

cafes = load_csv("app/datasets/cafes.csv")

restaurants = load_csv("app/datasets/restaurants.csv")

parks = load_csv("app/datasets/parks.csv")

museums = load_csv("app/datasets/Museum.csv")

theaters = load_csv("app/datasets/theaters.csv")

colleges = load_csv("app/datasets/colleges.csv")

waterfalls = load_csv("app/datasets/Waterfalls.csv")
temples= load_csv("app/datasets/temples.csv")

hospitals= load_csv("app/datasets/hospitals.csv")

pubs = load_csv("app/datasets/pubs.csv")

valleys = load_csv("app/datasets/valleys.csv")

helpdesk_places = load_csv(
    "app/datasets/helpdesk_places_50.csv"
)