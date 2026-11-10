"""
Minimal DB layer. Defaults to SQLite for zero-config Pi deployment.
Set DATABASE_URL to a Postgres DSN to use your existing Postgres instead.

Color model
-----------
Two sources of color, applied everywhere:
  - people     (you=blue, wife=pink, ...)
  - categories (work, kids, appointments, sports, ...)
Every item (event/chore/todo/grocery/meal) can carry a category_id and/or an
explicit color override. Resolution order (see services/color.py):
    item.color  ->  category.color  ->  person.color  ->  default
"""
import os
import sqlite3
from contextlib import contextmanager

DB_PATH = os.getenv("FAMILYHUB_DB", "familyhub.db")
# Railway volumes mount at /data; a relative "data/familyhub.db" would silently land
# inside the container and vanish on every deploy. If /data is a mount, use it.
if not os.path.isabs(DB_PATH) and DB_PATH.startswith("data/") and os.path.ismount("/data"):
    DB_PATH = "/" + DB_PATH
DEFAULT_COLOR = "#4f86c6"


def _ensure_dir():
    d = os.path.dirname(os.path.abspath(DB_PATH))
    try:
        os.makedirs(d, exist_ok=True)
    except OSError:
        pass


_ensure_dir()


@contextmanager
def get_db():
    conn = sqlite3.connect(DB_PATH, timeout=10)   # wait out a writer (mail poll thread) instead of "database is locked"
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def _has_column(conn, table, col):
    return any(r["name"] == col for r in conn.execute(f"PRAGMA table_info({table})"))


def _migrate(conn):
    """Add category_id/color columns to existing installs without data loss."""
    adds = {
        "chores":    [("category_id", "INTEGER"), ("color", "TEXT")],
        "meals":     [("category_id", "INTEGER"), ("color", "TEXT")],
        "todos":     [("category_id", "INTEGER"), ("color", "TEXT"),
                      ("due_date", "TEXT"), ("recurrence", "TEXT"),
                      ("ext_uid", "TEXT"), ("ext_source", "TEXT"), ("ext_list", "TEXT"),
                      ("person_id", "INTEGER")],
        "groceries": [("category_id", "INTEGER"), ("color", "TEXT"), ("got_at", "TEXT")],   # got_at: when ticked; purged 30 min later
        "people":    [("birthday", "TEXT")],        # "MM-DD" or "YYYY-MM-DD"; drives the Birthday skin + countdown
        "local_events": [("description", "TEXT"), ("skip_dates", "TEXT")],   # skip_dates: JSON list of "YYYY-MM-DD" occurrences to leave out
    }
    for table, cols in adds.items():
        for col, typ in cols:
            if not _has_column(conn, table, col):
                conn.execute(f"ALTER TABLE {table} ADD COLUMN {col} {typ}")


def init_db():
    with get_db() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS people (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                color TEXT NOT NULL DEFAULT '#4f86c6'
            );

            CREATE TABLE IF NOT EXISTS categories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                color TEXT NOT NULL DEFAULT '#4f86c6'
            );

            CREATE TABLE IF NOT EXISTS chores (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                person_id INTEGER REFERENCES people(id),
                category_id INTEGER REFERENCES categories(id),
                color TEXT,
                due_date TEXT,
                recurrence TEXT,
                stars INTEGER DEFAULT 0,
                done INTEGER DEFAULT 0,
                done_at TEXT
            );

            CREATE TABLE IF NOT EXISTS meals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT NOT NULL,
                slot TEXT NOT NULL,
                title TEXT NOT NULL,
                notes TEXT,
                category_id INTEGER REFERENCES categories(id),
                color TEXT
            );

            CREATE TABLE IF NOT EXISTS todos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                done INTEGER DEFAULT 0,
                person_id INTEGER REFERENCES people(id),
                category_id INTEGER REFERENCES categories(id),
                color TEXT,
                due_date TEXT,
                recurrence TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS groceries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                item TEXT NOT NULL,
                qty TEXT,
                got INTEGER DEFAULT 0,
                category_id INTEGER REFERENCES categories(id),
                color TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS local_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                start TEXT NOT NULL,
                end TEXT,
                all_day INTEGER DEFAULT 0,
                person_id INTEGER REFERENCES people(id),
                category_id INTEGER REFERENCES categories(id),
                color TEXT,
                description TEXT,
                recurrence TEXT,            -- 'daily'/'weekly'/'weekly:SA'/'monthly'
                reminder_minutes INTEGER,   -- minutes before to notify (NULL = none)
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS reward_ledger (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                person_id INTEGER REFERENCES people(id),
                stars INTEGER NOT NULL,      -- + earned, - redeemed
                reason TEXT,
                at TEXT DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS rewards (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                cost INTEGER NOT NULL        -- stars required
            );

            CREATE TABLE IF NOT EXISTS notifications (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                body TEXT,
                kind TEXT,                   -- 'reminder'|'digest'
                at TEXT NOT NULL,            -- when to fire (ISO)
                fired INTEGER DEFAULT 0,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS cal_sources (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                kind TEXT NOT NULL,
                label TEXT NOT NULL,
                config TEXT NOT NULL,
                person_id INTEGER REFERENCES people(id),
                category_id INTEGER REFERENCES categories(id)
            );

            CREATE TABLE IF NOT EXISTS routines (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                emoji TEXT,
                person_id INTEGER REFERENCES people(id),
                time_of_day TEXT DEFAULT 'morning',   -- morning|afternoon|bedtime|any
                days TEXT DEFAULT '',                 -- 'Mon,Tue,...' or '' = every day
                steps TEXT NOT NULL DEFAULT '[]',     -- JSON [{title, minutes, emoji}]
                stars INTEGER DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS routine_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                routine_id INTEGER REFERENCES routines(id),
                date TEXT NOT NULL,
                step_idx INTEGER NOT NULL,
                done_at TEXT,
                UNIQUE(routine_id, date, step_idx)
            );

            CREATE TABLE IF NOT EXISTS mail_imports (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                uid TEXT UNIQUE,
                subject TEXT,
                sender TEXT,
                received TEXT,
                events TEXT NOT NULL DEFAULT '[]',   -- JSON list of extracted events
                status TEXT DEFAULT 'pending'        -- pending|approved|dismissed|empty
            );

            CREATE TABLE IF NOT EXISTS countdowns (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                date TEXT NOT NULL,
                emoji TEXT,
                color TEXT,
                person_id INTEGER REFERENCES people(id)
            );
            """
        )
        _migrate(conn)
