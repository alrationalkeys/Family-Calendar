# Home Assistant + Qolsys IQ Panel — setup checklist

This is the **parallel track** for FamilyHub's smart-home features (Phase 2). Do it on
the **spare Raspberry Pi 5 (8GB)** — a *separate* box from the FamilyHub screen, so a
FamilyHub update can never take the alarm/house offline.

You need: the Pi 5 8GB, a microSD (or NVMe) + reader, your **IQ Panel dealer code**, and
both devices on the **same LAN**.

> Menu wording differs a little between IQ Panel 2+ and IQ Panel 4, and between HAOS
> releases. Where exact names vary, I've said so — follow the on-device/README wording.

---

## A. Install Home Assistant OS on the Pi 5

1. On your Windows desktop, install **Raspberry Pi Imager**.
2. Imager → **Choose Device:** Raspberry Pi 5 → **Choose OS:** *Other specific-purpose OS*
   → *Home Assistant and home automation* → **Home Assistant OS** (the Pi 5 image).
3. **Choose Storage:** your SD/NVMe → **Write**.
4. Put it in the Pi, plug in Ethernet (recommended for a hub) + power, wait ~10–15 min.
5. Browse to **http://homeassistant.local:8123** → create your admin account.
6. Settings → System → **Network**: give it a **static IP / DHCP reservation** (so its
   address never changes — FamilyHub and qolsysgw will point at it).

## B. Enable the 3rd-party connection on the IQ Panel

This exposes a local (LAN-only) control channel that `qolsysgw` talks to.

1. On the panel: **Settings → Advanced Settings →** enter your **dealer code**.
2. Go to **Installation → Devices → Wi-Fi Devices → 3rd Party Connections**
   (on some firmware it's under *Installation → Devices → 3rd Party Connections*).
3. Enable **"Control4"** (that toggle is the generic 3rd-party socket; it is **not**
   Control4-specific).
4. Tap **Reveal Secure Token** and copy the **token** — this is the secret `qolsysgw`
   uses. Also note the panel's **IP address** (Settings → Wi-Fi).
5. The panel listens on **TCP port 12345** (TLS). Keep both devices on the same subnet.

> Keep that token private. It can arm/disarm the panel — treat it like a house key.

## C. Bridge the panel into HA with qolsysgw

`qolsysgw` is a gateway that publishes the alarm partition + door/window zones to Home
Assistant over **MQTT**. It runs as an **AppDaemon** app.

1. HA → **Settings → Add-ons → Add-on Store**:
   - Install **Mosquitto broker**. Start it. Create an MQTT user/password
     (Settings → People/Users, or the add-on's config) and add the **MQTT** integration
     (it's usually auto-discovered → Configure).
   - Install **AppDaemon**.
2. Add **qolsysgw** from its GitHub repo into AppDaemon's `apps` folder and fill in its
   `apps.yaml` with: the **panel IP**, the **secure token** from step B4, and your
   **MQTT** host/user/password. (Follow the qolsysgw README for the exact config keys —
   they occasionally change.)
3. Restart AppDaemon. Within a minute you should see new HA entities:
   - an **`alarm_control_panel.*`** entity (arm/disarm + current state)
   - **`binary_sensor.*`** entities for each door/window/motion zone
4. Test in HA: Settings → Devices & Services → Entities → find the alarm panel →
   try **arm/disarm** from HA itself. If that works, FamilyHub will too.

## D. Create the token FamilyHub will use

1. In HA, click your **profile** (bottom-left) → **Security** →
   **Long-Lived Access Tokens** → **Create Token** → name it `familyhub`.
2. Copy it once (you can't see it again). This goes into FamilyHub's **`.env`** later as:
   ```
   HA_URL=http://<home-assistant-ip>:8123
   HA_TOKEN=<the long-lived token>
   ```
   It stays **server-side only** — FamilyHub never sends it to the browser.

## E. Later (optional, when you want more than the alarm)

The IQ Panel's 3rd-party API is great for the **alarm + its sensors**, but it won't expose
full control of lights/locks paired to the panel. When you're ready to control those from
FamilyHub, pair them **directly to Home Assistant** instead:
- **Z-Wave/Zigbee:** add a USB stick to the HA Pi → Z-Wave JS / ZHA.
- **WLED / ESP32:** they show up automatically via the WLED and ESPHome integrations.
Each new device then appears in HA, and FamilyHub's Smart Home tab will list it with no
code changes.

---

### What "done" looks like
- `http://homeassistant.local:8123` loads and you can arm/disarm the panel **from HA**.
- You have a `familyhub` long-lived token saved for Phase 2.

When you reach that point, tell me — that's the green light to build FamilyHub's Smart
Home tab (tiles, scenes, status bar, PIN-pad arm/disarm) against your live HA.
