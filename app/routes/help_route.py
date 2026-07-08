from fastapi import APIRouter
from app.services.help_service import get_place_details

router = APIRouter()


@router.get("/help")

def help_place(place: str):

    return get_place_details(place)