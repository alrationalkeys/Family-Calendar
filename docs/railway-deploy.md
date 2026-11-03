# Deploy FamilyHub to Railway (for testing)

A quick way to reach FamilyHub from your phone **anywhere** (not just home WiFi),
before the real Pi / mini-PC build. Railway builds the FastAPI app and gives it a
public `https://…up.railway.app` URL.

> ⚠️ **Read the Privacy section below first.** By default the calendar is
> *publicly readable* by anyone who has the URL. Fine for a quick test; not how
> you'd leave it long-term.

The repo already includes everything Railway needs: `railway.toml`, `Procfile`,
`requirements.txt`, and `.python-version`.

## Option A — deploy from GitHub (easiest)
1. Push this branch to GitHub (already done): `claude/tender-fermi-1g1upo`.
2. In Railway: **New Project → Deploy from GitHub repo →** pick `Family-Calendar`.
3. Under **Settings → Branch**, choose `claude/tender-fermi-1g1upo` (or merge to
   `main` first and deploy that).
4. Railway auto-detects Python, installs `requirements.txt`, and starts the app
   with the command in `railway.toml`. No port config needed — it uses `$PORT`.
5. **Settings → Networking → Generate Domain** to get your public URL.

## Option B — deploy from your computer (Railway CLI)
```bash
npm i -g @railway/cli
railway login
railway init            # create/link a project
railway up              # build & deploy the current folder
railway domain          # print the public URL
```

## See it on your phone
Open the generated URL on your phone's browser:
- Wall display: `https://<your-app>.up.railway.app/`
- Phone app:    `https://<your-app>.up.railway.app/phone.html`
- Add it to your home screen (it's a PWA) for an app-like icon.

The **Home / smart-home tab works in demo mode** here (sample lights, alarm,
scenes) — your real Home Assistant lives on your LAN and isn't reachable from
Railway, which is expected.

## Environment variables (Railway → service → Variables)
All optional; set what you want to light up:

| Variable | What it does |
|---|---|
| `SEED_DEMO` | `1` = load the sample family on first boot so it's not empty. **Turn this off (delete it) once you add real data**, or a fresh DB would reseed. |
| `FAMILYHUB_PIN` | Require this PIN for **writes** (adding/editing). Strongly recommended on a public URL. |
| `FAMILYHUB_LOCK_READS` | `1` = also require the PIN to **view** — a login screen gates all data. **Set this for real privacy on Railway.** Needs `FAMILYHUB_PIN`. |
| `FAMILYHUB_DB` | Set to `/data/familyhub.db` if you attach a Volume (see Persistence). |
| `ANTHROPIC_API_KEY` | Enables AI quick-add / vision. |
| `HA_DEMO` | `1` forces the Home tab's demo devices even if HA creds are set. |

Never paste secrets into the repo — set them here as variables only.

## Persistence (important)
Only **SQLite** is wired up, and Railway's container filesystem is **ephemeral** —
it resets on every deploy/restart, so your added events/lists would vanish.

To keep data between deploys:
1. Railway → service → **Volumes → New Volume**, mount path `/data`.
2. Add variable `FAMILYHUB_DB=/data/familyhub.db`.
3. Redeploy. The DB now lives on the volume and survives restarts.

(Without a volume it still runs — it just starts fresh each deploy. With
`SEED_DEMO=1` that means the demo family comes back each time.)

## Privacy — please read
FamilyHub was built for a trusted LAN. On a public Railway URL, **lock it down**:

**Set both of these variables:**
- `FAMILYHUB_PIN` = your family PIN (guards edits).
- `FAMILYHUB_LOCK_READS` = `1` (guards *viewing* too).

With `FAMILYHUB_LOCK_READS=1`, opening the URL shows a **login screen** and no
data loads until the PIN is entered — so the link alone reveals nothing. The PIN
is remembered on each device (stored locally in the browser), so you unlock once
per phone. Wrong guesses are rate-limited with a lockout; the constant-time
compare means a short PIN still isn't easily brute-forced, but **use 6+ digits**
on a public URL anyway.

If you set `FAMILYHUB_PIN` but *not* `FAMILYHUB_LOCK_READS`, viewing stays open to
anyone with the link (only edits are blocked) — fine for a quick demo with the
sample family, not for real data.

The static app shell (the empty HTML/JS) is still served publicly so the login
screen can load; it contains no family data — all data lives behind `/api`, which
is what the PIN protects.

For the strongest privacy long-term, the roadmap's plan is **Tailscale**: the app
stays on your LAN, reachable from your phone over an encrypted private network
with no public URL at all (see `docs/hardening.md`).

## Cost
A tiny app like this fits Railway's low-usage / hobby tier; it sleeps when idle on
some plans. This is a **testing convenience** — the end goal is still the wall
screen on your own hardware, which is $0/month.
