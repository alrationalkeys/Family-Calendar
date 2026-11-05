"""Tiny in-memory record of the last sync of each kind, for the phone's
"is it working?" readout (/api/sources/status)."""
from datetime import datetime

_S: dict[str, dict] = {}


def mark(kind: str, ok: bool, count: int = 0, error: str | None = None, label: str | None = None):
    _S[kind] = {"at": datetime.now().isoformat(timespec="seconds"), "ok": ok, "count": count,
                "error": (error or "")[:160] or None, "label": label}


def snapshot() -> dict:
    return dict(_S)
