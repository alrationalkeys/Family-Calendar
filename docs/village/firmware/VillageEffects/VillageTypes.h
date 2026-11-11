// Type definitions for VillageEffects.
// They live in this separate tab so the Arduino IDE sees them before it
// generates its automatic function declarations. Keep this file next to
// VillageEffects.ino (it opens as a second tab in the IDE).
#pragma once
#include <Arduino.h>

struct Settings {
  // village
  int manual = 1;         // 1 = MANUAL MODE: nothing happens on its own, only when you tell it to
  int openHour = 16, closeHour = 23, awakeMin = 8;
  int volume = 20;
  int rinkSpeed = 170, sleighSpeed = 230;
  int wakeLaps = 2, buttonLaps = 2;
  int treeSecs = 60, rachellSecs = 90;
  // which sound file plays for each event (mp3 folder number)
  int sndWake = 1, sndWhistle = 2, sndHoho = 3, sndTree = 4, sndRachell = 5, sndStation = 6;
  int whistleSecs = 4;     // train waits this long after the whistle starts (set to the whistle clip length; 0 = no wait)
  // random extras while awake (reindeer, Santa landing, sleigh bells...)
  int ambOn = 1;          // 1 = on
  int ambFirst = 7, ambLast = 10;   // file numbers on the main SD card (random pick)
  int ambMinMin = 10, ambMaxMin = 20;   // minutes between extras (random)
  // WLED preset numbers
  int psOff = 1, psSleepy = 2, psEvening = 3, psTree = 4, psRachell = 5;
  // sound spot 2 (carolers)
  int cOn = 1;            // spot turned on
  int cMotion = 1;        // sing when someone walks up to them
  int cButton = 1;        // sing when their button is pressed
  int cEvery = 0;         // also sing every N minutes during open hours (0 = never)
  int cWithWake = 0;      // sing when the whole village wakes up
  int cWithRach = 1;      // sing during Rachell's show
  int cFirst = 1, cLast = 1;   // songs on SD card 2: picks one at random from first..last
  int cVolume = 22;
  int cPreset = 0;        // WLED preset while they sing (0 = leave the lights alone)
  int cSecs = 60;         // how long that light preset stays on
  int cRest = 3;          // minutes before motion can start them again
  int pir1On = 1, pir2On = 0, pir3On = 0;   // which motion sensors are actually plugged in
  int lampsSleepy = 1;    // street lamps on while sleepy
  int lampsAwake = 1;     // street lamps on while awake and during shows
};

struct Field { const char* key; const char* label; int* val; int lo; int hi; bool check; const char* group; };
enum Mode { MODE_CLOSED, MODE_SLEEPY, MODE_AWAKE, MODE_TREE_SHOW, MODE_RACHELL };
struct Motor { int pin; int current; int target; unsigned long lastStep; };
enum SleighState { SL_HOME, SL_LEAVING, SL_FLYING };
struct Button { int pin; bool lastStable; bool lastRead; unsigned long changedAt; const char* name; };

struct Steady { bool raw; bool stable; unsigned long since; };   // motion sensor steady filter
