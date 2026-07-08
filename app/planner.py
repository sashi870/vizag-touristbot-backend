def generate_itinerary(days, mood):
    itinerary = []

    for day in range(1, days + 1):
        if mood == "relaxation":
            itinerary.append({
                "day": day,
                "plan": "Beach visit + cafe + sunset point"
            })

        elif mood == "adventure":
            itinerary.append({
                "day": day,
                "plan": "Trekking + waterfall + boating"
            })

        elif mood == "culture":
            itinerary.append({
                "day": day,
                "plan": "Temple visit + museum + local food"
            })

        else:
            itinerary.append({
                "day": day,
                "plan": "Mixed activities"
            })

    return itinerary