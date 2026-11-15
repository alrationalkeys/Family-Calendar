"""Game day: the family's teams, live scores, celebrate on a score. See services/gameday.py."""
from fastapi import APIRouter, HTTPException
from ..services import gameday

router = APIRouter()


@router.get("")
def games():
    """Our teams' games today (live first) for the wall chip + phone."""
    return gameday.status()


@router.get("/leagues")
def leagues():
    return [{"key": k, "label": v[1]} for k, v in gameday.LEAGUES.items()]


@router.get("/teams")
def teams(league: str):
    if league not in gameday.LEAGUES:
        raise HTTPException(400, "unknown league")
    try:
        return gameday.league_teams(league)
    except Exception:
        raise HTTPException(502, "Couldn't reach the scores service")


@router.post("/test")
def test():
    """Run one celebration now (lights + wall) for the first team."""
    return gameday.test()
