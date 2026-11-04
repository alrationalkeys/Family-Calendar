"""Photo screensaver feed.

Two sources, merged:
  - local uploads from the phone app  -> static/photos/  (POST /api/photos/upload)
  - an iCloud Shared Album link        -> settings.icloudAlbumUrl (services/icloud_album.py)
"""
import os
import re
import time
from fastapi import APIRouter, UploadFile, File, HTTPException
from ..services import icloud_album

router = APIRouter()
PHOTO_DIR = "static/photos"
ALLOWED = (".jpg", ".jpeg", ".png", ".webp", ".heic")
MAX_BYTES = 25 * 1024 * 1024


def _album_url() -> str:
    try:
        from .settings import get_settings
        return (get_settings().get("icloudAlbumUrl") or "").strip()
    except Exception:
        return ""


def _local():
    os.makedirs(PHOTO_DIR, exist_ok=True)
    files = sorted(f for f in os.listdir(PHOTO_DIR) if f.lower().endswith(ALLOWED[:4]))
    return [f"/photos/{f}" for f in files]


@router.get("/")
def list_photos():
    local = _local()
    album = icloud_album.photos_for(_album_url())
    return {"photos": local + album, "local": len(local), "album": len(album)}


@router.post("/upload")
async def upload(files: list[UploadFile] = File(...)):
    """Phone upload — one or many images. HEIC is accepted but only shown if the
    browser can render it (Safari can; Chromium on the wall can't), so the phone
    app asks iOS for JPEG via accept=image/jpeg,image/png."""
    os.makedirs(PHOTO_DIR, exist_ok=True)
    saved = []
    for f in files:
        name = os.path.basename(f.filename or "photo")
        ext = os.path.splitext(name)[1].lower() or ".jpg"
        if ext not in ALLOWED:
            continue
        data = await f.read()
        if not data or len(data) > MAX_BYTES:
            continue
        safe = re.sub(r"[^a-zA-Z0-9_-]+", "-", os.path.splitext(name)[0])[:40] or "photo"
        fname = f"{int(time.time()*1000)}-{safe}{ext}"
        with open(os.path.join(PHOTO_DIR, fname), "wb") as out:
            out.write(data)
        saved.append(f"/photos/{fname}")
    if not saved:
        raise HTTPException(400, "no usable images (jpg/png/webp up to 25MB)")
    return {"saved": saved}


@router.delete("/{name}")
def delete_photo(name: str):
    safe = os.path.basename(name)
    path = os.path.join(PHOTO_DIR, safe)
    if not os.path.isfile(path):
        raise HTTPException(404, "no such photo")
    os.remove(path)
    return {"deleted": safe}


@router.post("/album/refresh")
def refresh_album():
    """Force a re-fetch of the shared album (the phone calls this after saving a link)."""
    icloud_album._CACHE["at"] = 0
    n = len(icloud_album.photos_for(_album_url()))
    return {"album": n, "ok": n > 0 or not _album_url()}
