def detect_intent(query):
    query = query.lower()

    if "top" in query or "best" in query:
        return "top"

    elif "cheap" in query or "budget" in query:
        return "budget"

    elif "near" in query:
        return "nearby"

    return "normal"