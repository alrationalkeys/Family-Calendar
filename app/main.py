"""
FamilyHub — a self-hosted, AI-native family calendar / chore / meal display.
A DIY, subscription-free, 10x-better alternative to Skylight Calendar.

Runs on a Raspberry Pi (or any machine) and is displayed full-screen in a
kiosk-mode browser on a wall-mounted touchscreen. Controlled from any phone
on the LAN.

Architecture:
  - FastAPI backend aggregates calendars (Google + iCloud/CalDAV), chores,
    meal plans, and photos into one normalized feed.
  - SQLite for local state by default (swap to Postgres by changing DATABASE_URL).
  - Static frontend (static/index.html) polls /api/dashboard and renders the wall view.
  - AI endpoints (/api/ai/parse) turn natural language / pasted text into events.
"""
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

from .db import init_db
from .routers import (calendar, chores, meals, photos, ai, dashboard,
                      todos, groceries, categories, settings, sources, weather,
                      events, notifications, rewards, display, ha, login, routines, mail, announce, summary, admin)
from .auth import pin_guard
from fastapi import Depends


def _maybe_seed_demo():
    """On a fresh cloud/test deploy the app would otherwise be empty. If
    SEED_DEMO is set (e.g. on Railway) AND there's no data yet, load the sample
    family once so the wall/phone has something to show. Never overwrites real
    data — it only runs when the people table is empty."""
    import os
    if os.getenv("SEED_DEMO", "").lower() not in ("1", "true", "yes", "on"):
        return
    try:
        from .db import get_db
        with get_db() as conn:
            empty = conn.execute("SELECT COUNT(*) FROM people").fetchone()[0] == 0
            cleared = conn.execute("SELECT value FROM settings WHERE key='demo_cleared'").fetchone()
        if empty and not cleared:
            import seed_demo
            seed_demo.main()
    except Exception:
        # seeding is a convenience; never let it stop the app from booting
        pass


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    _maybe_seed_demo()
    # background loop: enforce the display on/off schedule even with no client polling
    import asyncio
    from .services import display_svc

    async def _display_loop():
        while True:
            try:
                display_svc.tick()
            except Exception:
                pass
            await asyncio.sleep(20)

    task = asyncio.create_task(_display_loop())

    # background: pull forwarded emails into pending imports every 5 min (no-op unless configured)
    from .services import mail_import

    async def _mail_loop():
        await asyncio.sleep(15)
        while True:
            try:
                if mail_import.configured():
                    await asyncio.to_thread(mail_import.poll)
            except Exception:
                pass
            await asyncio.sleep(300)

    mtask = asyncio.create_task(_mail_loop())
    # background: live Home Assistant state over WebSocket (no-op in demo mode)
    from .services import ha_live
    htask = asyncio.create_task(ha_live.run_forever())
    try:
        yield
    finally:
        task.cancel()
        mtask.cancel()
        htask.cancel()


app = FastAPI(title="FamilyHub", version="0.1.0", lifespan=lifespan,
              dependencies=[Depends(pin_guard)])

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],   # LAN-only device; tighten if exposed
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def no_cache_html(request, call_next):
    """Don't let browsers cache the HTML shell, so a `git pull` is reflected on
    the next refresh without a hard-reload. Static JS/CSS can still be cached."""
    resp = await call_next(request)
    path = request.url.path
    if path == "/" or path.endswith((".html", ".js", ".css")):
        resp.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    return resp

app.include_router(dashboard.router, prefix="/api")
app.include_router(calendar.router, prefix="/api/calendar", tags=["calendar"])
app.include_router(chores.router, prefix="/api/chores", tags=["chores"])
app.include_router(meals.router, prefix="/api/meals", tags=["meals"])
app.include_router(todos.router, prefix="/api/todos", tags=["todos"])
app.include_router(groceries.router, prefix="/api/groceries", tags=["groceries"])
app.include_router(categories.router, prefix="/api/categories", tags=["categories"])
app.include_router(settings.router, prefix="/api/settings", tags=["settings"])
app.include_router(sources.router, prefix="/api/sources", tags=["sources"])
app.include_router(weather.router, prefix="/api/weather", tags=["weather"])
app.include_router(events.router, prefix="/api/events", tags=["events"])
app.include_router(notifications.router, prefix="/api/notifications", tags=["notifications"])
app.include_router(rewards.router, prefix="/api/rewards", tags=["rewards"])
app.include_router(display.router, prefix="/api/display", tags=["display"])
app.include_router(photos.router, prefix="/api/photos", tags=["photos"])
app.include_router(ai.router, prefix="/api/ai", tags=["ai"])
app.include_router(ha.router, prefix="/api/ha", tags=["home-assistant"])
app.include_router(login.router, prefix="/api/auth", tags=["auth"])
app.include_router(routines.router, prefix="/api/routines", tags=["routines"])
app.include_router(mail.router, prefix="/api/mail", tags=["mail"])
app.include_router(announce.router, prefix="/api/announce", tags=["announce"])
app.include_router(summary.router, prefix="/api/summary", tags=["summary"])
app.include_router(admin.router, prefix="/api/admin", tags=["admin"])

# Serve the wall display
app.mount("/", StaticFiles(directory="static", html=True), name="static")
