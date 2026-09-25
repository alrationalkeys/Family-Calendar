"""Now Playing endpoints for the wall music widget (Spotify-backed)."""
from fastapi import APIRouter
from ..services import music_svc

router = APIRouter()


@router.get("/now")
def now_playing():
    """Current track for the wall widget. Empty state when no creds/nothing playing."""
    return music_svc.get_now_playing()


@router.post("/play")
def play():
    return music_svc.play()


@router.post("/pause")
def pause():
    return music_svc.pause()


@router.post("/next")
def next_track():
    return music_svc.next_track()


@router.post("/previous")
def previous():
    return music_svc.prev_track()
