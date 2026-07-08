def calculate_budget(total_budget, days):
    hotel = total_budget * 0.4
    food = total_budget * 0.25
    transport = total_budget * 0.15
    activities = total_budget * 0.15
    misc = total_budget * 0.05

    return {
        "Accommodation": hotel,
        "Food": food,
        "Transport": transport,
        "Activities": activities,
        "Miscellaneous": misc,
        "Total": total_budget
    }