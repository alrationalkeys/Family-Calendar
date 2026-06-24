"""Chore rewards — the part that makes stars mean something.
Completing chores earns stars (logged to the ledger); kids redeem stars for rewards
the family defines (e.g. '30 min screen time = 5 stars'). Gives the star system on
the chore chart an actual payoff, which is Skylight's real hook."""
from fastapi import APIRouter
from pydantic import BaseModel
from ..db import get_db

router = APIRouter()


class Reward(BaseModel):
    name: str
    cost: int


class Redemption(BaseModel):
    person_id: int
    reward_id: int


class StarGrant(BaseModel):
    person_id: int
    stars: int
    reason: str | None = None


@router.get("/balances")
def balances():
    """Star balance per person (earned minus redeemed)."""
    with get_db() as conn:
        people = [dict(r) for r in conn.execute("SELECT id,name,color FROM people")]
        for p in people:
            row = conn.execute("SELECT COALESCE(SUM(stars),0) AS bal FROM reward_ledger WHERE person_id=?",
                               (p["id"],)).fetchone()
            p["stars"] = row["bal"]
    return {"balances": people}


@router.get("/")
def list_rewards():
    with get_db() as conn:
        return [dict(r) for r in conn.execute("SELECT * FROM rewards ORDER BY cost")]


@router.post("/")
def add_reward(r: Reward):
    with get_db() as conn:
        cur = conn.execute("INSERT INTO rewards (name,cost) VALUES (?,?)", (r.name, r.cost))
        return {"id": cur.lastrowid}


@router.delete("/{reward_id}")
def delete_reward(reward_id: int):
    with get_db() as conn:
        conn.execute("DELETE FROM rewards WHERE id=?", (reward_id,))
        return {"deleted": reward_id}


@router.post("/grant")
def grant_stars(g: StarGrant):
    """Add stars to a person (called when a chore with stars is completed)."""
    with get_db() as conn:
        conn.execute("INSERT INTO reward_ledger (person_id,stars,reason) VALUES (?,?,?)",
                     (g.person_id, g.stars, g.reason or "earned"))
        return {"ok": True}


@router.post("/redeem")
def redeem(r: Redemption):
    with get_db() as conn:
        rw = conn.execute("SELECT name,cost FROM rewards WHERE id=?", (r.reward_id,)).fetchone()
        if not rw:
            return {"error": "reward not found"}
        bal = conn.execute("SELECT COALESCE(SUM(stars),0) AS b FROM reward_ledger WHERE person_id=?",
                           (r.person_id,)).fetchone()["b"]
        if bal < rw["cost"]:
            return {"error": "not enough stars", "balance": bal, "cost": rw["cost"]}
        conn.execute("INSERT INTO reward_ledger (person_id,stars,reason) VALUES (?,?,?)",
                     (r.person_id, -rw["cost"], f"redeemed: {rw['name']}"))
        return {"ok": True, "redeemed": rw["name"], "new_balance": bal - rw["cost"]}
