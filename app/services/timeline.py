"""
"What ran when" for one day: Home Assistant's recorder history turned into on/off spans.

  rows   heating / cooling per thermostat (hvac_action), then lights, plugs & switches, TVs
  power  any sensor with device_class power (W or kW): a line per sensor, in watts
  peak   the Santee Cooper demand window for that date (winter Nov-Mar 6-9 AM, summer Apr-Oct 3-6 PM)
  stats  heat / AC minutes, how much of it fell inside peak, light-hours

GET /api/ha/timeline?day=YYYY-MM-DD (default today). Demo mode returns a made-up day.
"""
from __future__ import annotations

import random
import urllib.parse
from datetime import date, datetime, timedelta

from . import ha_svc

_OFF = {"off", "standby", "unavailable", "unknown", "", None}


def peak_window(d: date):
    if d.month in (11, 12, 1, 2, 3):
        return 6 * 60, 9 * 60
    return 15 * 60, 18 * 60


def _kind(eid: str) -> str | None:
    dom = eid.split(".", 1)[0]
    return {"climate": "climate", "light": "light", "switch": "plug", "media_player": "tv"}.get(dom)


def _parse(ts: str) -> datetime:
    return datetime.fromisoformat(ts.replace("Z", "+00:00")).astimezone()


def _spans(states: list, kind: str, t0: datetime, t1: datetime) -> list:
    """[(start_min, end_min, label)] in minutes since local midnight, clipped to the day."""
    out, cur = [], None          # cur = (start, label)
    now = datetime.now().astimezone()
    for st in states:
        t = max(_parse(st.get("last_changed") or st.get("last_updated")), t0)
        if kind == "climate":
            a = (st.get("attributes") or {}).get("hvac_action")
            label = {"heating": "heat", "cooling": "cool"}.get(a)
        else:
            label = "on" if st.get("state") not in _OFF else None
        if cur and cur[1] != label:
            out.append((cur[0], t, cur[1])); cur = None
        if label and not cur:
            cur = (t, label)
    if cur:
        out.append((cur[0], min(t1, now), cur[1]))
    m = lambda t: round((t - t0).total_seconds() / 60, 1)
    return [[m(a), m(b), lab] for a, b, lab in out if b > a]


def _overlap(spans, lo, hi):
    return sum(max(0, min(b, hi) - max(a, lo)) for a, b, _ in spans)


def _stats(rows, peak):
    heat = sum(_overlap([s for s in r["spans"] if s[2] == "heat"], 0, 1440) for r in rows if r["kind"] == "climate")
    cool = sum(_overlap([s for s in r["spans"] if s[2] == "cool"], 0, 1440) for r in rows if r["kind"] == "climate")
    in_peak = sum(_overlap(r["spans"], *peak) for r in rows if r["kind"] == "climate")
    lights = sum(_overlap(r["spans"], 0, 1440) for r in rows if r["kind"] == "light")
    return {"heat_min": round(heat), "cool_min": round(cool), "hvac_peak_min": round(in_peak), "light_min": round(lights)}


def get(day: str | None = None) -> dict:
    try:
        d = date.fromisoformat(day) if day else date.today()
    except ValueError:
        d = date.today()
    peak = peak_window(d)
    if ha_svc.demo_mode() or not ha_svc.ha_url():
        return _demo(d, peak)
    t0 = datetime(d.year, d.month, d.day).astimezone()
    t1 = t0 + timedelta(days=1)
    try:
        tiles = [t for g in ha_svc.get_home().get("groups", []) for t in g.get("tiles", [])]
        ents = {t["entity_id"]: t["name"] for t in tiles if _kind(t["entity_id"])}
        all_states = ha_svc._request("/api/states") or []
        power = {s["entity_id"]: (s.get("attributes") or {}) for s in all_states
                 if s["entity_id"].startswith("sensor.") and (s.get("attributes") or {}).get("device_class") == "power"}
    except Exception:
        return {"ok": False, "reason": "couldn't reach Home Assistant"}

    def history(ids, minimal):
        if not ids:
            return []
        q = {"end_time": t1.isoformat(), "filter_entity_id": ",".join(ids)}
        path = f"/api/history/period/{urllib.parse.quote(t0.isoformat())}?{urllib.parse.urlencode(q)}"
        if minimal:
            path += "&minimal_response&no_attributes"
        return ha_svc._request(path, timeout=20) or []

    rows, pw = [], []
    try:
        clim = [e for e in ents if e.startswith("climate.")]
        for lst in history(clim, False) + history([e for e in ents if not e.startswith("climate.")], True):
            if not lst:
                continue
            eid = lst[0].get("entity_id")
            k = _kind(eid or "")
            if not k:
                continue
            for st in lst:
                st.setdefault("entity_id", eid)
            sp = _spans(lst, k, t0, t1)
            if sp or k == "climate":
                rows.append({"entity_id": eid, "name": ents.get(eid, eid), "kind": k, "spans": sp})
        for lst in history(list(power)[:12], True):
            if not lst:
                continue
            eid = lst[0].get("entity_id")
            a = power.get(eid, {})
            mult = 1000 if str(a.get("unit_of_measurement", "")).lower() == "kw" else 1
            pts = []
            for st in lst:
                try:
                    pts.append([round((_parse(st["last_changed"]) - t0).total_seconds() / 60, 1), round(float(st["state"]) * mult)])
                except (KeyError, TypeError, ValueError):
                    continue
            if pts:
                pw.append({"entity_id": eid, "name": a.get("friendly_name") or eid, "points": pts})
    except Exception as e:
        return {"ok": False, "reason": f"Home Assistant history failed ({getattr(e, 'code', '') or 'error'})"}
    order = {"climate": 0, "light": 1, "plug": 2, "tv": 3}
    rows.sort(key=lambda r: (order[r["kind"]], r["name"].lower()))
    return {"ok": True, "day": d.isoformat(), "peak": list(peak), "rows": rows, "power": pw, "stats": _stats(rows, peak),
            "now_min": _now_min(d)}


def _now_min(d):
    n = datetime.now()
    return n.hour * 60 + n.minute if n.date() == d else None


def _demo(d, peak):
    rnd = random.Random(d.toordinal())
    winter = d.month in (11, 12, 1, 2, 3)
    def runs(spans):
        out = []
        for a, b in spans:
            t = a
            while t < b:
                on = rnd.randint(12, 30); off = rnd.randint(15, 45)
                out.append([t, min(b, t + on)]); t += on + off
        return out
    hv = "heat" if winter else "cool"
    rows = []
    for name in ("Upstairs Thermostat", "Downstairs Thermostat"):
        sp = runs([(0, peak[0]), (peak[1], 1440)])        # off through peak, like the real setup
        rows.append({"entity_id": "climate." + name.lower().replace(" ", "_"), "name": name, "kind": "climate",
                     "spans": [[a, b, hv] for a, b in sp]})
    for name, sp in (("Kitchen Lights", [(390, 480), (1050, 1350)]), ("Living Room Lamp", [(1080, 1410)]),
                     ("Front Porch Light", [(1035, 1440)]), ("Driveway Light", [(1035, 1440)])):
        rows.append({"entity_id": "light." + name.lower().replace(" ", "_"), "name": name, "kind": "light", "spans": [[a, b, "on"] for a, b in sp]})
    for name, sp in (("Upstairs Smart Plugs", [(1020, 1380)]), ("Exterior Lights Plug", [(1035, 1440)])):
        rows.append({"entity_id": "switch." + name.lower().replace(" ", "_"), "name": name, "kind": "plug", "spans": [[a, b, "on"] for a, b in sp]})
    rows.append({"entity_id": "media_player.living_room_tv", "name": "Living Room TV", "kind": "tv", "spans": [[1170, 1350, "on"]]})
    pts, base = [], 350
    for m in range(0, 1440, 10):
        w = base + sum(3200 for r in rows[:2] for a, b, _ in r["spans"] if a <= m < b) + rnd.randint(-60, 80)
        pts.append([m, w])
    nm = _now_min(d)
    if nm is not None:
        for r in rows:
            r["spans"] = [[a, min(b, nm), k] for a, b, k in r["spans"] if a < nm]
        pts = [p for p in pts if p[0] <= nm]
    return {"ok": True, "demo": True, "day": d.isoformat(), "peak": list(peak), "rows": rows,
            "power": [{"entity_id": "sensor.house_power", "name": "Whole house", "points": pts}],
            "stats": _stats(rows, peak), "now_min": nm}
