/*
  North Pole Village - Board A: EFFECTS   (v2: second sound spot + settings page)
  ------------------------------------------------------------
  Runs: main sound (DFPlayer 1), a second sound spot such as the
  carolers (DFPlayer 2 + its own speaker), 3 motion sensors,
  4 buttons, 2 mist modules, sleigh (motor + hall
  sensor) and the ice rink motor. Tells the WLED light controller
  which preset to show, and tells Board B (train) when to run.

  Board: "ESP32 Dev Module"   (Arduino IDE 2, esp32 core 3.x)
  Libraries (Library Manager): "DFRobotDFPlayerMini"

  Phone (same WiFi):  http://village-fx.local            controls
                      http://village-fx.local/settings   Rachell's settings
  Serial Monitor 115200: type  h  for test commands.
  ------------------------------------------------------------
  Most choices (hours, volumes, songs, show lengths, carolers) are on
  the phone SETTINGS page and are saved on the board. Only the WiFi
  and network names below need editing here.
*/

#include <WiFi.h>
#include <ESPmDNS.h>
#include <ArduinoOTA.h>
#include <WiFiUdp.h>
#include <WebServer.h>
#include <HTTPClient.h>
#include <Preferences.h>
#include <time.h>
#include <DFRobotDFPlayerMini.h>
#include "VillageTypes.h"
#include "VillagePage.h"    // the phone control page (HTML)   // the second tab: type definitions

// ======================= EDIT THESE =========================
// WiFi name/password live in secrets.h (the "secrets.h" tab). Updates never replace that file.
#include "secrets.h"
const char* FIRMWARE_VERSION = "A-2026.11.02d";

const char* MY_NAME     = "village-fx";      // this board  -> http://village-fx.local
const char* LIGHTS_NAME = "village-lights";  // WLED: Config > WiFi Setup > mDNS address
const char* TRAIN_NAME  = "village-train";   // Board B
// If the lights/train can't be found by name, type their IP here, e.g. "192.168.1.50"
const char* LIGHTS_IP_OVERRIDE = "";
const char* TRAIN_IP_OVERRIDE  = "";
const char* TIMEZONE = "EST5EDT,M3.2.0,M11.1.0";   // US Eastern

// Hardware details (change only if something behaves backwards)
const int MIST_ON_LEVEL     = LOW;    // NULLLAB mist boards run when S is LOW (blue light = misting). If backwards, change to HIGH
const int SLEIGH_MAX_SECONDS = 180;   // safety stop if the sleigh never gets home (one full loop must fit)
const int MIST_PUFF_SECONDS    = 8;
const int STATION_MIST_SECONDS = 10;
// ============================================================


// ----------------------- PIN MAP ----------------------------
// (matches section 4 of the Build Book)
const int PIN_DF_RX      = 16;  // main sound:  ESP32 receives <- DFPlayer 1 TX
const int PIN_DF_TX      = 17;  //              ESP32 sends -> 1k -> DFPlayer 1 RX
const int PIN_DF2_RX     = 13;  // sound spot 2: ESP32 receives <- DFPlayer 2 TX
const int PIN_DF2_TX     = 14;  //              ESP32 sends -> 1k -> DFPlayer 2 RX
const int PIN_PIR1       = 34;
const int PIN_PIR2       = 35;
const int PIN_PIR3       = 4;   // motion sensor at the sound spot (carolers)
const int PIN_BTN_TREE   = 5;   // tree button (wired to D5 on the board)
const int PIN_BTN_TRAIN  = 33;
const int PIN_BTN_RACH   = 32;
const int PIN_BTN_SPOT   = 25;  // carolers button (wired to D25 on the board)
const int PIN_MIST1      = 18;  // chimney
const int PIN_MIST2      = 19;  // station
const int PIN_HALL       = 21;  // LOW when the sleigh's magnet is near
const int PIN_RINK       = 23;  // MOSFET 1
const int PIN_SLEIGH     = 22;  // MOSFET 2
const int PIN_LAMPS      = 2;   // MOSFET 3: street lamps (also blinks the board's blue LED)

const int MOTOR_PWM_FREQ = 1000;
const int MOTOR_PWM_BITS = 8;

// =================== SAVED SETTINGS ==========================
// Everything here is editable from the phone settings page.
Settings S;

Field FIELDS[] = {
  {"manual", "MANUAL MODE: nothing happens on its own (testing)", &S.manual, 0, 1, true, "Village"},
  {"openH",  "Village opens at (hour, 0-23)",   &S.openHour, 0, 23, false, "Village"},
  {"closeH", "Village closes at (hour, 0-23)",  &S.closeHour, 0, 23, false, "Village"},
  {"awake",  "Stay awake after last motion (minutes)", &S.awakeMin, 1, 60, false, "Village"},
  {"vol",    "Main speaker volume (0-30)",      &S.volume, 0, 30, false, "Village"},
  {"rink",   "Rink speed (0-255)",              &S.rinkSpeed, 0, 255, false, "Village"},
  {"sleigh", "Sleigh speed (0-255)",            &S.sleighSpeed, 0, 255, false, "Village"},
  {"wLaps",  "Train laps when village wakes",   &S.wakeLaps, 0, 20, false, "Village"},
  {"bLaps",  "Train laps for the train button", &S.buttonLaps, 1, 20, false, "Village"},
  {"treeS",  "Tree show length (seconds)",      &S.treeSecs, 10, 600, false, "Shows"},
  {"rachS",  "Rachell's show length (seconds)", &S.rachellSecs, 10, 600, false, "Shows"},
  {"sWake",  "Sound: village wakes / sleigh",   &S.sndWake, 0, 255, false, "Main speaker sounds (file numbers, 0 = silent)"},
  {"sWhis",  "Sound: train button",             &S.sndWhistle, 0, 255, false, "Main speaker sounds (file numbers, 0 = silent)"},
  {"sHoho",  "Sound: windows (now and then)",   &S.sndHoho, 0, 255, false, "Main speaker sounds (file numbers, 0 = silent)"},
  {"sTree",  "Sound: tree show music",          &S.sndTree, 0, 255, false, "Main speaker sounds (file numbers, 0 = silent)"},
  {"sRach",  "Sound: Rachell's song",           &S.sndRachell, 0, 255, false, "Main speaker sounds (file numbers, 0 = silent)"},
  {"sStat",  "Sound: train at the station",     &S.sndStation, 0, 255, false, "Main speaker sounds (file numbers, 0 = silent)"},
  {"whSec",  "Train waits for the whistle (seconds, 0 = no wait)", &S.whistleSecs, 0, 30, false, "Main speaker sounds (file numbers, 0 = silent)"},
  {"ambOn",  "Random extras while awake (1 = on)", &S.ambOn, 0, 1, true, "Random extras (reindeer, Santa, sleigh bells)"},
  {"ambF",   "Extras: first file number",       &S.ambFirst, 1, 255, false, "Random extras (reindeer, Santa, sleigh bells)"},
  {"ambL",   "Extras: last file number",        &S.ambLast, 1, 255, false, "Random extras (reindeer, Santa, sleigh bells)"},
  {"ambMin", "Extras: shortest wait (minutes)", &S.ambMinMin, 1, 120, false, "Random extras (reindeer, Santa, sleigh bells)"},
  {"ambMax", "Extras: longest wait (minutes)",  &S.ambMaxMin, 1, 120, false, "Random extras (reindeer, Santa, sleigh bells)"},
  {"pOff",   "Lights preset: off",              &S.psOff, 1, 250, false, "Light presets (WLED preset numbers)"},
  {"pSleep", "Lights preset: sleepy",           &S.psSleepy, 1, 250, false, "Light presets (WLED preset numbers)"},
  {"pEve",   "Lights preset: evening",          &S.psEvening, 1, 250, false, "Light presets (WLED preset numbers)"},
  {"pTree",  "Lights preset: tree show",        &S.psTree, 1, 250, false, "Light presets (WLED preset numbers)"},
  {"pRach",  "Lights preset: Rachell's show",   &S.psRachell, 1, 250, false, "Light presets (WLED preset numbers)"},
  {"cOn",    "Carolers turned on",              &S.cOn, 0, 1, true, "Carolers (sound spot 2)"},
  {"cMot",   "Sing when someone walks up to them", &S.cMotion, 0, 1, true, "Carolers (sound spot 2)"},
  {"cBtn",   "Sing when their button is pressed",  &S.cButton, 0, 1, true, "Carolers (sound spot 2)"},
  {"cWake",  "Sing when the whole village wakes",  &S.cWithWake, 0, 1, true, "Carolers (sound spot 2)"},
  {"cRach",  "Sing during Rachell's show",      &S.cWithRach, 0, 1, true, "Carolers (sound spot 2)"},
  {"cEvery", "Also sing every ___ minutes (0 = no)", &S.cEvery, 0, 240, false, "Carolers (sound spot 2)"},
  {"cFirst", "Songs: first file number",        &S.cFirst, 1, 255, false, "Carolers (sound spot 2)"},
  {"cLast",  "Songs: last file number (random pick in between)", &S.cLast, 1, 255, false, "Carolers (sound spot 2)"},
  {"cVol",   "Carolers volume (0-30)",          &S.cVolume, 0, 30, false, "Carolers (sound spot 2)"},
  {"cPre",   "Light preset while singing (0 = none)", &S.cPreset, 0, 250, false, "Carolers (sound spot 2)"},
  {"cSecs",  "Keep that light preset for (seconds)", &S.cSecs, 5, 600, false, "Carolers (sound spot 2)"},
  {"cRest",  "Rest between songs (minutes)",    &S.cRest, 0, 60, false, "Carolers (sound spot 2)"},
  {"pir1",   "Motion sensor 1 (front) is plugged in", &S.pir1On, 0, 1, true, "Motion sensors (untick any that aren't wired)"},
  {"pir2",   "Motion sensor 2 (side) is plugged in",  &S.pir2On, 0, 1, true, "Motion sensors (untick any that aren't wired)"},
  {"pir3",   "Motion sensor 3 (carolers) is plugged in", &S.pir3On, 0, 1, true, "Motion sensors (untick any that aren't wired)"},
  {"lSleep", "Street lamps on while sleepy",    &S.lampsSleepy, 0, 1, true, "Street lamps"},
  {"lAwake", "Street lamps on when awake / shows", &S.lampsAwake, 0, 1, true, "Street lamps"},
};
const int NFIELDS = sizeof(FIELDS) / sizeof(FIELDS[0]);
Preferences prefs;

void loadSettings() {
  prefs.begin("village", true);
  for (int i = 0; i < NFIELDS; i++) *FIELDS[i].val = prefs.getInt(FIELDS[i].key, *FIELDS[i].val);
  prefs.end();
}
void saveSettings() {
  prefs.begin("village", false);
  for (int i = 0; i < NFIELDS; i++) prefs.putInt(FIELDS[i].key, *FIELDS[i].val);
  prefs.end();
}

// ----------------------- GLOBALS ----------------------------
WebServer server(80);
DFRobotDFPlayerMini dfplayer, dfplayer2;
bool soundOK = false, sound2OK = false;

Mode mode = MODE_CLOSED;
Mode modeAfterShow = MODE_SLEEPY;
unsigned long showEndsAt = 0;
unsigned long lastMotionAt = 0;
unsigned long nextSleighAt = 0, nextMistAt = 0, nextWindowAt = 0, nextAmbAt = 0, lastMainPlayAt = 0;
bool manualOverride = false;

IPAddress lightsIP, trainIP;

Motor rink   = { PIN_RINK, 0, 0, 0 };
Motor sleigh = { PIN_SLEIGH, 0, 0, 0 };

SleighState sleighState = SL_HOME;
unsigned long sleighStartedAt = 0;

unsigned long mist1Until = 0, mist2Until = 0;

Button btnTree  = { PIN_BTN_TREE,  HIGH, HIGH, 0, "TREE" };
Button btnTrain = { PIN_BTN_TRAIN, HIGH, HIGH, 0, "TRAIN" };
Button btnRach  = { PIN_BTN_RACH,  HIGH, HIGH, 0, "RACHELL" };
Button btnSpot  = { PIN_BTN_SPOT,  HIGH, HIGH, 0, "CAROLERS" };

bool pir1Last = false, pir2Last = false, pir3Last = false;
// Motion "steady" filter: a real sensor holds its signal for seconds; an empty pin
// flickers in microseconds. Only accept a change that lasts PIR_STEADY_MS.
const unsigned long PIR_STEADY_MS = 250;
Steady pirS[3] = { {false, false, 0}, {false, false, 0}, {false, false, 0} };
bool steadyRead(Steady& st, bool enabled, int pin) {
  bool r = enabled && digitalRead(pin) == HIGH;
  if (r != st.raw) { st.raw = r; st.since = millis(); }
  if (st.stable != st.raw && millis() - st.since >= PIR_STEADY_MS) st.stable = st.raw;
  return st.stable;
}

// carolers state
bool carolLightsOn = false;
unsigned long carolLightsUntil = 0;
unsigned long lastCarolAt = 0;
bool everCaroled = false;

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
}
String logText() {   // oldest first; first line is the sequence number so the page knows if anything changed
  String out = String(logSeq) + "\n";
  for (int i = 0; i < logCount; i++) out += logBuf[(logHead - logCount + i + LOG_LINES) % LOG_LINES] + "\n";
  return out;
}

const char* modeName(Mode m) {
  switch (m) {
    case MODE_CLOSED: return "closed";
    case MODE_SLEEPY: return "sleepy";
    case MODE_AWAKE: return "awake";
    case MODE_TREE_SHOW: return "tree show";
    case MODE_RACHELL: return "Rachell show";
  }
  return "?";
}

int presetForMode(Mode m) {
  switch (m) {
    case MODE_CLOSED: return S.psOff;
    case MODE_SLEEPY: return S.psSleepy;
    case MODE_AWAKE: return S.psEvening;
    case MODE_TREE_SHOW: return S.psTree;
    case MODE_RACHELL: return S.psRachell;
  }
  return S.psEvening;
}

// ===================== NETWORK HELPERS =======================
bool resolve(const char* name, const char* overrideIP, IPAddress& out) {
  if (overrideIP && strlen(overrideIP) > 0) return out.fromString(overrideIP);
  if (out != IPAddress(0, 0, 0, 0)) return true;
  IPAddress ip = MDNS.queryHost(name, 1000);
  Preferences np; np.begin("net", false);
  String key = String(name).substring(0, 15);
  if (ip != IPAddress(0, 0, 0, 0)) {
    out = ip; logln(String("Found ") + name + " at " + ip.toString());
    if (np.getString(key.c_str(), "") != ip.toString()) np.putString(key.c_str(), ip.toString());   // remember it
    np.end(); return true;
  }
  String saved = np.getString(key.c_str(), ""); np.end();
  if (saved.length() && out.fromString(saved)) { logln(String("Using last known address for ") + name + ": " + saved); return true; }
  logln(String("Could not find ") + name + ".local");
  return false;
}

void setLightsPreset(int preset, int transitionTenths = 30) {
  if (preset <= 0 || WiFi.status() != WL_CONNECTED) return;
  if (!resolve(LIGHTS_NAME, LIGHTS_IP_OVERRIDE, lightsIP)) return;
  HTTPClient http;
  http.setTimeout(1500);
  http.begin(String("http://") + lightsIP.toString() + "/json/state");
  http.addHeader("Content-Type", "application/json");
  int code = http.POST(String("{\"ps\":") + preset + ",\"tt\":" + transitionTenths + "}");
  http.end();
  logln(String("Lights -> preset ") + preset + " (" + code + ")");
  if (code <= 0) lightsIP = IPAddress(0, 0, 0, 0);
}

// Train start waits until the whistle has finished (set S.whistleSecs to the clip length).
int pendingTrainLaps = 0;
unsigned long pendingTrainAt = 0;
void trainAfterWhistle(int laps) {
  bool show = (mode == MODE_TREE_SHOW || mode == MODE_RACHELL);
  if (!show && S.sndWhistle > 0 && S.whistleSecs > 0) {
    play(S.sndWhistle);
    pendingTrainLaps = laps;
    pendingTrainAt = millis() + (unsigned long)S.whistleSecs * 1000UL;
    logln(String("Train starts after whistle (") + S.whistleSecs + " s)");
  } else {
    trainGo(laps);           // inside a show, or no whistle set: go right away
  }
}

void trainGo(int laps) {
  if (laps <= 0 || WiFi.status() != WL_CONNECTED) return;
  if (!resolve(TRAIN_NAME, TRAIN_IP_OVERRIDE, trainIP)) return;
  HTTPClient http;
  http.setTimeout(1500);
  http.begin(String("http://") + trainIP.toString() + "/go?laps=" + laps);
  int code = http.GET();
  http.end();
  logln(String("Train -> go ") + laps + " laps (" + code + ")");
  if (code <= 0) trainIP = IPAddress(0, 0, 0, 0);
}

// ---- train hub: ask Board B for its status / send it simple commands ----
unsigned long trainRetryAt = 0;          // after a failure, wait before trying again (keeps this page fast)
String trainStatusCache = "Looking for the train board...";
String pendingTrainCmd = "";
unsigned long lastTrainView = 0, nextTrainPoll = 0;
String trainRequest(const String& path) {
  if (WiFi.status() != WL_CONNECTED) return "";
  if ((long)(millis() - trainRetryAt) < 0) return "";
  if (!resolve(TRAIN_NAME, TRAIN_IP_OVERRIDE, trainIP)) { trainRetryAt = millis() + 20000; return ""; }
  HTTPClient http;
  http.setConnectTimeout(600);
  http.setTimeout(700);
  http.begin(String("http://") + trainIP.toString() + path);
  int code = http.GET();
  String body = code == 200 ? http.getString() : "";
  http.end();
  if (code <= 0) { trainIP = IPAddress(0, 0, 0, 0); trainRetryAt = millis() + 20000; }
  return body;
}

// Background job: send queued train commands, and refresh the train status
// (only while someone has the page open, every 4 s).
void updateTrainHub() {
  if (pendingTrainCmd.length()) {
    String p = pendingTrainCmd; pendingTrainCmd = "";
    trainRetryAt = 0;                                  // a button press always tries right away
    if (trainRequest(p) == "") logln("Train board not reachable");
    nextTrainPoll = 0;
    return;
  }
  if (millis() - lastTrainView > 15000 || (long)(millis() - nextTrainPoll) < 0) return;
  nextTrainPoll = millis() + 4000;
  String r = trainRequest("/status");
  trainStatusCache = r.length() ? r : "Train board not found (is it powered and on WiFi?)";
}

// ========================= SOUND ============================
void play(int n) {
  if (n <= 0) return;
  if (!soundOK) { logln(String("(main sound not ready) would play ") + n); return; }
  dfplayer.playMp3Folder(n);
  lastMainPlayAt = millis();
  logln(String("Main speaker: ") + n);
}

void play2(int n) {
  if (n <= 0) return;
  if (!sound2OK) { logln(String("(carolers sound not ready) would play ") + n); return; }
  dfplayer2.volume(S.cVolume);
  dfplayer2.playMp3Folder(n);
  logln(String("Carolers speaker: ") + n);
}

// ========================= MOTORS ===========================
void motorWrite(Motor& m, int duty) { m.current = duty; ledcWrite(m.pin, duty); }
void updateMotor(Motor& m) {
  if (m.current == m.target) return;
  if (millis() - m.lastStep < 8) return;
  m.lastStep = millis();
  motorWrite(m, m.current + (m.target > m.current ? 1 : -1));
}
void rinkOn()  { rink.target = S.rinkSpeed; logln("Rink on"); }
void rinkOff() { rink.target = 0; logln("Rink off"); }

// ========================= SLEIGH ===========================
bool sleighAtHome() { return digitalRead(PIN_HALL) == LOW; }
void sleighFly() {
  if (sleighState != SL_HOME) return;
  sleighState = SL_LEAVING; sleighStartedAt = millis();
  sleigh.target = S.sleighSpeed;
  logln("Sleigh: take off");
}
void sleighStop(const char* why) {
  sleigh.target = 0; motorWrite(sleigh, 0); sleighState = SL_HOME;
  logln(String("Sleigh: stop (") + why + ")");
}
void updateSleigh() {
  if (sleighState == SL_HOME) return;
  unsigned long t = millis() - sleighStartedAt;
  if (t > (unsigned long)SLEIGH_MAX_SECONDS * 1000UL) { sleighStop("timeout - check magnet/sensor"); return; }
  if (sleighState == SL_LEAVING) {
    if ((!sleighAtHome() && t > 500) || t > 10000) { sleighState = SL_FLYING; logln("Sleigh: in the air"); }
  } else if (sleighAtHome() && t > 3000) sleighStop("home");
}

// ========================== MIST ============================
void mistWrite(int pin, bool on) { digitalWrite(pin, on ? MIST_ON_LEVEL : !MIST_ON_LEVEL); }
// Mist is turned off for now. Set MIST_ENABLED to true to bring it back.
const bool MIST_ENABLED = false;
void mistChimney(int seconds) { if (!MIST_ENABLED) return; mist1Until = millis() + seconds * 1000UL; mistWrite(PIN_MIST1, true); logln("Mist: chimney"); }
void mistStation(int seconds) { if (!MIST_ENABLED) return; mist2Until = millis() + seconds * 1000UL; mistWrite(PIN_MIST2, true); logln("Mist: station"); }
void updateMist() {
  if (mist1Until && (long)(millis() - mist1Until) >= 0) { mistWrite(PIN_MIST1, false); mist1Until = 0; }
  if (mist2Until && (long)(millis() - mist2Until) >= 0) { mistWrite(PIN_MIST2, false); mist2Until = 0; }
}

// ======================== CLOCK =============================
bool villageOpen() {
  if (manualOverride) return true;
  struct tm t;
  if (!getLocalTime(&t, 0)) return true;   // no clock yet: assume open
  if (S.openHour == S.closeHour) return true;
  if (S.openHour < S.closeHour) return t.tm_hour >= S.openHour && t.tm_hour < S.closeHour;
  return t.tm_hour >= S.openHour || t.tm_hour < S.closeHour;
}

// ======================= CAROLERS ===========================
// reason: "motion", "button", "timer", "wake", "rachell", "phone"
void carolersSing(const char* reason) {
  bool forced = !strcmp(reason, "button") || !strcmp(reason, "rachell") || !strcmp(reason, "phone");
  if (!S.cOn && strcmp(reason, "phone")) return;
  if (!forced && !S.manual) {
    if (!villageOpen()) return;
    if (everCaroled && millis() - lastCarolAt < (unsigned long)S.cRest * 60000UL) return;
  }
  int lo = min(S.cFirst, S.cLast), hi = max(S.cFirst, S.cLast);
  int song = lo + (int)random(hi - lo + 1);
  logln(String("Carolers sing (") + reason + "), song " + song);
  play2(song);
  trainQuiet(S.cSecs);
  lastCarolAt = millis(); everCaroled = true;
  if (S.cPreset > 0 && mode != MODE_TREE_SHOW && mode != MODE_RACHELL) {
    setLightsPreset(S.cPreset, 15);
    carolLightsOn = true;
    carolLightsUntil = millis() + S.cSecs * 1000UL;
  }
}

// ======================== STREET LAMPS ======================
bool lampsForced = false, lampsForcedOn = false;
void updateLamps() {
  bool on;
  if (lampsForced) on = lampsForcedOn;
  else if (S.manual) on = false;
  else if (mode == MODE_CLOSED) on = false;
  else if (mode == MODE_SLEEPY) on = S.lampsSleepy;
  else on = S.lampsAwake;
  digitalWrite(PIN_LAMPS, on ? HIGH : LOW);
}

void updateCarolers() {
  if (carolLightsOn && (long)(millis() - carolLightsUntil) >= 0) {
    carolLightsOn = false;
    if (mode != MODE_TREE_SHOW && mode != MODE_RACHELL) setLightsPreset(presetForMode(mode), 30);
  }
  if (!S.manual && S.cOn && S.cEvery > 0 && villageOpen() && mode != MODE_CLOSED) {
    if (!everCaroled || millis() - lastCarolAt > (unsigned long)S.cEvery * 60000UL) {
      if (millis() > 90000) carolersSing("timer");
    }
  }
}

// ======================== MODES =============================
void enterMode(Mode m) {
  mode = m;
  carolLightsOn = false;
  logln(String("Mode: ") + modeName(m));
  switch (m) {
    case MODE_CLOSED: setLightsPreset(S.psOff, 50); rinkOff(); trainQuiet(0); break;
    case MODE_SLEEPY: setLightsPreset(S.psSleepy, 80); rinkOff(); trainQuiet(0); break;
    case MODE_AWAKE:
      setLightsPreset(S.psEvening, 40);
      play(S.sndWake);
      rinkOn(); sleighFly(); mistChimney(MIST_PUFF_SECONDS);
      trainGo(S.wakeLaps);
      if (S.cWithWake) carolersSing("wake");
      nextSleighAt = millis() + random(120, 200) * 1000UL;
      nextMistAt   = millis() + random(60, 120) * 1000UL;
      nextWindowAt = millis() + random(40, 90) * 1000UL;
      nextAmbAt = millis() + random(min(S.ambMinMin, S.ambMaxMin), max(S.ambMinMin, S.ambMaxMin) + 1) * 60000UL;
      break;
    case MODE_TREE_SHOW:
      setLightsPreset(S.psTree, 10);
      play(S.sndTree);
      trainQuiet(S.treeSecs);
      showEndsAt = millis() + S.treeSecs * 1000UL;
      break;
    case MODE_RACHELL:
      setLightsPreset(S.psRachell, 10);
      play(S.sndRachell);
      trainQuiet(S.rachellSecs);
      rinkOn(); sleighFly(); mistChimney(MIST_PUFF_SECONDS);
      trainGo(1);
      if (S.cWithRach) carolersSing("rachell");
      showEndsAt = millis() + S.rachellSecs * 1000UL;
      break;
  }
}

void startShow(Mode show) {
  if (mode != MODE_TREE_SHOW && mode != MODE_RACHELL) modeAfterShow = mode;
  enterMode(show);
}

void wake() {
  lastMotionAt = millis();
  if (mode == MODE_SLEEPY) enterMode(MODE_AWAKE);
}

void updateMode() {
  unsigned long now = millis();
  bool open = villageOpen();
  if (mode == MODE_TREE_SHOW || mode == MODE_RACHELL) {
    if ((long)(now - showEndsAt) >= 0) {
      Mode back = modeAfterShow;
      if (S.manual) { logln("Show finished"); enterMode(back == MODE_CLOSED ? MODE_CLOSED : MODE_SLEEPY); return; }
      if (!open) back = MODE_CLOSED;
      else if (back == MODE_CLOSED) back = MODE_SLEEPY;
      if (back == MODE_AWAKE) { lastMotionAt = now; setLightsPreset(S.psEvening, 30); mode = MODE_AWAKE; logln("Mode: awake"); }
      else enterMode(back);
    }
    return;
  }
  if (S.manual) return;     // MANUAL MODE: no clock, no time-outs, no random effects
  if (!open && mode != MODE_CLOSED) { enterMode(MODE_CLOSED); return; }
  if (open && mode == MODE_CLOSED) { enterMode(MODE_SLEEPY); return; }
  if (mode == MODE_AWAKE) {
    if (now - lastMotionAt > (unsigned long)S.awakeMin * 60000UL) { enterMode(MODE_SLEEPY); return; }
    if ((long)(now - nextSleighAt) >= 0) { play(S.sndWake); sleighFly(); nextSleighAt = now + random(150, 260) * 1000UL; }
    if ((long)(now - nextMistAt) >= 0)   { mistChimney(MIST_PUFF_SECONDS); nextMistAt = now + random(70, 140) * 1000UL; }
    if ((long)(now - nextWindowAt) >= 0) { if (random(3) == 0) play(S.sndHoho); nextWindowAt = now + random(50, 110) * 1000UL; }
    // random extras: only when nothing has played on the main speaker for 20 s, so they never cut a sound off
    if (S.ambOn && (long)(now - nextAmbAt) >= 0) {
      if (now - lastMainPlayAt > 20000UL) {
        int lo = min(S.ambFirst, S.ambLast), hi = max(S.ambFirst, S.ambLast);
        play(random(lo, hi + 1));
      }
      int lo = min(S.ambMinMin, S.ambMaxMin), hi = max(S.ambMinMin, S.ambMaxMin);
      nextAmbAt = now + random(lo, hi + 1) * 60000UL;
    }
  }
}

// ======================== INPUTS ============================
bool buttonPressed(Button& b) {
  bool r = digitalRead(b.pin);
  if (r != b.lastRead) { b.lastRead = r; b.changedAt = millis(); }
  if (millis() - b.changedAt > 40 && r != b.lastStable) {
    b.lastStable = r;
    if (r == LOW) { logln(String("Button: ") + b.name); return true; }
  }
  return false;
}

void readInputs() {
  if (buttonPressed(btnTree))  startShow(MODE_TREE_SHOW);
  if (buttonPressed(btnTrain)) trainAfterWhistle(S.buttonLaps);
  if (buttonPressed(btnRach))  startShow(MODE_RACHELL);
  if (buttonPressed(btnSpot) && S.cButton) carolersSing("button");

  bool settled = millis() > 60000;   // PIRs need ~60 s after power-up
  bool p1 = steadyRead(pirS[0], S.pir1On, PIN_PIR1), p2 = steadyRead(pirS[1], S.pir2On, PIN_PIR2), p3 = steadyRead(pirS[2], S.pir3On, PIN_PIR3);
  if (p1 != pir1Last) logln(p1 ? "Motion 1: ON  (someone moving)" : "Motion 1: off");
  if (p2 != pir2Last) logln(p2 ? "Motion 2: ON  (someone moving)" : "Motion 2: off");
  if (!p3 && pir3Last) logln("Motion 3: off");
  if (p3 && !pir3Last) {
    logln("Motion 3 (carolers): ON");
    if (settled && S.cMotion && !S.manual) carolersSing("motion");
  }
  pir1Last = p1; pir2Last = p2; pir3Last = p3;
  if ((p1 || p2 || p3) && settled && !S.manual) wake();   // in manual mode motion is only reported
}

// ======================= WEB PAGES ==========================
// The phone page lives in VillagePage.h (its own tab).


String statusText() {
  String ver = String("\nCode version: ") + FIRMWARE_VERSION;
  struct tm t; char clock[32] = "clock not set yet";
  if (getLocalTime(&t, 0)) strftime(clock, sizeof(clock), "%a %I:%M %p", &t);
  String s = String(S.manual ? "MANUAL MODE: nothing happens unless you tap it\n" : "AUTOMATIC: runs on its own\n");
  s += String("Mode: ") + modeName(mode) + (manualOverride ? " (ignoring clock)" : "") + "\n";
  s += String("Time: ") + clock + "  |  open " + S.openHour + ":00 to " + S.closeHour + ":00\n";
  s += String("Motion: ") + (pir1Last ? "1 " : "") + (pir2Last ? "2 " : "") + (pir3Last ? "3(carolers)" : "") + "\n";
  s += String("Sleigh: ") + (sleighState == SL_HOME ? "home" : "flying") + (sleighAtHome() ? " (magnet seen)" : "") + "\n";
  s += String("Rink speed: ") + rink.current + "/255   Street lamps: " + (digitalRead(PIN_LAMPS) ? "on" : "off") + "\n";
  s += String("Main sound: ") + (soundOK ? "ready" : "NOT FOUND") + "   Carolers sound: " + (sound2OK ? "ready" : "NOT FOUND") + "\n";
  s += String("Lights: ") + (lightsIP == IPAddress(0,0,0,0) ? "not found yet" : lightsIP.toString()) + "   Train: " + (trainIP == IPAddress(0,0,0,0) ? "not found yet" : trainIP.toString());
  return s + ver;
}

void sendSettingsPage(const String& msg) {
  String h = F("<!doctype html><html><head><meta name=viewport content=\"width=device-width,initial-scale=1\"><title>Village Settings</title>"
    "<style>body{font-family:sans-serif;margin:14px;background:#1b1410;color:#f6ead8}h1{font-size:22px}h2{font-size:17px;color:#f2c46d;margin:18px 0 6px}"
    "label{display:flex;justify-content:space-between;align-items:center;gap:10px;padding:7px 0;border-bottom:1px solid #3a2b22;font-size:15px}"
    "input[type=number]{width:80px;font-size:17px;padding:6px;border-radius:6px;border:0}input[type=checkbox]{width:26px;height:26px}"
    "button,a{display:block;text-align:center;text-decoration:none;font-size:18px;padding:13px;margin:14px 0;border:0;border-radius:10px;background:#1f5a32;color:#fff}"
    ".m{background:#2a3d2a;padding:8px;border-radius:8px}.h{font-size:13px;color:#cdb}</style></head><body><h1>Village Settings</h1>");
  if (msg.length()) h += "<p class=m>" + msg + "</p>";
  h += F("<p class=h>Change anything, then press Save at the bottom. Sound numbers match the file names on each SD card (0004.mp3 = 4).</p><form method=post action=/save>");
  const char* group = "";
  for (int i = 0; i < NFIELDS; i++) {
    Field& f = FIELDS[i];
    if (strcmp(group, f.group)) { group = f.group; h += String("<h2>") + group + "</h2>"; }
    h += String("<label>") + f.label;
    if (f.check) h += String("<input type=checkbox name=") + f.key + (*f.val ? " checked" : "") + ">";
    else h += String("<input type=number name=") + f.key + " min=" + f.lo + " max=" + f.hi + " value=" + *f.val + ">";
    h += "</label>";
  }
  h += F("<button type=submit>Save</button></form><a href=\"/cmd?do=carol&back=1\" style=\"background:#7a1414\">Test: carolers sing now</a><a href=\"/\">Back to controls</a></body></html>");
  server.send(200, "text/html", h);
}

void handleSave() {
  for (int i = 0; i < NFIELDS; i++) {
    Field& f = FIELDS[i];
    if (f.check) { *f.val = server.hasArg(f.key) ? 1 : 0; continue; }
    if (server.hasArg(f.key)) *f.val = constrain(server.arg(f.key).toInt(), f.lo, f.hi);
  }
  saveSettings();
  if (soundOK) dfplayer.volume(S.volume);
  if (sound2OK) dfplayer2.volume(S.cVolume);
  if (rink.target > 0) rink.target = S.rinkSpeed;
  logln("Settings saved");
  sendSettingsPage("Saved. Changes take effect now.");
}

void doCommand(const String& c) {
  if (c.startsWith("play:")) play(c.substring(5).toInt());          // test one main-speaker file, e.g. play:7
  else if (c.startsWith("light:")) setLightsPreset(c.substring(6).toInt(), 10);   // test one WLED preset, e.g. light:4
  else if (c == "wake") { lastMotionAt = millis(); if (mode != MODE_AWAKE) enterMode(MODE_AWAKE); }
  else if (c == "sleep") enterMode(villageOpen() ? MODE_SLEEPY : MODE_CLOSED);
  else if (c == "tree") startShow(MODE_TREE_SHOW);
  else if (c == "rachell") startShow(MODE_RACHELL);
  else if (c == "carol") carolersSing("phone");
  else if (c == "train") trainAfterWhistle(S.buttonLaps);
  else if (c == "sleigh") sleighFly();
  else if (c == "rinkon") rinkOn();
  else if (c == "rinkoff") rinkOff();
  else if (c == "mist1") mistChimney(MIST_PUFF_SECONDS);
  else if (c == "mist2") mistStation(STATION_MIST_SECONDS);
  else if (c == "lampson") { lampsForced = true; lampsForcedOn = true; }
  else if (c == "lampsoff") { lampsForced = true; lampsForcedOn = false; }
  else if (c == "lampsauto") lampsForced = false;
  else if (c == "manual") {
    S.manual = !S.manual; saveSettings();
    logln(S.manual ? "MANUAL MODE on: nothing happens on its own" : "AUTOMATIC mode on");
    if (!S.manual) { lampsForced = false; enterMode(villageOpen() ? MODE_SLEEPY : MODE_CLOSED); }
  }
  else if (c == "override") { manualOverride = !manualOverride; logln(String("Ignore clock: ") + (manualOverride ? "on" : "off")); }
  else if (c.startsWith("snd2_")) play2(c.substring(5).toInt());
  else if (c.startsWith("snd")) play(c.substring(3).toInt());
  else if (c == "station") {
    if (mode != MODE_TREE_SHOW && mode != MODE_RACHELL) play(S.sndStation);   // don't cut off a show's song
    mistStation(STATION_MIST_SECONDS);
  }
}

void setupWeb() {
  server.on("/", []() { server.send_P(200, "text/html", PAGE); });
  server.on("/status", []() { server.send(200, "text/plain", statusText()); });
  server.on("/log", []() { server.send(200, "text/plain", logText()); });
  server.on("/logclear", []() { logHead = 0; logCount = 0; logSeq++; server.send(200, "text/plain", "ok"); });
  server.on("/settings", []() { sendSettingsPage(""); });
  server.on("/save", HTTP_POST, handleSave);
  server.on("/cmd", []() {
    doCommand(server.arg("do"));
    if (server.hasArg("back")) { server.sendHeader("Location", "/settings"); server.send(303); }
    else server.send(200, "text/plain", "ok");
  });
  server.on("/train", []() {          // hub: answers instantly; the loop talks to Board B in the background
    String d = server.arg("do");
    if (d == "status") { lastTrainView = millis(); server.send(200, "text/plain", trainStatusCache); return; }
    String path = "";
    if (d == "stop" || d == "xing" || d == "relaytest" || d == "bttest" || d.startsWith("go?laps=")) path = "/" + d;
    if (path == "") { server.send(400, "text/plain", "unknown"); return; }
    logln(String("Train <- ") + d + " (from phone)");
    pendingTrainCmd = path;
    server.send(200, "text/plain", "ok");
  });
  server.on("/links", []() {          // the hub page uses these so its links work even when ".local" names don't
    String l = lightsIP == IPAddress(0, 0, 0, 0) ? String("village-lights.local") : lightsIP.toString();
    String t = trainIP == IPAddress(0, 0, 0, 0) ? String("village-train.local") : trainIP.toString();
    server.send(200, "text/plain", l + "\n" + t);
  });
  server.on("/station", []() { doCommand("station"); server.send(200, "text/plain", "ok"); });  // from Board B
  server.begin();
}

// ===================== SERIAL TEST MENU =====================
void printHelp() {
  logln("\n--- Village Effects test menu (type a letter, press Enter) ---");
  logln(" 1-6  main speaker sound 1-6     c  carolers sing (speaker 2)");
  logln(" w    wake village   z  sleep    t  tree show   r  Rachell show");
  logln(" g    send train     f  fly sleigh   k  rink on   x  rink off");
  logln(" m    chimney mist   n  station mist");
  logln(" l    street lamps on/off test   a  lamps back to automatic");
  logln(" M    manual mode on/off (capital M)");
  logln(" o    ignore clock on/off        s  status      h  this menu");
}

void readSerial() {
  if (!Serial.available()) return;
  char ch = Serial.read();
  switch (ch) {
    case '1': case '2': case '3': case '4': case '5': case '6': play(ch - '0'); break;
    case 'c': doCommand("carol"); break;
    case 'l': doCommand(lampsForced && lampsForcedOn ? "lampsoff" : "lampson"); break;
    case 'a': doCommand("lampsauto"); break;
    case 'w': doCommand("wake"); break;      case 'z': doCommand("sleep"); break;
    case 't': doCommand("tree"); break;      case 'r': doCommand("rachell"); break;
    case 'g': doCommand("train"); break;     case 'f': doCommand("sleigh"); break;
    case 'k': doCommand("rinkon"); break;    case 'x': doCommand("rinkoff"); break;
    case 'm': doCommand("mist1"); break;     case 'n': doCommand("mist2"); break;
    case 'o': doCommand("override"); break;
    case 'M': doCommand("manual"); break;
    case 's': logln(statusText()); break;    case 'h': printHelp(); break;
    default: break;
  }
}

// ========================= SETUP ============================
// ---- finding the other board: each board says "I'm here" on the network every 5 s ----
WiFiUDP disc;
const int DISC_PORT = 4210;
unsigned long nextAnnounce = 0;
void setupDiscovery() { if (WiFi.status() == WL_CONNECTED) disc.begin(DISC_PORT); }
// ask the train to play quietly for `secs` seconds (0 = back to normal) so a song can be heard over it
void trainQuiet(int secs) {
  if (WiFi.status() != WL_CONNECTED || trainIP == IPAddress(0, 0, 0, 0)) return;
  disc.beginPacket(trainIP, DISC_PORT);
  disc.print(String("TDUCK:") + secs);
  disc.endPacket();
}

void updateDiscovery() {
  if (WiFi.status() != WL_CONNECTED) return;
  if ((long)(millis() - nextAnnounce) >= 0) {
    nextAnnounce = millis() + 5000;
    disc.beginPacket(IPAddress(255, 255, 255, 255), DISC_PORT);
    disc.print(MY_NAME);
    disc.endPacket();
  }
  for (int k = 0; k < 8; k++) {                // handle everything that arrived since last time
    int n = disc.parsePacket();
    if (n <= 0) return;
    char buf[200]; int len = disc.read(buf, 199); if (len < 0) len = 0; buf[len] = 0;
    if (!strncmp(buf, "TLOG:", 5)) {            // a log line from the train board
      logln(String("[train] ") + (buf + 5));
    } else if (!strcmp(buf, "TSTATION")) {      // the train just stopped at the station
      static unsigned long lastStation = 0;
      if (millis() - lastStation > 3000) { lastStation = millis(); doCommand("station"); }
    } else if (!strcmp(buf, TRAIN_NAME)) {
      IPAddress from = disc.remoteIP();
      static IPAddress announced;                 // only log when the address is new, not every 5 s
      trainIP = from;
      if (from != announced) { announced = from; logln(String("Found ") + TRAIN_NAME + " at " + from.toString()); }
      trainRetryAt = 0;
    }
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
  Serial.begin(115200);
  delay(300);
  logln("\n\nNorth Pole Village - Board A (effects) starting");
  loadSettings();

  pinMode(PIN_PIR1, INPUT); pinMode(PIN_PIR2, INPUT); pinMode(PIN_PIR3, INPUT_PULLDOWN);
  pinMode(PIN_BTN_TREE, INPUT_PULLUP); pinMode(PIN_BTN_TRAIN, INPUT_PULLUP);
  pinMode(PIN_BTN_RACH, INPUT_PULLUP); pinMode(PIN_BTN_SPOT, INPUT_PULLUP);
  pinMode(PIN_HALL, INPUT_PULLUP);
  pinMode(PIN_MIST1, OUTPUT); pinMode(PIN_MIST2, OUTPUT);
  mistWrite(PIN_MIST1, false); mistWrite(PIN_MIST2, false);

  // Motors on PWM channels 0 and 1 (one shared timer).
  ledcAttachChannel(PIN_RINK,   MOTOR_PWM_FREQ, MOTOR_PWM_BITS, 0); ledcWrite(PIN_RINK, 0);
  ledcAttachChannel(PIN_SLEIGH, MOTOR_PWM_FREQ, MOTOR_PWM_BITS, 1); ledcWrite(PIN_SLEIGH, 0);
  pinMode(PIN_LAMPS, OUTPUT); digitalWrite(PIN_LAMPS, LOW);

  Serial2.begin(9600, SERIAL_8N1, PIN_DF_RX, PIN_DF_TX);
  Serial1.begin(9600, SERIAL_8N1, PIN_DF2_RX, PIN_DF2_TX);
  delay(800);
  soundOK = dfplayer.begin(Serial2, true, true);
  if (soundOK) { dfplayer.volume(S.volume); logln("Main sound: ready"); }
  else logln("Main sound: NOT found (check RX/TX, 1k resistor, SD card)");
  sound2OK = dfplayer2.begin(Serial1, true, true);
  if (sound2OK) { dfplayer2.volume(S.cVolume); logln("Carolers sound: ready"); }
  else logln("Carolers sound: NOT found (fine if not wired yet)");

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
    configTzTime(TIMEZONE, "pool.ntp.org", "time.nist.gov");
  } else logln("\nWiFi: NOT connected (check name/password; it keeps trying)");
  setupOTA();
  setupDiscovery();
  setupWeb();
  logln(String("Firmware version ") + FIRMWARE_VERSION);
  randomSeed(esp_random());
  printHelp();
  logln("Tip: motion sensors are ignored for the first 60 seconds.");
  if (S.manual) logln("MANUAL MODE is on: nothing happens on its own. Turn it off on the phone page when you're done testing.");
}

// ========================== LOOP ============================
unsigned long lastWifiCheck = 0;
void loop() {
  ArduinoOTA.handle();
  updateDiscovery();
  if (pendingTrainLaps > 0 && (long)(millis() - pendingTrainAt) >= 0) { int l = pendingTrainLaps; pendingTrainLaps = 0; trainGo(l); }
  server.handleClient();
  readSerial();
  readInputs();
  updateMode();
  updateCarolers();
  updateLamps();
  updateTrainHub();
  updateMotor(rink);
  updateMotor(sleigh);
  updateSleigh();
  updateMist();
  if (millis() - lastWifiCheck > 30000) {
    lastWifiCheck = millis();
    if (WiFi.status() != WL_CONNECTED) { logln("WiFi: reconnecting"); WiFi.reconnect(); }
  }
}
