"""
What the AI features cost. Every Claude call reports its token counts; record() turns them into an approximate
dollar figure with the public per-million-token prices below and keeps a row per call (table ai_usage).

Approximate on purpose: prices change, and the real bill is on the Anthropic Console (console.anthropic.com >
Usage / Cost). Tracking starts the day this file was added; earlier use isn't in the total.
"""
from __future__ import annotations

from datetime import datetime, timedelta

from ..db import get_db

# $ per million tokens (input, output). Cache reads bill at 0.1x input, cache writes at 1.25x input.
PRICES = {
    "claude-fable-5-2": (8.0, 40.0), "claude-fable-5-1": (10.0, 50.0), "claude-fable-5": (10.0, 50.0),
    "claude-opus-5-5": (4.0, 20.0), "claude-opus-5": (5.0, 25.0), "claude-opus-4-8": (5.0, 25.0),
    "claude-opus-4-7": (5.0, 25.0), "claude-opus-4-6": (5.0, 25.0),
    "claude-sonnet-5-5": (2.0, 10.0), "claude-sonnet-5": (2.0, 10.0), "claude-sonnet-4-6": (3.0, 15.0),
    "claude-haiku-5-5": (0.10, 0.50), "claude-haiku-4-5": (1.0, 5.0),
}
WEB_SEARCH_EACH = 0.01          # $10 per 1,000 searches
FEATURES = {"voice": "Voice questions and commands", "quick-add": "Quick add (typed)", "vision": "Photo to events",
            "meals": "Meal planner", "package": "Package on the porch", "email": "Email import", "other": "Other"}


def _table(conn):
    conn.execute("CREATE TABLE IF NOT EXISTS ai_usage (id INTEGER PRIMARY KEY AUTOINCREMENT, at TEXT NOT NULL, feature TEXT, "
                 "model TEXT, tin INTEGER, tout INTEGER, cache_read INTEGER, cache_write INTEGER, searches INTEGER, cost REAL)")


def price(model: str) -> tuple:
    m = (model or "").lower()
    for k in sorted(PRICES, key=len, reverse=True):        # longest id first, so dated ids still match their family
        if m.startswith(k):
            return PRICES[k]
    return PRICES["claude-opus-4-8"]                        # unknown model: assume Opus-tier rather than understate


def cost_of(model: str, usage) -> tuple:
    """-> (dollars, tokens_in, tokens_out, cache_read, cache_write, searches) from a response's usage object."""
    g = lambda o, k: (getattr(o, k, None) if not isinstance(o, dict) else o.get(k)) or 0
    tin, tout = g(usage, "input_tokens"), g(usage, "output_tokens")
    cr, cw = g(usage, "cache_read_input_tokens"), g(usage, "cache_creation_input_tokens")
    stu = getattr(usage, "server_tool_use", None) if not isinstance(usage, dict) else usage.get("server_tool_use")
    searches = g(stu, "web_search_requests") if stu is not None else 0
    pi, po = price(model)
    dollars = (tin * pi + cr * pi * 0.1 + cw * pi * 1.25 + tout * po) / 1_000_000 + searches * WEB_SEARCH_EACH
    return dollars, tin, tout, cr, cw, searches


def record(feature: str, resp) -> float:
    """Log one API response. Returns its approximate cost in dollars (0.0 if it couldn't be read). Never raises."""
    try:
        model = getattr(resp, "model", "") or ""
        dollars, tin, tout, cr, cw, searches = cost_of(model, getattr(resp, "usage", None))
        with get_db() as conn:
            _table(conn)
            conn.execute("INSERT INTO ai_usage (at, feature, model, tin, tout, cache_read, cache_write, searches, cost) "
                         "VALUES (?,?,?,?,?,?,?,?,?)",
                         (datetime.now().isoformat(timespec="seconds"), feature, model, tin, tout, cr, cw, searches, dollars))
        return dollars
    except Exception:
        return 0.0


def cents(dollars: float) -> str:
    """Short human figure: '~0.3¢', '~4¢', '~$1.25'."""
    c = dollars * 100
    if c < 0.05:
        return "under 0.1¢"
    return f"~{c:.1f}¢" if c < 10 else (f"~{c:.0f}¢" if c < 100 else f"~${dollars:.2f}")


def summary() -> dict:
    now = datetime.now()
    day, month = now.strftime("%Y-%m-%d"), now.strftime("%Y-%m")
    week = (now - timedelta(days=7)).isoformat(timespec="seconds")
    with get_db() as conn:
        _table(conn)
        one = lambda q, *a: conn.execute(q, a).fetchone()
        tot = one("SELECT COALESCE(SUM(cost),0) c, COUNT(*) n, MIN(at) first FROM ai_usage")
        feats = [dict(r) for r in conn.execute(
            "SELECT feature, COUNT(*) n, COALESCE(SUM(cost),0) cost, COALESCE(SUM(searches),0) searches FROM ai_usage "
            "GROUP BY feature ORDER BY cost DESC")]
        models = [dict(r) for r in conn.execute(
            "SELECT model, COUNT(*) n, COALESCE(SUM(cost),0) cost FROM ai_usage GROUP BY model ORDER BY cost DESC")]
        out = {
            "today": one("SELECT COALESCE(SUM(cost),0) c FROM ai_usage WHERE at LIKE ?", day + "%")["c"],
            "week": one("SELECT COALESCE(SUM(cost),0) c FROM ai_usage WHERE at>=?", week)["c"],
            "month": one("SELECT COALESCE(SUM(cost),0) c FROM ai_usage WHERE at LIKE ?", month + "%")["c"],
            "total": tot["c"], "calls": tot["n"], "since": (tot["first"] or "")[:10] or None,
            "by_feature": [{**f, "label": FEATURES.get(f["feature"], f["feature"] or "Other")} for f in feats],
            "by_model": models,
        }
    for k in ("today", "week", "month", "total"):
        out[k + "_text"] = "$%.2f" % out[k] if out[k] >= 0.995 else cents(out[k]).replace("~", "") if out[k] else "0¢"
    return out
