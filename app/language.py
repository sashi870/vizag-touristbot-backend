def detect_language(query):
    telugu_words = ["హాయ్", "విజాగ్", "బీచ్"]
    hindi_words = ["नमस्ते", "होटल", "घूमना"]

    for word in telugu_words:
        if word in query:
            return "telugu"

    for word in hindi_words:
        if word in query:
            return "hindi"

    return "english"