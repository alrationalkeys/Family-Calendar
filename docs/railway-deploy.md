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
| `FAMILYHUB_PIN` | Require this PIN (sent as `X-FH-PIN`) for **writes**. Strongly recommended on a public URL. |
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
FamilyHub was built for a trusted LAN. On a public Railway URL:
- **Reads are open to anyone with the link.** The PIN (`FAMILYHUB_PIN`) only
  guards *writes* (adding/editing/deleting), not viewing. So someone with the URL
  could see your family's calendar, chores and lists.
- For a quick test that's usually fine (the URL is long and unguessable), but
  **don't put anything you'd mind a stranger seeing**, and treat the URL as
  semi-secret.
- At minimum, **set `FAMILYHUB_PIN`** so randoms can't add/delete your data.

For real privacy, the roadmap's plan is **Tailscale** (the app stays on your LAN,
reachable from your phone over an encrypted private network — no public URL at
all). Ask and I can also add *read* authentication (require the PIN or a login to
view, not just to write) if you want to keep using Railway but lock down viewing.

## Cost
A tiny app like this fits Railway's low-usage / hobby tier; it sleeps when idle on
some plans. This is a **testing convenience** — the end goal is still the wall
screen on your own hardware, which is $0/month.
