"""Photo screensaver feed — drop images in static/photos/."""
import os
from fastapi import APIRouter

router = APIRouter()
PHOTO_DIR = "static/photos"


@router.get("/")
def list_photos():
    os.makedirs(PHOTO_DIR, exist_ok=True)
    files = [f"/photos/{f}" for f in os.listdir(PHOTO_DIR)
             if f.lower().endswith((".jpg", ".jpeg", ".png", ".webp"))]
    return {"photos": files}
