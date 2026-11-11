// Talks to the Lionel LionChief engine over Bluetooth (BLE), the same way the Cab3 app does.
// Kept in its own tab so the Arduino IDE handles it cleanly.
// Protocol (community reverse-engineered, github.com/Property404/lionchief-controller):
//   service e20a39f4-73f5-4bc4-a12f-17d1ad07a961, characteristic 08590f7e-db05-467e-8757-72f6faeb13d4
//   every command = 0x00, <command bytes>, checksum
#pragma once
#include <Arduino.h>
#include <BLEDevice.h>
#include <WiFi.h>

void logln(const String& s);   // lives in VillageTrain.ino

namespace lc {
  static BLEUUID SVC("e20a39f4-73f5-4bc4-a12f-17d1ad07a961");
  static BLEUUID CHR("08590f7e-db05-467e-8757-72f6faeb13d4");
  static BLEClient* client = nullptr;
  static BLERemoteCharacteristic* chr = nullptr;
  static BLEAdvertisedDevice* dev = nullptr;
  static bool inited = false;
  static String engineName = "";

  inline void init() {
    if (inited) return;
    WiFi.setSleep(true);     // required: WiFi and Bluetooth share the radio and must take turns
    BLEDevice::init("village-train");
    inited = true;
  }

  inline bool connected() {
    if (client && !client->isConnected()) chr = nullptr;
    return client && chr && client->isConnected();
  }

  // Look for a LionChief engine (names start with "LC"). Takes `secs` seconds.
  inline bool scan(uint32_t secs) {
    init();
    if (dev) { delete dev; dev = nullptr; }
    BLEScan* sc = BLEDevice::getScan();
    sc->setActiveScan(true);
    sc->setInterval(100);
    sc->setWindow(99);
    BLEScanResults* res = sc->start(secs, false);
    int best = -999;
    if (res) {
      for (int i = 0; i < res->getCount(); i++) {
        BLEAdvertisedDevice d = res->getDevice(i);
        String n = d.haveName() ? String(d.getName().c_str()) : String("");
        bool match = n.startsWith("LC") || (d.haveServiceUUID() && d.isAdvertisingService(SVC));
        if (match && d.getRSSI() > best) {
          best = d.getRSSI();
          if (dev) delete dev;
          dev = new BLEAdvertisedDevice(d);
          engineName = n.length() ? n : String(d.getAddress().toString().c_str());
        }
      }
    }
    sc->clearResults();
    return dev != nullptr;
  }

  // Find and connect. Blocks for a few seconds (only used while the train is standing still).
  inline bool connect() {
    if (connected()) return true;
    if (!scan(4)) { logln("Bluetooth: no engine found (on the track, powered, switch on BT?)"); return false; }
    if (!client) client = BLEDevice::createClient();
    logln(String("Bluetooth: found ") + engineName + ", connecting...");
    if (!client->connect(dev)) { logln("Bluetooth: couldn't connect"); return false; }
    BLERemoteService* s = client->getService(SVC);
    if (!s) { logln("Bluetooth: engine has no train service"); client->disconnect(); return false; }
    chr = s->getCharacteristic(CHR);
    if (!chr) { logln("Bluetooth: engine has no command channel"); client->disconnect(); return false; }
    logln(String("Bluetooth: connected to ") + engineName);
    return true;
  }

  inline void send(const uint8_t* cmd, size_t n) {
    if (!connected()) return;
    uint8_t buf[12];
    buf[0] = 0x00;
    int sum = 0;
    for (size_t i = 0; i < n && i < 10; i++) { buf[i + 1] = cmd[i]; sum += cmd[i]; }
    buf[n + 1] = (uint8_t)((256 - (sum & 0xFF)) & 0xFF);   // checksum (the engine doesn't seem to check it)
    chr->writeValue(buf, n + 2, !chr->canWriteNoResponse());
  }

  inline void speed(int v)   { v = constrain(v, 0, 31); uint8_t c[] = {0x45, (uint8_t)v}; send(c, 2); }
  inline void forward()      { uint8_t c[] = {0x46, 0x01}; send(c, 2); }
  inline void horn(bool on)  { uint8_t c[] = {0x48, (uint8_t)(on ? 1 : 0)}; send(c, 2); }
  inline void bell(bool on)  { uint8_t c[] = {0x47, (uint8_t)(on ? 1 : 0)}; send(c, 2); }
  // NOTE: 0x4b is DISCONNECT (not volume). Main volume is 0x4c; the engine/chuff sound is 0x44 type 4.
  inline void volume(int v)  { v = constrain(v, 0, 7); uint8_t c[] = {0x4c, (uint8_t)v}; send(c, 2); }   // main volume 0-7
  inline void chuff(int v)   { v = constrain(v, 0, 7) * 2; uint8_t c[] = {0x44, 0x04, (uint8_t)v, 0x00}; send(c, 4); }  // engine sound 0-14, normal pitch
  inline void announce()     { uint8_t c[] = {0x4d, 0x00, 0x00}; send(c, 3); }   // random announcement

  inline void drop() {          // forget the connection (used when track power goes off)
    if (client && client->isConnected()) client->disconnect();
    chr = nullptr;
  }
}
