#!/usr/bin/env python3
"""
Load a believable sample family into FamilyHub so the wall isn't empty when you
try it out. Great for a test drive on a laptop/Surface before real data.

    python seed_demo.py

This REPLACES the content tables (people, events, chores, lists, meals, stars)
with demo data. To get back to a clean slate, just delete familyhub.db and
restart — nothing here touches your real calendars or settings sources.
"""
from datetime import date, datetime, timedelta
from app.db import init_db, get_db

TABLES = ["reward_ledger", "chores", "meals", "todos", "groceries", "local_events",
          "people", "categories"]


def iso(d, t=None):
    return d.isoformat() + (f"T{t}:00" if t else "")


def main():
    init_db()
    today = date.today()
    with get_db() as conn:
        for t in TABLES:
            conn.execute(f"DELETE FROM {t}")

        # People (sample — swap for your real family later, in Settings)
        people = {}
        for name, color in [("Mom", "#e05a9c"), ("Dad", "#4f86c6"),
                            ("Ella", "#9b59b6"), ("Max", "#3bb273")]:
            cur = conn.execute("INSERT INTO people (name,color) VALUES (?,?)", (name, color))
            people[name] = cur.lastrowid

        # Categories
        for cname, ccolor in [("School", "#e9a23b"), ("Sports", "#2ca8a8"), ("Family", "#c0689b")]:
            conn.execute("INSERT INTO categories (name,color) VALUES (?,?)", (cname, ccolor))

        # Calendar events across this week (local events show without any sync)
        def ev(title, day_offset, t=None, end=None, person=None, allday=0, rec=None):
            d = today + timedelta(days=day_offset)
            conn.execute(
                "INSERT INTO local_events (title,start,end,all_day,person_id,color,recurrence) "
                "VALUES (?,?,?,?,?,?,?)",
                (title, iso(d, t), iso(d, end) if end else None, allday,
                 people.get(person), None, rec))
        ev("Soccer practice", 0, "16:00", "17:00", "Max")
        ev("Dinner with the Parkers", 0, "19:00", "21:00", "Dad")
        ev("Trash day", 1, allday=1, rec="weekly")
        ev("Dentist — Ella", 1, "09:30", "10:15", "Ella")
        ev("Swim meet", 2, "10:00", "12:00", "Max")
        ev("Book club", 3, "18:30", "20:00", "Mom")
        ev("Date night", 4, "18:30", "22:00", "Mom")
        ev("School closed", 5, allday=1)
        ev("Grandma visits", 6, allday=1, person="Family" if False else None)

        # Chores (with stars) — some recurring
        chores = [
            ("Feed the dog", "Max", 2, "daily"),
            ("Make your bed", "Ella", 1, "daily"),
            ("Homework", "Ella", 3, None),
            ("Take out trash", "Max", 2, "weekly"),
            ("Load the dishwasher", "Ella", 2, "daily"),
            ("Tidy your room", "Max", 2, None),
        ]
        for title, person, stars, rec in chores:
            conn.execute(
                "INSERT INTO chores (title,person_id,color,due_date,recurrence,stars) "
                "VALUES (?,?,?,?,?,?)",
                (title, people[person], None, today.isoformat(), rec, stars))

        # Star ledger: a few earned TODAY (drives today's progress) + older balance.
        # Today's entries omit `at` so the default UTC timestamp lands on today.
        for person, earns in [("Max", [2, 2, 2]), ("Ella", [1, 3])]:
            for s in earns:
                conn.execute("INSERT INTO reward_ledger (person_id,stars,reason) VALUES (?,?,?)",
                             (people[person], s, "chore: demo"))
        # older balance padding (date irrelevant to balance)
        past = (datetime.now() - timedelta(days=4)).isoformat()
        conn.execute("INSERT INTO reward_ledger (person_id,stars,reason,at) VALUES (?,?,?,?)",
                     (people["Max"], 29, "chore: earlier this week", past))
        conn.execute("INSERT INTO reward_ledger (person_id,stars,reason,at) VALUES (?,?,?,?)",
                     (people["Ella"], 25, "chore: earlier this week", past))

        # Groceries
        for item, qty in [("Milk", "2"), ("Eggs", ""), ("Bread", ""), ("Bananas", ""),
                          ("Coffee", ""), ("Chicken", "2 lb"), ("Spinach", "")]:
            conn.execute("INSERT INTO groceries (item,qty) VALUES (?,?)", (item, qty))

        # To-dos
        for t in ["Call the dentist", "Pay the electric bill", "RSVP to the birthday party",
                  "Return library books"]:
            conn.execute("INSERT INTO todos (title) VALUES (?)", (t,))

        # Meals for the week
        meals = ["Tacos", "Spaghetti & meatballs", "Sheet-pan chicken", "Breakfast for dinner",
                 "Stir-fry", "Pizza night", "Pot roast"]
        for i, m in enumerate(meals):
            d = (today + timedelta(days=i)).isoformat()
            conn.execute("INSERT INTO meals (date,slot,title) VALUES (?,?,?)", (d, "dinner", m))

    print("Demo family loaded: 4 people, a week of events, 6 chores, stars, "
          "groceries, to-dos, and meals.\nStart the app and open it. "
          "Delete familyhub.db to reset.")


if __name__ == "__main__":
    main()
