"""
Demo seed — fills FamilyHub with realistic sample data so the app looks alive
when you show it to someone (before real calendars are connected).

Run from the project root:
    python seed_demo.py

Safe to re-run: it clears demo data first. Does NOT touch real calendar sources.
"""
import datetime as dt
from app.db import init_db, get_db

init_db()

today = dt.date.today()


def iso(day_offset, hour, minute=0):
    d = today + dt.timedelta(days=day_offset)
    return dt.datetime(d.year, d.month, d.day, hour, minute).isoformat()


def date_only(day_offset):
    return (today + dt.timedelta(days=day_offset)).isoformat()


with get_db() as conn:
    # wipe previous demo rows so re-running stays clean
    for t in ("people", "categories", "chores", "meals", "todos", "groceries"):
        conn.execute(f"DELETE FROM {t}")

    # --- people ---
    conn.execute("INSERT INTO people (name,color) VALUES (?,?),(?,?)",
                 ("Mom", "#d96b8a", "Dad", "#4f86c6"))

    # --- categories ---
    cats = [("Work", "#7c5cff"), ("Kids", "#5cb88a"),
            ("Appointments", "#e9a23b"), ("Sports", "#e0533d"),
            ("Social", "#3db5c9")]
    conn.executemany("INSERT INTO categories (name,color) VALUES (?,?)", cats)
    # map names to ids
    cat = {r["name"]: r["id"] for r in conn.execute("SELECT id,name FROM categories")}

    # --- todos (with category colors) ---
    todos = [
        ("Schedule oil change", cat["Appointments"]),
        ("RSVP to birthday party", cat["Social"]),
        ("Print field trip form", cat["Kids"]),
        ("Finish quarterly report", cat["Work"]),
    ]
    conn.executemany("INSERT INTO todos (title,category_id) VALUES (?,?)", todos)

    # --- groceries ---
    groceries = [
        ("Milk", "2 gal", cat["Kids"]),
        ("Eggs", "1 dozen", None),
        ("Coffee", None, None),
        ("Chicken breast", "3 lb", None),
        ("Bananas", None, cat["Kids"]),
        ("Dish soap", None, None),
    ]
    conn.executemany("INSERT INTO groceries (item,qty,category_id) VALUES (?,?,?)", groceries)

    # --- meals (today + next few days) ---
    meals = [
        (date_only(0), "breakfast", "Pancakes", cat["Kids"]),
        (date_only(0), "dinner", "Taco night", cat["Kids"]),
        (date_only(1), "dinner", "Grilled salmon", None),
        (date_only(2), "dinner", "Spaghetti", cat["Kids"]),
        (date_only(3), "dinner", "Pizza Friday", cat["Social"]),
    ]
    conn.executemany("INSERT INTO meals (date,slot,title,category_id) VALUES (?,?,?,?)", meals)

    # --- chores ---
    people = {r["name"]: r["id"] for r in conn.execute("SELECT id,name FROM people")}
    chores = [
        ("Take out trash", people["Dad"], 1),
        ("Walk the dog", people["Mom"], 1),
        ("Load dishwasher", people["Dad"], 0),
    ]
    conn.executemany("INSERT INTO chores (title,person_id,stars) VALUES (?,?,?)", chores)

print("Seeded people, categories, todos, groceries, meals, and chores.")

# --- demo calendar events (written to demo_events.json) ---
# Served by the calendar endpoint only when no real Google/iCloud source is connected.
import json as _json

demo_events = [
    {"title": "Soccer practice", "start": iso(0, 17, 0), "end": iso(0, 18, 30),
     "source": "demo", "all_day": False, "color": "#e0533d"},
    {"title": "Dentist — Emma", "start": iso(1, 9, 0), "end": iso(1, 10, 0),
     "source": "demo", "all_day": False, "color": "#e9a23b"},
    {"title": "Team standup", "start": iso(1, 11, 0), "end": iso(1, 11, 30),
     "source": "demo", "all_day": False, "color": "#7c5cff"},
    {"title": "Lunch with Sarah", "start": iso(2, 12, 30), "end": iso(2, 13, 30),
     "source": "demo", "all_day": False, "color": "#3db5c9"},
    {"title": "Piano lesson", "start": iso(2, 16, 0), "end": iso(2, 17, 0),
     "source": "demo", "all_day": False, "color": "#5cb88a"},
    {"title": "Date night", "start": iso(4, 19, 0), "end": iso(4, 21, 0),
     "source": "demo", "all_day": False, "color": "#d96b8a"},
    {"title": "Kids' game day", "start": iso(6, 10, 0), "end": iso(6, 12, 0),
     "source": "demo", "all_day": False, "color": "#e0533d"},
    {"title": "Grandma visiting", "start": date_only(6), "end": date_only(6),
     "source": "demo", "all_day": True, "color": "#3db5c9"},
    {"title": "Quarterly review", "start": iso(8, 14, 0), "end": iso(8, 15, 0),
     "source": "demo", "all_day": False, "color": "#7c5cff"},
]
with open("demo_events.json", "w") as f:
    _json.dump(demo_events, f, indent=2)

print(f"Wrote {len(demo_events)} demo calendar events to demo_events.json")
print("\nDemo ready. Run:  uvicorn app.main:app --host 0.0.0.0 --port 8000")
print("Wall:  http://localhost:8000/   ·   Phone:  http://localhost:8000/phone.html")
print("\nTo clear the demo later: delete familyhub.db and demo_events.json,")
print("then connect a real calendar.")
