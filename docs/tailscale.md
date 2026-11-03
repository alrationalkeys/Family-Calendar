# Reach FamilyHub from anywhere — Tailscale (the private way)

This is the recommended way to use FamilyHub from your phone when you're **not at
home** — at work, on cell data, wherever. Unlike the Railway option, nothing is
exposed to the public internet: Tailscale builds a private, encrypted
(WireGuard) network between *your own devices only*. No open ports, no public
URL, no one else can reach it.

**When to use which:**
- **At home on WiFi:** just use `http://<host-ip>:8000` — no Tailscale needed.
- **Away from home, private:** Tailscale (this guide). Best for real family data.
- **Away from home, quick demo for someone else:** Railway (`docs/railway-deploy.md`),
  locked down with `FAMILYHUB_LOCK_READS=1`.

The wall screen itself never needs Tailscale — it's on your home LAN. Tailscale
is for the **phones** (and you) connecting from outside.

---

## 1. Install Tailscale on the FamilyHub host
"Host" = the Pi / mini-PC that runs FamilyHub (the `uvicorn` server).

```bash
curl -fsSL https://tailscale.com/install.sh | sh
sudo tailscale up
```
It prints a login URL — open it, sign in (Google/Microsoft/GitHub/email all
work), and the host joins your private network ("tailnet"). Free personal plan
covers plenty of devices.

Give the host a clear name so it's easy to reach:
```bash
sudo tailscale up --hostname=familyhub
```

Find its address any time:
```bash
tailscale ip -4          # e.g. 100.101.102.103
tailscale status         # lists all your devices + names
```

## 2. Install Tailscale on your phone(s)
- Install the **Tailscale** app (App Store / Play Store).
- Sign in with the **same account**.
- Leave it connected (it's lightweight and battery-friendly).

## 3. Open FamilyHub from your phone, anywhere
In the phone browser:
- Wall view: `http://100.101.102.103:8000/` (the host's Tailscale IP), or
- Phone app: `http://100.101.102.103:8000/phone.html`

### Nicer: MagicDNS (use a name, not an IP)
In the Tailscale admin console (login.tailscale.com) → **DNS** → enable
**MagicDNS**. Now you can use the hostname instead of the IP:
- `http://familyhub:8000/` and `http://familyhub:8000/phone.html`

Add that to your phone's home screen (it's a PWA) for an app icon.

---

## 4. Optional but recommended: real HTTPS (for the PWA + offline)
FamilyHub's **service worker / offline cache** and some PWA features only fully
work over `https://` (or `localhost`). Tailscale can give the host a *real,
trusted* HTTPS certificate — no browser warnings — with one command, using
Tailscale Serve:

1. In the admin console → **DNS**, note your tailnet name (e.g.
   `tailnet-abcd.ts.net`), and enable **HTTPS Certificates**.
2. On the host:
   ```bash
   sudo tailscale serve --bg 8000
   ```
   This reverse-proxies `https://familyhub.<tailnet>.ts.net/` → your local
   `127.0.0.1:8000`, with a valid Let's Encrypt cert that Tailscale manages.
3. On your phone (with Tailscale connected), open
   `https://familyhub.<tailnet>.ts.net/` — padlock and all. Offline mode and
   "Add to Home Screen" now behave like a native app.

Check or undo it:
```bash
tailscale serve status
sudo tailscale serve --https=443 off
```

> This replaces the self-hosted `Caddyfile` HTTPS approach for remote access —
> `tailscale serve` is simpler because Tailscale handles the certificate. Keep
> the `Caddyfile` only if you also want local-LAN HTTPS without Tailscale.

---

## 5. Now you can drop the public Railway URL
Once Tailscale works from your phone:
- In Railway, you can **pause or delete** the service (your data was only demo
  data there anyway — real data lives on the home host).
- Keep `FAMILYHUB_PIN` set on the host for write protection. You generally
  **don't need `FAMILYHUB_LOCK_READS`** anymore, because only your own devices
  can even reach the app over Tailscale — it's private by construction.

---

## Keeping it running
- **Start on boot:** the installer sets up the `tailscaled` service via systemd,
  so it reconnects automatically after a reboot. Confirm with
  `systemctl status tailscaled`.
- **Share with family:** either add each phone to your tailnet (simplest), or use
  Tailscale's "Share" feature to invite a device without giving full account
  access.
- **Nothing to forward:** do **not** open ports on your router. That's the whole
  point — Tailscale needs no port forwarding and leaves your home network closed.

## Troubleshooting
- *Phone can't load it:* make sure the Tailscale app is **connected** (toggle on)
  and the host shows up in `tailscale status`.
- *Name doesn't resolve:* enable **MagicDNS** in the admin console; try the raw
  `100.x.y.z` IP to confirm connectivity first.
- *Works on IP but you want HTTPS:* set up `tailscale serve` (section 4).
- *Multiple people:* each device needs the Tailscale app signed into your tailnet
  (or a shared invite).

See also `docs/hardening.md` for the broader security checklist (PIN lockout,
backups, LAN posture).
