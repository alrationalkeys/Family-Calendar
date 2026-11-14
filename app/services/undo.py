"""
Oops-proof check-offs: a to-do or chore you tick stays on the lists (crossed out) for settings.undoMinutes (30);
tapping it again inside that window puts it back exactly as it was: done -> open, a repeating one's due date
rolled back, and a chore's stars taken back off the ledger.

Columns: done_at (when it was ticked) + undo_due (a repeating item's due date before it rolled; "" = had none).
"""
from __future__ import annotations

from datetime import datetime, timedelta


def minutes() -> int:
    try:
        from ..routers.settings import get_settings
        return max(0, min(240, int((get_settings() or {}).get("undoMinutes", 30))))
    except Exception:
        return 30


def cutoff() -> str:
    return (datetime.now() - timedelta(minutes=minutes())).isoformat(timespec="seconds")


def now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def recent(row) -> bool:
    """Ticked inside the undo window and still undoable (done, or a repeat that rolled forward)."""
    try:
        at = row["done_at"]
        undo_due = row["undo_due"]
    except (KeyError, IndexError):
        return False
    if not at or at < cutoff():
        return False
    return bool(row["done"]) or undo_due is not None


def mark(d: dict) -> dict:
    """API/dashboard rows: just_done = show it crossed out with an undo."""
    d["just_done"] = recent(d)
    d.pop("undo_due", None)
    return d


def sql_visible() -> str:
    """WHERE fragment: open items + ones ticked inside the undo window (one '?' = cutoff())."""
    return "(done=0 OR (done=1 AND done_at IS NOT NULL AND done_at>=?))"
