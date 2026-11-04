"""
iCloud Shared Album -> photo URLs, no Apple account needed.

Share an album from the Photos app with "Public Website" on, paste the link
(https://www.icloud.com/sharedalbum/#B0abc...) into the phone app, and the wall's
slideshow fills itself from it. Anyone in the family who can add to the shared
album adds to the wall. This is how Skylight's photo frame feels, for free.

Apple's web stream API (what the public album page itself uses):
    POST https://p01-sharedstreams.icloud.com/<token>/sharedstreams/webstream   {"streamCtag": null}
        -> may answer 330 with X-Apple-MMe-Host: pNN-sharedstreams.icloud.com (use that host)
        -> {"photos": [{"photoGuid", "derivatives": {"<w>": {"checksum", "width", ...}}}], ...}
    POST .../sharedstreams/webasseturls   {"photoGuids": [...]}
        -> {"items": {"<checksum>": {"url_location", "url_path"}}}
The asset URLs expire after a few hours, so results are cached briefly and
refreshed on a timer. All failures degrade to [] (the local photos still show).
"""
from __future__ import annotations

import json
import re
import time
import urllib.request
import urllib.error

_CACHE = {"url": None, "at": 0.0, "photos": []}
TTL = 45 * 60          # refresh asset URLs every 45 min (they expire in hours)
MAX_W = 2200           # biggest derivative we bother with (the panel is 1080p)


def album_token(url: str) -> str | None:
    m = re.search(r"sharedalbum/#([A-Za-z0-9_\-]+)", url or "")
    return m.group(1) if m else None


def _post(url: str, payload: dict, timeout=12):
    req = urllib.request.Request(url, data=json.dumps(payload).encode(), method="POST",
                                 headers={"Content-Type": "application/json", "User-Agent": "FamilyHub/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, dict(r.headers), json.loads(r.read().decode() or "{}")
    except urllib.error.HTTPError as e:
        body = e.read().decode(errors="ignore")
        try:
            return e.code, dict(e.headers), json.loads(body or "{}")
        except json.JSONDecodeError:
            return e.code, dict(e.headers), {}


def fetch_album(url: str) -> list[dict]:
    """Return [{url, width, height}] for every photo in the shared album."""
    token = album_token(url)
    if not token:
        return []
    host = "p01-sharedstreams.icloud.com"
    base = f"https://{host}/{token}/sharedstreams"
    status, headers, data = _post(base + "/webstream", {"streamCtag": None})
    if status == 330:
        host = headers.get("X-Apple-MMe-Host") or headers.get("x-apple-mme-host") or host
        base = f"https://{host}/{token}/sharedstreams"
        status, headers, data = _post(base + "/webstream", {"streamCtag": None})
    photos = data.get("photos") or []
    if not photos:
        return []
    # pick one derivative per photo: the largest that's <= MAX_W (else the smallest)
    want = {}
    for p in photos:
        ders = list((p.get("derivatives") or {}).values())
        ders = [d for d in ders if d.get("checksum")]
        if not ders:
            continue
        ok = [d for d in ders if int(d.get("width") or 0) <= MAX_W]
        pick = max(ok, key=lambda d: int(d.get("width") or 0)) if ok else min(ders, key=lambda d: int(d.get("width") or 0))
        want[pick["checksum"]] = (p.get("photoGuid"), pick)
    guids = sorted({g for g, _ in want.values() if g})
    out = []
    for i in range(0, len(guids), 25):          # Apple caps the batch size
        status, _, assets = _post(base + "/webasseturls", {"photoGuids": guids[i:i + 25]})
        items = (assets or {}).get("items") or {}
        for checksum, (guid, der) in want.items():
            it = items.get(checksum)
            if it and it.get("url_location") and it.get("url_path"):
                out.append({"url": f"https://{it['url_location']}{it['url_path']}",
                            "width": der.get("width"), "height": der.get("height")})
    return out


def photos_for(url: str) -> list[str]:
    """Cached list of photo URLs for the configured album ([] if none/unreachable)."""
    if not url:
        _CACHE.update({"url": None, "photos": []})
        return []
    now = time.time()
    if _CACHE["url"] == url and now - _CACHE["at"] < TTL:
        return _CACHE["photos"]
    try:
        urls = [p["url"] for p in fetch_album(url)]
    except Exception:
        urls = _CACHE["photos"] if _CACHE["url"] == url else []
    _CACHE.update({"url": url, "at": now, "photos": urls})
    return urls
