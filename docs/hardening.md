# FamilyHub — security hardening

The boring stuff that actually protects you. Do these before the wall touches real
devices (alarm/locks via Home Assistant). None of it is exotic "military-grade"
anything — it's defense in depth, done simply.

## 1. Keep it off the public internet
FamilyHub and Home Assistant should have **no ports forwarded** from your router.
Everything is LAN-only. For access from outside the house, use Tailscale (below),
never port-forwarding.

## 2. Tailscale — encrypted remote access (free)
WireGuard-based mesh VPN. Your phone reaches the hub from anywhere as if on home wifi,
with nothing exposed to the internet.
1. Make a free account at tailscale.com.
2. On the FamilyHub Pi: `curl -fsSL https://tailscale.com/install.sh | sh` then `sudo tailscale up`.
3. Install the Tailscale app on your phone, sign in.
4. Reach the hub at its Tailscale name/IP. Done — end-to-end encrypted, no open ports.

**Full walkthrough** (MagicDNS, real HTTPS via `tailscale serve`, dropping the
public Railway URL, troubleshooting): see `docs/tailscale.md`.

## 3. Local HTTPS with Caddy
On the LAN, FamilyHub speaks plain HTTP. Put **Caddy** in front for encrypted traffic
(and so the service worker / PWA features work on phones, not just localhost).

```
# /etc/caddy/Caddyfile  — see Caddyfile in repo root for a copy
familyhub.local {
    tls internal                 # Caddy's own local CA (no external cert needed)
    reverse_proxy 127.0.0.1:8000 # FamilyHub runs on :8000 behind it
}
```
- `sudo apt install caddy`, drop in the Caddyfile, `sudo systemctl restart caddy`.
- Caddy forwards the real client IP in `X-Forwarded-For`, which FamilyHub's PIN
  lockout already honors.
- To silence the browser warning, trust Caddy's local root CA on your devices
  (`caddy trust` prints where it lives), or just accept it on the LAN.

## 4. Turn on the PIN + lockout
Set a PIN so changes need it (reads stay open so the wall always shows):
```
FAMILYHUB_PIN=062815           # your family PIN
FAMILYHUB_MAX_FAILS=5          # wrong tries before a lockout (default 5)
FAMILYHUB_LOCKOUT=60           # lockout seconds (default 60)
```
The PIN is compared in constant time and brute-force attempts lock the offending
device out. (A separate, stronger PIN gates alarm **disarm** when Phase 2 lands.)

## 5. Network isolation
Put the wall + HA (and IoT gadgets) on a **separate VLAN / guest-style network**
from your laptops and phones-with-bank-apps, if your router supports it. Firewall it
to LAN-only. Limits blast radius if any one gadget is compromised.

## 6. Keep it patched
```
sudo apt install unattended-upgrades && sudo dpkg-reconfigure unattended-upgrades
```
Security updates apply themselves. Home Assistant updates itself from its own UI.

## 7. Back up
`python backup.py --keep 14` (systemd timer included) keeps rolling DB backups.
Copy them off the Pi occasionally (another machine or a USB stick).

## Deliberately skipped
**Full-disk encryption on the wall Pi.** A headless kiosk can't type a passphrase at
boot, and the real threat is the network, not someone stealing the Pi. High hassle,
near-zero benefit here.
