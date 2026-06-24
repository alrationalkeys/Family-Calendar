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
                      events, notifications, rewards)
from .auth import pin_guard
from fastapi import Depends


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(title="FamilyHub", version="0.1.0", lifespan=lifespan,
              dependencies=[Depends(pin_guard)])

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],   # LAN-only device; tighten if exposed
    allow_methods=["*"],
    allow_headers=["*"],
)

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
app.include_router(photos.router, prefix="/api/photos", tags=["photos"])
app.include_router(ai.router, prefix="/api/ai", tags=["ai"])

# Serve the wall display
app.mount("/", StaticFiles(directory="static", html=True), name="static")
