"""Weather endpoint for the wall header."""
from fastapi import APIRouter
from ..services import weather_svc

router = APIRouter()


@router.get("")
def weather(lat: float = weather_svc.DEFAULT_LAT, lon: float = weather_svc.DEFAULT_LON):
    return weather_svc.get_weather(lat, lon)
