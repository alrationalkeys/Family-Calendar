"""Weather endpoint for the wall header."""
from fastapi import APIRouter
from ..services import weather_svc

router = APIRouter()


@router.get("")
def weather(lat: float = weather_svc.DEFAULT_LAT, lon: float = weather_svc.DEFAULT_LON):
    return weather_svc.get_weather(lat, lon)


@router.get("/forecast")
def forecast(lat: float = weather_svc.DEFAULT_LAT, lon: float = weather_svc.DEFAULT_LON, days: int = 7):
    return weather_svc.get_forecast(lat, lon, days)


@router.get("/alerts")
def alerts():
    """National Weather Service alerts for the house (Moderate and up), with a prep checklist for storms."""
    from ..services import wx_alerts
    return {"alerts": wx_alerts.alerts()}
