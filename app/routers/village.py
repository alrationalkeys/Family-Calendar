"""North Pole Village buttons + status for the wall, phone and voice (services/village.py)."""
from fastapi import APIRouter
from pydantic import BaseModel

from ..services import village

router = APIRouter()


class Cmd(BaseModel):
    do: str


@router.get("/status")
def status():
    """{reachable, mode, manual, train, laps_left, said}. The tile hides itself when reachable is false."""
    return village.status()


@router.post("/cmd")
def cmd(c: Cmd):
    return village.command(c.do)
