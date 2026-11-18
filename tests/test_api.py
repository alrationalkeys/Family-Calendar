"""The server's own endpoints, end to end, on a scratch database."""
import datetime

# endpoints that stream forever, redirect to a login, or need the outside world
SKIP = ("/api/ha/events", "/api/spotify/", "/api/games/teams", "/api/weather", "/api/mail/", "/api/travel",
        "/api/ha/camera", "/api/ha/art", "/api/admin/", "/api/photos/", "/api/auth/", "/api/ai/voice/cloud",
        "/docs", "/redoc", "/openapi.json")


def test_every_plain_get_endpoint_answers(client):
    """No GET endpoint may crash (500) on an empty house."""
    from app.main import app
    bad = []
    for r in app.routes:
        path = getattr(r, "path", "")
        if "GET" not in (getattr(r, "methods", None) or ()) or "{" in path or not path.startswith("/api/"):
            continue
        if any(path.startswith(s) for s in SKIP):
            continue
        resp = client.get(path)
        if resp.status_code >= 500 or resp.status_code == 422:
            bad.append((path, resp.status_code))
    assert not bad, bad


def test_pages_are_served(client):
    for path in ("/", "/phone.html", "/theme.js", "/home-shared.js", "/manifest.json"):
        assert client.get(path).status_code == 200, path


def test_settings_patch_merges_and_keeps_other_keys(client):
    client.patch("/api/settings", json={"undoMinutes": 12})
    client.patch("/api/settings", json={"gameDelay": 9})
    s = client.get("/api/settings").json()
    assert s["undoMinutes"] == 12 and s["gameDelay"] == 9
    assert "panels" in s                      # a default that nobody set is still there
    client.patch("/api/settings", json={"undoMinutes": 30})


def test_todo_lifecycle_with_undo(client):
    t = client.post("/api/todos/", json={"title": "Test the undo"}).json()
    tid = t["id"]
    r = client.post(f"/api/todos/{tid}/toggle").json()
    row = next(x for x in client.get("/api/dashboard").json()["todos"] if x["id"] == tid)
    assert row.get("just_done"), "a ticked to-do stays visible (crossed out) for the undo window"
    r = client.post(f"/api/todos/{tid}/toggle").json()
    assert r.get("undone")
    row = next(x for x in client.get("/api/dashboard").json()["todos"] if x["id"] == tid)
    assert not row.get("done") and not row.get("just_done")
    assert client.delete(f"/api/todos/{tid}").status_code == 200


def test_todo_lists_and_several_people(client):
    p1 = client.post("/api/categories/people", json={"name": "Tester One", "color": "#112233"}).json()
    p2 = client.post("/api/categories/people", json={"name": "Tester Two", "color": "#445566"}).json()
    t = client.post("/api/todos/", json={"title": "Shared job", "list_name": "Work", "person_ids": [p1["id"], p2["id"]]}).json()
    row = next(x for x in client.get("/api/dashboard").json()["todos"] if x["id"] == t["id"])
    assert row["list_name"] == "Work" and sorted(row["person_ids"]) == sorted([p1["id"], p2["id"]])
    client.delete(f"/api/todos/{t['id']}")


def test_chore_stars_are_credited_and_removed_on_undo(client):
    p = client.post("/api/categories/people", json={"name": "Star Kid", "color": "#aa0000"}).json()
    c = client.post("/api/chores/", json={"title": "Feed the dogs", "stars": 3, "person_ids": [p["id"]]}).json()

    def stars():
        return next((b["stars"] for b in client.get("/api/chores/scoreboard").json().get("scoreboard", []) if b["id"] == p["id"]), 0)
    before = stars()
    client.post(f"/api/chores/{c['id']}/toggle")
    assert stars() == before + 3
    client.post(f"/api/chores/{c['id']}/toggle")
    assert stars() == before
    client.delete(f"/api/chores/{c['id']}")


def test_grocery_add_toggle_delete(client):
    g = client.post("/api/groceries/", json={"item": "test milk"}).json()
    assert client.post(f"/api/groceries/{g['id']}/toggle").status_code == 200
    assert client.delete(f"/api/groceries/{g['id']}").status_code == 200


def test_local_event_shows_on_the_calendar(client):
    day = datetime.date.today().isoformat()
    e = client.post("/api/events/", json={"title": "Test dentist", "start": f"{day}T15:00:00", "end": f"{day}T16:00:00"}).json()
    titles = [x["title"] for x in client.get("/api/calendar/events?days=2").json()["events"]]
    assert "Test dentist" in titles
    client.delete(f"/api/events/{e['id']}")


def test_voice_rules_without_an_ai_key(client):
    say = lambda t: client.post("/api/ai/command", json={"text": t}).json().get("say", "")
    assert "Christmas is" in say("how many days until Christmas")
    assert "timer" in say("set a timer for 3 minutes").lower()
    assert "locked" in say("is the front door locked").lower() or "front door" in say("is the front door locked").lower()
    # a device's name inside a general question must not be answered with that device's state
    assert " is on." not in say("how many days until the kitchen remodel")


def test_voice_never_disarms(client):
    r = client.post("/api/ai/command", json={"text": "disarm the alarm"}).json()
    assert r.get("ok") is False and "PIN" in r.get("say", "")


def test_diagnostics_hide_secrets(client):
    txt = client.get("/api/ha/diag?q=front door").text
    assert "FamilyHub diagnostics" in txt and "front_door" in txt
    from app.services import diag
    assert "eyJ" not in diag._hide("Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.abcdefghijklmnopqrstuvwxyz")
    assert diag._clean({"latitude": 1, "access_token": "x", "brightness": 3}) == {"brightness": 3}


def test_game_day_test_button_needs_a_team(client):
    client.patch("/api/settings", json={"teams": []})
    assert client.post("/api/games/test").json()["ok"] is False


def test_house_report_runs_on_an_empty_month(client):
    r = client.get("/api/ha/report?month=2020-01").json()
    assert r["month"] == "2020-01" and r["lines"]
