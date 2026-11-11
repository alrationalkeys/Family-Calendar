/*
  North Pole Village - Board B: TRAIN
  ------------------------------------------------------------
  Runs the Lionel train two ways (choose on the train Settings page):
   * Bluetooth (engine switch on BT): the board drives the engine like the
     Cab3 app does - your speed, volume, whistle, bell, smooth stops.
     The relay just powers the track while the train is in use.
   * Continuous (engine switch on Continuous): relay power on = runs,
     power off = stops. If Bluetooth ever can't connect, a run falls
     back to this automatically.

  - IR sensor 1 sees the train ENTERING the station -> short delay ->
    power off -> train waits at the platform (red signal, bell, mist)
    -> power back on (green signal) -> train leaves.
  - Counts laps. When the last lap reaches the station it stops there
    and stays until it's told to go again.

  Board: "ESP32 Dev Module"  (Arduino IDE 2, esp32 core 3.x). Library: "ESP32Servo".
  Serial Monitor 115200: type  h  for the test menu.
  Phone (same WiFi): http://village-train.local
  ------------------------------------------------------------
  ONLY EDIT THE "SETTINGS" SECTION BELOW.
*/

#include <WiFi.h>
#include <ESPmDNS.h>
#include <ArduinoOTA.h>
#include <WiFiUdp.h>
#include <WebServer.h>
#include <time.h>
#include <ESP32Servo.h>   // Library Manager: "ESP32Servo" (for the crossing gates)
#include <Preferences.h>
#include "TrainBLE.h"      // Bluetooth engine control (its own tab)

// ======================= SETTINGS ===========================
// WiFi name/password live in secrets.h (the "secrets.h" tab). Updates never replace that file.
#include "secrets.h"
#include "TrainPage.h"      // the phone page (HTML)
const char* FIRMWARE_VERSION = "B-2026.11.01d";

const char* MY_NAME = "village-train";   // this board -> http://village-train.local
const char* FX_NAME = "village-fx";      // Board A (bell + station mist)
const char* FX_IP_OVERRIDE = "";         // e.g. "192.168.1.51" if the name isn't found

// Station stop tuning (adjust after watching the train)
int STOP_DELAY_MS        = 0;      // after the engine reaches sensor 1, wait this long (ms), then cut power.
                                   // 0 = stop right at sensor 1. Raise it (e.g. 300) to stop a little further on.
// (wait at the platform, stop every lap, speed, volume... are on the phone's train Settings page)
int  MAX_RUN_MINUTES     = 10;     // safety: power off if the train has run this long
int  SENSOR_IGNORE_MS    = 5000;   // after a sensor fires, ignore it this long (the cars pass by)
int  DEPART_TIMEOUT_MS   = 8000;   // if sensor 2 never fires after leaving, carry on anyway
int  DEPART_CLEAR_MS     = 12000;  // after leaving the station, ignore sensor 1 this long (the cars roll past it)

// Railroad crossing (set CROSSING_ENABLED = false if you don't build it)
bool CROSSING_ENABLED     = true;
int  GATE_UP_ANGLE        = 90;     // servo angle with the gate arm pointing up
int  GATE_DOWN_ANGLE      = 0;      // servo angle with the arm across the road (try 180 if it goes the wrong way)
int  GATE2_REVERSED       = 1;      // the second gate faces the other way, so it turns the opposite direction
int  CROSSING_CLEAR_MS    = 3000;   // gates rise this long after the last car has passed the crossing sensor

// Most IR sensor boards pull their output LOW when they see something.
// If yours is the other way round, change LOW to HIGH.
const int SENSOR_ACTIVE = LOW;
// Relay jumper on "H": HIGH = relay on = track powered.
const int RELAY_ON = HIGH;
// ===================== END OF SETTINGS ======================

// ----------------------- PIN MAP ----------------------------
const int PIN_RELAY   = 26;
const int PIN_IR_IN   = 34;  // sensor 1: train entering the station
const int PIN_IR_OUT  = 35;  // sensor 2: train leaving the station
const int PIN_GREEN   = 25;
const int PIN_RED     = 27;
const int PIN_XING_IR = 32;  // crossing sensor (just before the road)
const int PIN_GATE1   = 18;  // crossing gate servo 1
const int PIN_GATE2   = 19;  // crossing gate servo 2
const int PIN_FLASH_A = 21;  // crossbuck lamps A (left lamp on both crossbucks)
const int PIN_FLASH_B = 22;  // crossbuck lamps B (right lamp on both crossbucks)

// ----------------------- STATE ------------------------------
enum State { ST_STOPPED, ST_RUNNING, ST_APPROACH, ST_WAITING, ST_DEPARTING, ST_CONNECTING };
State state = ST_STOPPED;
int lapsLeft = 0;
unsigned long stateAt = 0, runStartedAt = 0;
unsigned long inIgnoreUntil = 0, outIgnoreUntil = 0;
bool lastIn = false, lastOut = false;
int lapsDone = 0;

// ---- phone settings (saved on the board) ----
Preferences prefs;
int setCtrl = 1;        // 1 = Bluetooth, 0 = Continuous (relay only)
int setSpeed = 12;      // cruising speed 1-31
int setVol = 5;         // engine master volume 1-7
int setChuff = 3;       // steam chuff volume 0-7
int setRampMs = 2000;   // time to slow from cruising speed to a stop (and to get up to speed)
int setWaitS = 15;      // seconds waiting at the platform (when stopping every lap)
int setEveryLap = 0;    // 1 = stop at the station every lap
int setWhistle = 1;     // whistle when leaving
int setBell = 1;        // bell when arriving
int setKeepOnMin = 3;   // Bluetooth: keep track power on this many minutes after the last stop
int setDuckVol = 1;     // volume while a village show or song is playing (0 = silent)
unsigned long duckUntil = 0;   // the village asked us to be quiet until this time

// ---- Bluetooth run state ----
bool trackOn = false, btRun = false;
int curSpeed = 0, targetSpeed = 0;
unsigned long rampNext = 0, hornOffAt = 0, bellOffAt = 0, powerOffAt = 0, connectAt = 0, btTestAt = 0;
int connectTries = 0;

WebServer server(80);
IPAddress fxIP;
WiFiUDP disc;              // discovery + sending log lines to Board A
const int DISC_PORT = 4210;

// ---- live event log (shown on the phone page) ----
const int LOG_LINES = 60;
String logBuf[LOG_LINES];
int logHead = 0, logCount = 0;
unsigned long logSeq = 0;
void logln(const String& s) {
  Serial.println(s);
  char stamp[16];
  struct tm t;
  if (getLocalTime(&t, 0)) strftime(stamp, sizeof(stamp), "%H:%M:%S", &t);
  else snprintf(stamp, sizeof(stamp), "+%lus", millis() / 1000);
  logBuf[logHead] = String(stamp) + "  " + s;
  logHead = (logHead + 1) % LOG_LINES;
  if (logCount < LOG_LINES) logCount++;
  logSeq++;
  // copy the line to Board A's log too (one quick network message, never waits)
  if (WiFi.status() == WL_CONNECTED && fxIP != IPAddress(0, 0, 0, 0)) {
    disc.beginPacket(fxIP, DISC_PORT);
    disc.print("TLOG:");
    disc.print(s.substring(0, 180));
    disc.endPacket();
  }
}
String logText() {   // oldest first; first line is the sequence number so the page knows if anything changed
  String out = String(logSeq) + "\n";
  for (int i = 0; i < logCount; i++) out += logBuf[(logHead - logCount + i + LOG_LINES) % LOG_LINES] + "\n";
  return out;
}

const char* stateName(State s) {
  switch (s) {
    case ST_STOPPED: return "stopped at station";
    case ST_RUNNING: return "running";
    case ST_APPROACH: return "arriving at station";
    case ST_WAITING: return "waiting at platform";
    case ST_DEPARTING: return "leaving station";
    case ST_CONNECTING: return "connecting to the engine (Bluetooth)";
  }
  return "?";
}

void trackPower(bool on) {
  trackOn = on;
  if (!on) { lc::drop(); curSpeed = targetSpeed = 0; }
  digitalWrite(PIN_RELAY, on ? RELAY_ON : !RELAY_ON);
  digitalWrite(PIN_GREEN, on ? HIGH : LOW);
  digitalWrite(PIN_RED,   on ? LOW : HIGH);
  logln(on ? "Track power ON  (green)" : "Track power OFF (red)");
}

void setState(State s) { state = s; stateAt = millis(); logln(String("Train: ") + stateName(s) + "  laps left " + lapsLeft); }

// tell Board A the train is at the station (bell + mist): one quick network message
void tellFxStation() {
  if (WiFi.status() != WL_CONNECTED) return;
  if (strlen(FX_IP_OVERRIDE)) fxIP.fromString(FX_IP_OVERRIDE);
  if (fxIP == IPAddress(0, 0, 0, 0)) fxIP = MDNS.queryHost(FX_NAME, 1500);
  if (fxIP == IPAddress(0, 0, 0, 0)) { logln("Board A not found (bell/mist skipped)"); return; }
  for (int i = 0; i < 2; i++) {          // sent twice in case one gets lost; Board A ignores the repeat
    disc.beginPacket(fxIP, DISC_PORT); disc.print("TSTATION"); disc.endPacket(); delay(5);
  }
}

// ---- commands ----
bool ducked() { return duckUntil && (long)(millis() - duckUntil) < 0; }
// set the engine's volume: quieter while the village is playing a show or song
void applyVolume() {
  if (!btRun || !lc::connected()) return;
  if (ducked()) { lc::volume(setDuckVol); lc::chuff(0); }
  else { lc::volume(setVol); lc::chuff(setChuff); }
}

void toot(int ms) { lc::horn(true); hornOffAt = millis() + ms; }

// pull out of the station (power is already on)
void depart() {
  outIgnoreUntil = 0;
  inIgnoreUntil = millis() + DEPART_CLEAR_MS; lastIn = true;   // don't count our own cars leaving
  if (btRun) {
    applyVolume(); lc::forward();
    if (setWhistle) toot(1200);
    targetSpeed = setSpeed;
  }
  setState(ST_DEPARTING);
}

// power the track and either connect over Bluetooth or just go (Continuous)
void powerAndGo() {
  powerOffAt = 0;
  if (setCtrl == 1) {
    if (!trackOn) trackPower(true);
    if (lc::connected()) { btRun = true; depart(); }
    else { connectTries = 0; connectAt = millis() + 2500; setState(ST_CONNECTING); }   // engine needs ~2 s to wake up
  } else {
    btRun = false;
    trackPower(true);
    depart();
  }
}

void go(int laps) {
  if (laps < 1) laps = 1;
  if (state == ST_STOPPED || state == ST_WAITING) {
    lapsLeft = laps;
    runStartedAt = millis();
    powerAndGo();
  } else {
    lapsLeft += laps;          // already moving: add laps
    logln(String("Added laps, now ") + lapsLeft);
  }
}

void stopNow() {
  lapsLeft = 0;
  if (btRun && lc::connected()) lc::speed(0);
  btRun = false; powerOffAt = 0;
  trackPower(false);
  setState(ST_STOPPED);
}

// the train has stopped at the platform
void arrived() {
  if (btRun && setBell) { lc::bell(true); bellOffAt = millis() + 3000; }
  tellFxStation();
  if (lapsLeft <= 0) {
    lapsLeft = 0;
    setState(ST_STOPPED);
    if (btRun) powerOffAt = millis() + (unsigned long)max(setKeepOnMin, 0) * 60000UL + 5000;   // let the bell finish
  } else setState(ST_WAITING);
}

// ---- sensors ----
// Steady filter: a car over a sensor lasts a good fraction of a second; an empty
// (unplugged) pin flickers in microseconds. Only accept readings that hold SENSOR_STEADY_MS.
const unsigned long SENSOR_STEADY_MS = 120;
bool sRaw[40], sStable[40]; unsigned long sSince[40];
bool sensorActive(int pin) {
  bool r = digitalRead(pin) == SENSOR_ACTIVE;
  if (r != sRaw[pin]) { sRaw[pin] = r; sSince[pin] = millis(); }
  if (sStable[pin] != sRaw[pin] && millis() - sSince[pin] >= SENSOR_STEADY_MS) sStable[pin] = sRaw[pin];
  return sStable[pin];
}

bool sensorEdge(int pin, bool& last, unsigned long& ignoreUntil) {
  bool active = sensorActive(pin);
  bool edge = active && !last && (long)(millis() - ignoreUntil) >= 0;
  last = active;
  if (edge) ignoreUntil = millis() + SENSOR_IGNORE_MS;
  return edge;
}

// ---------------- CROSSING ----------------
Servo gate1, gate2;
bool xingActive = false, gatesAttached = false;
unsigned long xingLastSeen = 0, xingFlashAt = 0, gateStepAt = 0, gatesIdleAt = 0;
int gatePos = 90, gateTarget = 90;
bool flashPhase = false;

void gatesWrite(int a) {
  if (!gatesAttached) {
    gate1.setPeriodHertz(50); gate2.setPeriodHertz(50);
    gate1.attach(PIN_GATE1, 500, 2400); gate2.attach(PIN_GATE2, 500, 2400);
    gatesAttached = true;
  }
  gate1.write(a);
  gate2.write(GATE2_REVERSED ? 180 - a : a);
}

void crossingDown(const char* why) {
  if (!xingActive) logln(String("Crossing: gates down (") + why + ")");
  xingActive = true; xingLastSeen = millis(); gateTarget = GATE_DOWN_ANGLE;
}

void updateCrossing() {
  if (!CROSSING_ENABLED) return;
  unsigned long now = millis();
  if (sensorActive(PIN_XING_IR)) crossingDown("train");
  if (xingActive && now - xingLastSeen > (unsigned long)CROSSING_CLEAR_MS) {
    xingActive = false; gateTarget = GATE_UP_ANGLE; logln("Crossing: clear, gates up");
  }
  // flash the crossbuck lamps while active, and until the gates are fully up
  bool flashing = xingActive || gatePos != gateTarget;
  if (flashing && now - xingFlashAt > 500) {
    xingFlashAt = now; flashPhase = !flashPhase;
    digitalWrite(PIN_FLASH_A, flashPhase); digitalWrite(PIN_FLASH_B, !flashPhase);
  }
  if (!flashing) { digitalWrite(PIN_FLASH_A, LOW); digitalWrite(PIN_FLASH_B, LOW); }
  // move the gates slowly: 1 degree every 20 ms (about 2 s for 90 degrees)
  if (gatePos != gateTarget && now - gateStepAt > 20) {
    gateStepAt = now; gatePos += gateTarget > gatePos ? 1 : -1; gatesWrite(gatePos); gatesIdleAt = now;
  }
  // stop driving the servos 1 s after they arrive, so they don't buzz
  if (gatesAttached && gatePos == gateTarget && now - gatesIdleAt > 1000) {
    gate1.detach(); gate2.detach(); gatesAttached = false;
  }
}

unsigned long relayTestUntil = 0;
void update() {
  if (relayTestUntil && (long)(millis() - relayTestUntil) >= 0) {
    relayTestUntil = 0;
    if (state == ST_STOPPED) { trackPower(false); logln("Relay test: OFF"); }
  }
  unsigned long now = millis();

  // Bluetooth helpers: speed ramps, whistle/bell timers, idle power-off, lost connection
  if (btRun && curSpeed != targetSpeed && (long)(now - rampNext) >= 0 && lc::connected()) {
    curSpeed += targetSpeed > curSpeed ? 1 : -1;
    lc::speed(curSpeed);
    rampNext = now + max(40, setRampMs / max(1, setSpeed));
  }
  if (hornOffAt && (long)(now - hornOffAt) >= 0) { hornOffAt = 0; lc::horn(false); }
  if (duckUntil && (long)(now - duckUntil) >= 0) { duckUntil = 0; applyVolume(); logln("Train volume back to normal"); }
  if (bellOffAt && (long)(now - bellOffAt) >= 0) { bellOffAt = 0; lc::bell(false); }
  if (powerOffAt && (long)(now - powerOffAt) >= 0 && state == ST_STOPPED) {
    powerOffAt = 0; btRun = false; trackPower(false); logln("Track power off (train idle)");
  }
  if (btTestAt && (long)(now - btTestAt) >= 0) {
    btTestAt = 0;
    if (lc::connect()) { lc::volume(setVol); toot(1500); logln("Bluetooth test OK: whistle!"); }
    else logln("Bluetooth test failed: check the engine switch is on BT and it's on powered track");
  }
  if (btRun && state != ST_STOPPED && state != ST_CONNECTING && !lc::connected()) {
    logln("Bluetooth: lost the engine, stopping for safety"); stopNow(); return;
  }

  bool inEdge  = sensorEdge(PIN_IR_IN,  lastIn,  inIgnoreUntil);
  bool outEdge = sensorEdge(PIN_IR_OUT, lastOut, outIgnoreUntil);
  if (inEdge)  logln("Sensor 1 (entering) saw the train");
  if (outEdge) logln("Sensor 2 (leaving) saw the train");

  // safety limit
  if (state != ST_STOPPED && state != ST_WAITING && now - runStartedAt > (unsigned long)MAX_RUN_MINUTES * 60000UL) {
    logln("Safety: max run time reached"); stopNow(); return;
  }

  switch (state) {
    case ST_STOPPED: break;

    case ST_DEPARTING:
      if (outEdge || now - stateAt > (unsigned long)DEPART_TIMEOUT_MS) setState(ST_RUNNING);
      break;

    case ST_CONNECTING:
      if ((long)(now - connectAt) >= 0) {
        if (lc::connect()) { btRun = true; depart(); }
        else if (++connectTries < 3) connectAt = millis() + 1000;
        else {
          logln("Bluetooth didn't connect: running in Continuous mode this time (engine switch on Continuous?)");
          btRun = false; depart();
        }
      }
      break;

    case ST_RUNNING:
      if (inEdge) {
        lapsLeft--; lapsDone++;
        if (lapsLeft <= 0 || setEveryLap) { if (btRun) targetSpeed = 0; setState(ST_APPROACH); }
        else logln(String("Lap done, ") + lapsLeft + " to go (not stopping)");
      }
      break;

    case ST_APPROACH:
      if (btRun) {                                   // slowing down smoothly
        if (curSpeed == 0 && now - stateAt > 600) arrived();
      } else if (now - stateAt >= (unsigned long)STOP_DELAY_MS) {
        trackPower(false);
        arrived();
      }
      break;

    case ST_WAITING:
      if (now - stateAt >= (unsigned long)setWaitS * 1000UL) powerAndGo();
      break;
  }
}

// ---- web ----
// The phone page lives in TrainPage.h (its own tab).


String statusText() {
  String ver = String("\nCode version: ") + FIRMWARE_VERSION;
  String x = String("\nCrossing: ") + (xingActive ? "GATES DOWN" : "clear") + "   sensor: " + (sensorActive(PIN_XING_IR) ? "SEES TRAIN" : "clear");
  String s = String("State: ") + stateName(state) + "\nLaps left: " + lapsLeft + "   laps done since power-up: " + lapsDone;
  s += String("\nSensor 1 (in): ") + (sensorActive(PIN_IR_IN) ? "SEES TRAIN" : "clear");
  s += String("   Sensor 2 (out): ") + (sensorActive(PIN_IR_OUT) ? "SEES TRAIN" : "clear");
  s += String("\nControl: ") + (setCtrl == 1 ? "Bluetooth" : "Continuous (relay)");
  if (setCtrl == 1) s += lc::connected() ? String(" - connected to ") + lc::engineName + "   speed " + curSpeed + "/31" : String(" - not connected");
  s += String("   track power ") + (trackOn ? "ON" : "off");
  return s + x + ver;
}

void loadSettings() {
  prefs.begin("train", true);
  setCtrl = prefs.getInt("ctrl", setCtrl);       setSpeed = prefs.getInt("speed", setSpeed);
  setVol = prefs.getInt("vol", setVol);          setChuff = prefs.getInt("chuff", setChuff);
  setRampMs = prefs.getInt("ramp", setRampMs);   setWaitS = prefs.getInt("wait", setWaitS);
  setEveryLap = prefs.getInt("every", setEveryLap); setWhistle = prefs.getInt("whistle", setWhistle);
  setBell = prefs.getInt("bell", setBell);       setKeepOnMin = prefs.getInt("keepon", setKeepOnMin);
  setDuckVol = prefs.getInt("duck", setDuckVol);
  prefs.end();
}
void saveSettings() {
  prefs.begin("train", false);
  prefs.putInt("ctrl", setCtrl);   prefs.putInt("speed", setSpeed); prefs.putInt("vol", setVol);
  prefs.putInt("chuff", setChuff); prefs.putInt("ramp", setRampMs); prefs.putInt("wait", setWaitS);
  prefs.putInt("every", setEveryLap); prefs.putInt("whistle", setWhistle); prefs.putInt("bell", setBell);
  prefs.putInt("keepon", setKeepOnMin); prefs.putInt("duck", setDuckVol);
  prefs.end();
}

String numRow(const char* label, const char* key, int v, int lo, int hi, const char* help) {
  return String("<p><b>") + label + "</b><br><input type=number name=" + key + " value=" + v + " min=" + lo + " max=" + hi +
         "> <small>" + help + "</small></p>";
}
String chkRow(const char* label, const char* key, int v) {
  return String("<p><label><input type=checkbox name=") + key + " value=1" + (v ? " checked" : "") + "> " + label + "</label></p>";
}
String settingsPage(bool saved) {
  String h = "<!doctype html><html><head><meta name=viewport content='width=device-width,initial-scale=1'><title>Train settings</title>"
             "<style>body{font-family:sans-serif;margin:16px;background:#101820;color:#e8f0f8}input,select{font-size:17px;padding:6px;border-radius:6px}"
             "small{color:#9ab}button{font-size:17px;padding:12px 20px;border:0;border-radius:10px;background:#1f5a32;color:#fff}a{color:#9cf}</style></head><body>"
             "<h1>Train settings</h1>";
  if (saved) h += "<p style='color:#7CFC7C'>Saved.</p>";
  h += "<form action=/save><p><b>Control</b><br><select name=ctrl>";
  h += String("<option value=1") + (setCtrl == 1 ? " selected" : "") + ">Bluetooth (engine switch on BT)</option>";
  h += String("<option value=0") + (setCtrl == 0 ? " selected" : "") + ">Continuous (engine switch on Continuous)</option></select></p>";
  h += numRow("Speed", "speed", setSpeed, 1, 31, "1 = crawl, 31 = flat out. Bluetooth only.");
  h += numRow("Overall volume", "vol", setVol, 0, 7, "0 silent - 7 loud. Bluetooth only.");
  h += numRow("Engine sound volume", "chuff", setChuff, 0, 7, "steam chuff and engine noises, 0 = off. Bluetooth only.");
  h += numRow("Volume during village songs", "duck", setDuckVol, 0, 7, "the train goes this quiet (and stops chuffing) while a show or the carolers play.");
  h += numRow("Slow-down time (ms)", "ramp", setRampMs, 0, 8000, "how gently it stops at the station and gets going. Bluetooth only.");
  h += chkRow("Stop at the station every lap", "every", setEveryLap);
  h += numRow("Wait at the platform (seconds)", "wait", setWaitS, 3, 120, "when stopping every lap");
  h += chkRow("Whistle when leaving", "whistle", setWhistle);
  h += chkRow("Bell when arriving", "bell", setBell);
  h += numRow("Keep track powered after the last stop (minutes)", "keepon", setKeepOnMin, 0, 60, "Bluetooth: next run starts without reconnecting");
  h += "<p><button>Save</button></p></form><p><a href=/>Back to the train</a>";
  if (fxIP != IPAddress(0, 0, 0, 0)) h += String(" &nbsp;|&nbsp; <a href='http://") + fxIP.toString() + "/'>Back to the village</a>";
  h += "</p></body></html>";
  return h;
}

void setupWeb() {
  server.on("/", []() { server.send_P(200, "text/html", PAGE); });
  server.on("/status", []() { server.send(200, "text/plain", statusText()); });
  server.on("/fx", []() {                      // jump to Board A's village page
    server.sendHeader("Location", fxIP == IPAddress(0, 0, 0, 0) ? String("http://village-fx.local/") : String("http://") + fxIP.toString() + "/");
    server.send(302, "text/plain", "");
  });
  server.on("/log", []() { server.send(200, "text/plain", logText()); });
  server.on("/logclear", []() { logHead = 0; logCount = 0; logSeq++; server.send(200, "text/plain", "ok"); });
  server.on("/go", []() { go(server.hasArg("laps") ? server.arg("laps").toInt() : 1); server.send(200, "text/plain", "ok"); });
  server.on("/stop", []() { stopNow(); server.send(200, "text/plain", "ok"); });
  server.on("/relaytest", []() {
    if (state == ST_STOPPED) { trackPower(true); relayTestUntil = millis() + 5000; logln("Relay test: ON for 5 seconds"); }
    else logln("Relay test skipped: the train is running");
    server.send(200, "text/plain", "ok");
  });
  server.on("/xing", []() { crossingDown("phone"); server.send(200, "text/plain", "ok"); });
  server.on("/settings", []() { server.send(200, "text/html", settingsPage(false)); });
  server.on("/save", []() {
    auto gi = [](const char* k, int lo, int hi, int cur) { return server.hasArg(k) ? constrain((int)server.arg(k).toInt(), lo, hi) : cur; };
    setCtrl = gi("ctrl", 0, 1, setCtrl);   setSpeed = gi("speed", 1, 31, setSpeed);
    setVol = gi("vol", 0, 7, setVol);      setChuff = gi("chuff", 0, 7, setChuff);
    setRampMs = gi("ramp", 0, 8000, setRampMs); setWaitS = gi("wait", 3, 120, setWaitS);
    setKeepOnMin = gi("keepon", 0, 60, setKeepOnMin);
    setDuckVol = gi("duck", 0, 7, setDuckVol);
    setEveryLap = server.hasArg("every") ? 1 : 0;   // unticked boxes aren't sent
    setWhistle = server.hasArg("whistle") ? 1 : 0;
    setBell = server.hasArg("bell") ? 1 : 0;
    saveSettings();
    logln(String("Settings saved: ") + (setCtrl ? "Bluetooth" : "Continuous") + ", speed " + setSpeed + ", volume " + setVol);
    if (btRun && lc::connected()) {                 // apply right away if the train is running
      applyVolume();
      if (state == ST_RUNNING || state == ST_DEPARTING) targetSpeed = setSpeed;
    }
    server.send(200, "text/html", settingsPage(true));
  });
  server.on("/bttest", []() {
    if (state != ST_STOPPED) { logln("Bluetooth test skipped: the train is running"); }
    else {
      if (!trackOn) trackPower(true);
      powerOffAt = millis() + 60000;               // power off again after a minute
      btTestAt = millis() + 2500;                  // give the engine time to wake up
      logln("Bluetooth test: track on, looking for the engine...");
    }
    server.send(200, "text/plain", "ok");
  });
  server.begin();
}

// ---- serial test menu ----
void printHelp() {
  logln("\n--- Village Train test menu (type, press Enter) ---");
  logln(" 1-9  run that many laps    s  STOP");
  logln(" p    relay test (on 3 s)   i  show sensors   h  this menu");
  logln(" x    crossing test (gates down, lamps flash, then up)");
}

void readSerial() {
  if (!Serial.available()) return;
  char ch = Serial.read();
  if (ch >= '1' && ch <= '9') go(ch - '0');
  else if (ch == 's') stopNow();
  else if (ch == 'i') logln(statusText());
  else if (ch == 'h') printHelp();
  else if (ch == 'p') { trackPower(true); delay(3000); trackPower(false); }
  else if (ch == 'x') crossingDown("test");
}

// ---- finding the other board: each board says "I'm here" on the network every 5 s ----
unsigned long nextAnnounce = 0;
void setupDiscovery() { if (WiFi.status() == WL_CONNECTED) disc.begin(DISC_PORT); }
void updateDiscovery() {
  if (WiFi.status() != WL_CONNECTED) return;
  if ((long)(millis() - nextAnnounce) >= 0) {
    nextAnnounce = millis() + 5000;
    disc.beginPacket(IPAddress(255, 255, 255, 255), DISC_PORT);
    disc.print(MY_NAME);
    disc.endPacket();
  }
  int n = disc.parsePacket();
  if (n <= 0) return;
  char buf[33]; int len = disc.read(buf, 32); if (len < 0) len = 0; buf[len] = 0;
  if (!strncmp(buf, "TDUCK:", 6)) {           // Board A: a song is starting (seconds), or 0 = done
    int secs = atoi(buf + 6);
    unsigned long want = millis() + (unsigned long)secs * 1000UL;
    if (secs <= 0) duckUntil = 0;
    else if (!ducked() || (long)(want - duckUntil) > 0) duckUntil = want;   // a shorter request never cuts a longer one short
    if (secs > 0) logln(String("Train quiet for ") + secs + " s (village song playing)");
    applyVolume();
    return;
  }
  if (!strcmp(buf, FX_NAME)) {
    IPAddress from = disc.remoteIP();
    if (from != fxIP) { fxIP = from; logln(String("Found ") + FX_NAME + " at " + from.toString()); }
    
  }
}

// ---- upload over WiFi (Arduino IDE: Tools > Port > network port) ----
void setupOTA() {
  if (WiFi.status() != WL_CONNECTED) { logln("WiFi upload not available (no WiFi): use USB"); return; }
  ArduinoOTA.setHostname(MY_NAME);
  ArduinoOTA.setPassword(OTA_PASSWORD);
  ArduinoOTA.onStart([]() { logln("WiFi upload starting... (don't unplug)"); });
  ArduinoOTA.onEnd([]() { logln("WiFi upload done, restarting"); });
  ArduinoOTA.onError([](ota_error_t e) { logln(String("WiFi upload error ") + (int)e); });
  ArduinoOTA.begin();
  logln(String("WiFi upload ready: ") + MY_NAME + " at " + WiFi.localIP().toString());
}

void setup() {
  pinMode(PIN_RELAY, OUTPUT);
  digitalWrite(PIN_RELAY, !RELAY_ON);          // track OFF first thing
  pinMode(PIN_GREEN, OUTPUT); pinMode(PIN_RED, OUTPUT);
  pinMode(PIN_XING_IR, INPUT_PULLUP);
  pinMode(PIN_FLASH_A, OUTPUT); pinMode(PIN_FLASH_B, OUTPUT);
  gatePos = gateTarget = GATE_UP_ANGLE;
  if (CROSSING_ENABLED) { gatesWrite(GATE_UP_ANGLE); gatesIdleAt = millis(); }
  pinMode(PIN_IR_IN, INPUT); pinMode(PIN_IR_OUT, INPUT);   // 34/35 have no pull-ups; the sensor boards drive them
  Serial.begin(115200);
  delay(300);
  logln("\n\nNorth Pole Village - Board B (train) starting");
  loadSettings();
  trackPower(false);

  WiFi.mode(WIFI_STA);
  WiFi.setHostname(MY_NAME);
  WiFi.begin(WIFI_SSID, WIFI_PASS);
  WiFi.setSleep(false);   // keep WiFi fully awake: steadier pages and WiFi uploads
  Serial.print("WiFi: connecting");
  for (int i = 0; i < 40 && WiFi.status() != WL_CONNECTED; i++) { delay(250); Serial.print("."); }
  if (WiFi.status() == WL_CONNECTED) {
    logln(String("\nWiFi: connected, IP ") + WiFi.localIP().toString());
    MDNS.begin(MY_NAME);
    MDNS.addService("http", "tcp", 80);
  } else logln("\nWiFi: NOT connected (it keeps trying)");
  setupOTA();
  setupDiscovery();
  setupWeb();
  logln(String("Firmware version ") + FIRMWARE_VERSION);
  printHelp();
}

unsigned long lastWifiCheck = 0;
void loop() {
  ArduinoOTA.handle();
  updateDiscovery();
  server.handleClient();
  readSerial();
  update();
  updateCrossing();
  if (millis() - lastWifiCheck > 30000) {
    lastWifiCheck = millis();
    if (WiFi.status() != WL_CONNECTED) WiFi.reconnect();
  }
}
