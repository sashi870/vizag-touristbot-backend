def analyze_budget(budget):
    if budget <= 500:
        return {
            "hotel": 100,
            "food": 150,
            "travel": 100,
            "places": 150
        }

    elif budget <= 2000:
        return {
            "hotel": 700,
            "food": 500,
            "travel": 400,
            "places": 400
        }

    else:
        return {
            "hotel": 4000,
            "food": 2000,
            "travel": 2000,
            "places": 2000
        }