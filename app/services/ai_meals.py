"""
AI meal planner — "plan this week's dinners" → 7 meals + a grocery list.

Skylight sells meal planning as a paid add-on and still makes you type every
dinner. Here Claude plans around what's already on the calendar, what's in the
grocery list, the family's size and a free-text preference ("kid-friendly, one
vegetarian night, no fish, under 30 minutes"). Without an API key a built-in
rotation of easy family dinners is used so the feature still works.
"""
from __future__ import annotations

import json
import os
import re
from datetime import date, timedelta

from ..db import get_db

SYSTEM = """You plan family dinners. Today is {today}. Return ONLY a JSON array, no prose,
no markdown fences. One item per requested day:
{{"date": "YYYY-MM-DD", "title": "short dinner name", "ingredients": ["item", ...], "minutes": int}}
Rules: realistic weeknight cooking, vary proteins and cuisines across the week, respect the
preferences exactly, skip dates that already have a dinner (listed), reuse ingredients across
days to cut waste, list 4-9 grocery-style ingredients per meal (no salt/pepper/oil/water),
and don't repeat a title from the recent meals list."""

# No-key fallback: fourteen easy dinners, rotated.
_FALLBACK = [
    ("Tacos", ["ground beef", "taco shells", "shredded cheese", "lettuce", "tomatoes", "salsa"], 25),
    ("Spaghetti & meatballs", ["spaghetti", "frozen meatballs", "marinara sauce", "parmesan", "garlic bread"], 30),
    ("Sheet-pan chicken & veggies", ["chicken thighs", "broccoli", "baby potatoes", "carrots", "lemon"], 40),
    ("Grilled cheese & tomato soup", ["bread", "cheddar", "butter", "tomato soup"], 15),
    ("Chicken stir-fry", ["chicken breast", "stir-fry vegetables", "soy sauce", "rice", "garlic", "ginger"], 25),
    ("Homemade pizza night", ["pizza dough", "pizza sauce", "mozzarella", "pepperoni", "bell pepper"], 30),
    ("Burgers & sweet potato fries", ["ground beef", "burger buns", "cheddar", "sweet potatoes", "lettuce", "pickles"], 30),
    ("Slow-cooker pulled pork", ["pork shoulder", "bbq sauce", "slider buns", "coleslaw mix"], 20),
    ("Baked salmon & rice", ["salmon fillets", "rice", "green beans", "lemon", "butter"], 25),
    ("Breakfast for dinner", ["eggs", "bacon", "pancake mix", "maple syrup", "berries"], 20),
    ("Chicken quesadillas", ["tortillas", "rotisserie chicken", "shredded cheese", "black beans", "sour cream", "salsa"], 20),
    ("Beef chili", ["ground beef", "kidney beans", "diced tomatoes", "onion", "chili seasoning", "cornbread mix"], 45),
    ("Chicken Caesar wraps", ["tortillas", "rotisserie chicken", "romaine", "caesar dressing", "parmesan", "croutons"], 15),
    ("Mac & cheese with peas", ["elbow pasta", "cheddar", "milk", "butter", "frozen peas", "ham"], 25),
]


def _context(start: date, days: int):
    end = start + timedelta(days=days - 1)
    with get_db() as conn:
        taken = {r["date"] for r in conn.execute(
            "SELECT date FROM meals WHERE slot='dinner' AND date BETWEEN ? AND ?", (start.isoformat(), end.isoformat()))}
        recent = [r["title"] for r in conn.execute(
            "SELECT DISTINCT title FROM meals WHERE date >= ? ORDER BY date DESC LIMIT 20",
            ((start - timedelta(days=21)).isoformat(),))]
        groceries = [r["item"] for r in conn.execute("SELECT item FROM groceries WHERE got=0")]
        people = conn.execute("SELECT COUNT(*) c FROM people").fetchone()["c"]
    return taken, recent, groceries, people


def plan(days: int = 7, prefs: str = "", start: str | None = None) -> dict:
    days = max(1, min(14, int(days or 7)))
    start_d = date.fromisoformat(start) if start else date.today()
    taken, recent, groceries, people = _context(start_d, days)
    wanted = [start_d + timedelta(days=i) for i in range(days)]
    free = [d for d in wanted if d.isoformat() not in taken]
    if not free:
        return {"meals": [], "skipped": sorted(taken), "source": "none"}
    meals = None
    if os.environ.get("ANTHROPIC_API_KEY"):
        try:
            from anthropic import Anthropic
            client = Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"], timeout=60.0)
            user = (f"Plan dinner for these dates: {', '.join(d.isoformat() for d in free)}.\n"
                    f"Family size: {people or 4}.\nPreferences: {prefs.strip() or 'easy, kid-friendly, varied'}.\n"
                    f"Dates already planned (skip): {', '.join(sorted(taken)) or 'none'}.\n"
                    f"Recent meals (avoid repeating): {', '.join(recent) or 'none'}.\n"
                    f"Already on the grocery list (feel free to use): {', '.join(groceries) or 'nothing'}.")
            resp = client.messages.create(model="claude-opus-4-8", max_tokens=1800,
                                          system=SYSTEM.format(today=date.today().isoformat()),
                                          messages=[{"role": "user", "content": user}])
            raw = "".join(b.text for b in resp.content if b.type == "text").strip()
            raw = raw.removeprefix("```json").removeprefix("```").removesuffix("```").strip()
            parsed = json.loads(raw)
            meals = [m for m in parsed if m.get("title") and m.get("date")]
            source = "ai"
        except Exception:
            meals = None
    if meals is None:
        source = "builtin"
        avoid = {t.lower() for t in recent}
        pool = [m for m in _FALLBACK if m[0].lower() not in avoid] or _FALLBACK
        off = start_d.toordinal() % len(pool)
        meals = []
        for i, d in enumerate(free):
            t, ing, mins = pool[(off + i) % len(pool)]
            meals.append({"date": d.isoformat(), "title": t, "ingredients": ing, "minutes": mins})
    for m in meals:
        m["slot"] = "dinner"
        m["ingredients"] = [str(x).strip() for x in (m.get("ingredients") or []) if str(x).strip()][:10]
    return {"meals": meals, "skipped": sorted(taken), "source": source}


def apply(meals: list[dict], add_groceries: bool = True) -> dict:
    """Write the chosen meals (and their ingredients, de-duplicated) to the DB."""
    added_meals, added_items = 0, []
    with get_db() as conn:
        have = {re.sub(r"\s+", " ", r["item"].strip().lower()) for r in conn.execute("SELECT item FROM groceries WHERE got=0")}
        for m in meals:
            d, title = m.get("date"), (m.get("title") or "").strip()
            if not d or not title:
                continue
            if conn.execute("SELECT 1 FROM meals WHERE date=? AND slot='dinner'", (d,)).fetchone():
                continue
            conn.execute("INSERT INTO meals (date, slot, title, notes) VALUES (?,?,?,?)",
                         (d, "dinner", title, ", ".join(m.get("ingredients") or []) or None))
            added_meals += 1
            if add_groceries:
                for ing in m.get("ingredients") or []:
                    key = re.sub(r"\s+", " ", str(ing).strip().lower())
                    if not key or key in have:
                        continue
                    conn.execute("INSERT INTO groceries (item) VALUES (?)", (str(ing).strip(),))
                    have.add(key)
                    added_items.append(str(ing).strip())
    return {"meals": added_meals, "groceries": added_items}
