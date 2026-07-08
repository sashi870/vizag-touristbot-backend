from fastapi import APIRouter
from app.services.budget_service import analyze_budget
from app.services.recommendation_service import get_recommendations

router = APIRouter()

@router.post("/chat")
def chat(data: dict):
    try:
        budget = int(data.get("budget", 500))
        location = data.get("location", "Vizag")
        query = data.get("query", "")

        # Budget breakdown
        budget_data = analyze_budget(budget)

        # Ollama recommendation
        recommendations = get_recommendations(
            location,
            budget,
            query
        )

        # Temporary hardcoded places
        places = [
            {
                "name": "RK Beach",
                "latitude": 17.7100,
                "longitude": 83.3200,
                "description": "Beautiful beach in Vizag",
                "budget": 100
            },
            {
                "name": "Kailasagiri",
                "latitude": 17.7490,
                "longitude": 83.3420,
                "description": "Hilltop tourist attraction",
                "budget": 200
            },
            {
                "name": "Rushikonda Beach",
                "latitude": 17.7828,
                "longitude": 83.3850,
                "description": "Popular beach destination",
                "budget": 150
            }
        ]

        return {
            "success": True,
            "budget": budget_data,
            "recommendations": recommendations,
            "places": places
        }

    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }