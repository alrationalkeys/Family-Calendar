/*
  BlindTilt.ino - FamilyHub DIY blind tilt motor
  ==============================================
  Board   : ESP32-C6 "SuperMini", Arduino IDE, arduino-esp32 core 3.x
  Radio   : Zigbee End Device (joins Home Assistant ZHA). No Wi-Fi, no passwords in this file.
  Motor   : N20 gearmotor with a 2-channel hall encoder, DRV8833 driver
  Job     : turn the tilt wand of a horizontal blind. Shows up in Home Assistant as a cover with tilt.

  Read ../README.md first: wiring, Arduino IDE settings, pairing, bench test, calibration, LED blinks.

  How it knows where the slats are
  --------------------------------
  There are no limit switches. The encoder on the motor counts how far the wand has turned.
  "Home" (position 0) is found by turning gently toward one closed stop until the encoder stops
  counting. That is called a stall. From there every position is a number of encoder counts.

  IMPORTANT: the encoder stall is the ONLY load sensing this hardware has. The DRV8833 has no
  current-sense output wired to the ESP32, so the firmware cannot measure motor current. Everything
  that protects the blind (gentle homing speed, stop within about 150 ms of no movement, a time
  limit on every move) depends on the encoder working. If the encoder is unplugged the motor only
  runs for the start-up grace time (START_GRACE_MS) and then stops with a fault.

  Zigbee library calls used here were checked against the arduino-esp32 source, tag 3.3.13:
    libraries/Zigbee/src/ep/ZigbeeWindowCovering.h / .cpp   (ZigbeeWindowCovering: onOpen, onClose,
        onStop, onGoToTiltPercentage, setTiltPercentage, setCoveringType, setConfigStatus, setMode,
        setLimits, enum value BLIND_TILT_ONLY)
    libraries/Zigbee/src/ZigbeeEP.h / .cpp                   (setManufacturerAndModel, setPowerSource,
        setBatteryPercentage, setBatteryVoltage, reportBatteryPercentage, onIdentify)
    libraries/Zigbee/src/ZigbeeCore.h / .cpp                 (Zigbee.addEndpoint, begin, connected,
        factoryReset, setRxOnWhenIdle, ZIGBEE_DEFAULT_ED_CONFIG)
    libraries/Zigbee/examples/Zigbee_Window_Covering and Zigbee_Temp_Hum_Sensor_Sleepy
  Home Assistant side checked against zigpy/zha, zha/application/platforms/cover/__init__.py.

  Two things in that library you need to know about:
   1. It has no hook for the Zigbee "calibration mode" bit, so re-homing is on the BOOT button
      (hold about 2 s, see the README) instead of a Zigbee command.
   2. It silently ignores a "go to tilt" command when the number is the same as the tilt it
      already has. So this sketch always reports the real position after a move.
*/

#ifndef ZIGBEE_MODE_ED
#error "In the Arduino IDE set Tools > Zigbee mode > Zigbee ED (end device). See the README."
#endif

#include "Zigbee.h"
#include "esp_sleep.h"

// =====================================================================================
//  CONFIG - everything you may need to change is in this one section
// =====================================================================================

// ---- Power mode ---------------------------------------------------------------------
// 1 = stay awake all the time. Use this on USB power for bench testing. Commands arrive at once,
//     and the serial console works. Do NOT run from the battery like this: it would be flat in
//     a day or two.
// 0 = battery mode: deep sleep, wake every SLEEP_SECONDS, listen briefly, sleep again.
//     Read "Battery mode" in the README before switching. Commands can be slow or missed.
#define STAY_AWAKE 1

// 0 = no battery connected (USB bench test): do not check the battery voltage before moving.
// 1 = battery + divider are wired: refuse to move when the cell is below BATT_CUTOFF_MV.
#define BATTERY_FITTED 0

// ---- Pins (GPIO numbers printed on the ESP32-C6 SuperMini) --------------------------
// Avoid 8, 9 and 15 for anything else (LED / BOOT button / boot strapping), and 12, 13 (USB).
const uint8_t PIN_MOTOR_IN1   = 18;   // DRV8833 IN1 (PWM)
const uint8_t PIN_MOTOR_IN2   = 19;   // DRV8833 IN2 (PWM)
const uint8_t PIN_MOTOR_SLEEP = 20;   // DRV8833 nSLEEP ("SLP" / "EEP"). HIGH = driver on, LOW = asleep
const uint8_t PIN_ENC_A       = 1;    // encoder channel A
const uint8_t PIN_ENC_B       = 2;    // encoder channel B
const int8_t  PIN_ENC_POWER   = 3;    // encoder VCC is fed from this pin so it is off between moves.
                                      // Set to -1 if you wired encoder VCC straight to 3V3.
const uint8_t PIN_BATTERY     = 0;    // battery divider midpoint (must be an ADC pin: GPIO 0-6)
const uint8_t PIN_LED         = 15;   // on-board plain LED
const uint8_t LED_ON_LEVEL    = HIGH; // change to LOW if your LED lights when the pin is LOW
const uint8_t PIN_BUTTON      = 9;    // on-board BOOT button (pressed = LOW)

// ---- Mechanics: MEASURE AND ADJUST THESE --------------------------------------------
// These three numbers decide how many encoder counts make one full turn of the WAND.
// They are starting guesses. N20 encoders are usually 7 pulses per motor turn (some are 3 or 12),
// a "1:298" gearbox is really about 297.9, and the printed gears add their own ratio.
// Do the "Calibrate counts per turn" steps in the README and correct them.
const float ENCODER_PULSES_PER_MOTOR_TURN = 7.0f;    // pulses on ONE channel per motor shaft turn (CPR)
const float QUADRATURE_FACTOR             = 4.0f;    // both edges of both channels are counted
const float GEARBOX_RATIO                 = 298.0f;  // motor turns per gearbox output turn
const float DRIVE_RATIO                   = 1.0f;    // wand-gear teeth / motor-pinion teeth (1.0 = direct)
const float COUNTS_PER_WAND_TURN =
  ENCODER_PULSES_PER_MOTOR_TURN * QUADRATURE_FACTOR * GEARBOX_RATIO * DRIVE_RATIO;   // 8344 with the guesses

const float WAND_TURNS_FULL_TRAVEL = 5.0f;   // wand turns from closed one way to closed the other way

// How much of that travel the 0-100 % tilt slider covers, counted from the home stop.
//   5.0 (= full travel): 0 % closed at the home stop, 50 % slats level, 100 % closed the other way.
//   2.5 (= half travel): 0 % closed at the home stop, 100 % slats level. The other half is not used.
// See "What the tilt numbers mean" in the README before changing it.
const float TILT_SCALE_TURNS = 5.0f;

const bool MOTOR_REVERSED   = false;  // true = homing turns toward the OTHER closed stop
const bool ENCODER_REVERSED = false;  // flip if you get the 5-blink fault (counting backwards)

// ---- Speeds (PWM duty, 0-255) -------------------------------------------------------
const uint32_t PWM_FREQ_HZ  = 20000;  // above hearing, so the motor does not whine
const uint8_t  PWM_BITS     = 8;
const uint8_t  PWM_START    = 70;     // soft start begins here
const uint8_t  PWM_RUN      = 255;    // normal travel speed
const uint8_t  PWM_APPROACH = 110;    // speed for the last bit before the target
const uint8_t  PWM_HOMING   = 130;    // gentle speed used whenever it is feeling for a stop
const uint16_t RAMP_UP_MS   = 300;    // soft start: time to go from PWM_START to full speed
const uint16_t RAMP_DOWN_MS = 150;    // soft stop when a move is interrupted
const float    SLOWDOWN_TURNS = 0.25f;  // start slowing this many wand turns before the target
const uint16_t BRAKE_MS     = 60;     // short electrical brake at the end of a normal move
const uint16_t CONTROL_TICK_MS = 5;   // how often the move loop checks the encoder

// ---- Stall detection (the only load sensing there is) -------------------------------
const uint16_t STALL_TIME_MS    = 150;  // no encoder movement for this long = stalled, power off
const uint16_t STALL_MIN_COUNTS = 6;    // fewer counts than this in STALL_TIME_MS = "not moving"
const uint16_t START_GRACE_MS   = 350;  // time allowed to get going at the start of a move
const uint16_t WRONG_WAY_COUNTS = 60;   // counting backwards this far = encoder wired the other way
const uint16_t MIN_MOVE_COUNTS  = 40;   // less than this during homing = the motor is not turning
const uint16_t SETTLE_MS        = 150;  // wait for the gear train to relax after power is cut

// ---- Time limits (every move has one) -----------------------------------------------
const uint32_t MOVE_TIME_BASE_MS     = 2000;   // fixed allowance per move ...
const uint32_t MOVE_TIME_PER_TURN_MS = 8000;   // ... plus this much per wand turn of distance
const uint32_t HOMING_TIME_LIMIT_MS  = 60000;  // hard limit for feeling for the home stop
const uint32_t BACKOFF_TIME_LIMIT_MS = 5000;   // hard limit for the small back-off before homing

// ---- Homing -------------------------------------------------------------------------
const float HOME_BACKOFF_TURNS    = 0.15f;  // first turn away from the stop by this much
const float HOME_APPROACH_TURNS   = 0.35f;  // when closing, switch to the gentle speed this early
const float HOME_OVERTRAVEL_TURNS = 0.5f;   // give up homing after full travel plus this much
const float END_TOLERANCE_TURNS   = 0.5f;   // a stall this close to the far stop counts as "arrived"
const bool  HOME_ON_FIRST_CONNECT = true;   // home by itself the first time it joins after power-up

// ---- Battery ------------------------------------------------------------------------
const float    BATT_R_TOP_OHMS    = 220000.0f;  // resistor from battery + to the ADC pin
const float    BATT_R_BOTTOM_OHMS = 220000.0f;  // resistor from the ADC pin to GND
const float    BATT_CALIBRATION   = 1.00f;      // multimeter volts / reported volts (trim, near 1.0)
const uint16_t BATT_FULL_MV       = 4150;       // shown as 100 %
const uint16_t BATT_EMPTY_MV      = 3300;       // shown as 0 %
const uint16_t BATT_CUTOFF_MV     = 3400;       // below this it refuses to move the motor
const uint32_t BATT_REPORT_INTERVAL_MS = 30UL * 60UL * 1000UL;  // stay-awake mode: report this often

// ---- Battery mode (only used when STAY_AWAKE is 0) -----------------------------------
const uint32_t SLEEP_SECONDS            = 20;      // deep sleep between listening windows
const uint32_t LISTEN_WINDOW_MS         = 3000;    // stay awake this long after re-connecting
const uint32_t JOIN_WAIT_MS             = 15000;   // give up waiting for the network after this
const uint32_t AFTER_ACTIVITY_AWAKE_MS  = 10000;   // stay awake this long after a command or button
const uint32_t COLD_BOOT_AWAKE_MS       = 180000;  // after power-up stay awake 3 min (pairing takes time)
const uint32_t NOT_JOINED_SLEEP_SECONDS = 300;     // not paired / network gone: sleep longer
const uint32_t LOW_BATT_SLEEP_SECONDS   = 900;     // battery below cutoff: sleep longer to recover
const uint32_t POLL_INTERVAL_MS         = 1000;    // how often it asks its Zigbee parent for messages
const uint16_t BATT_REPORT_EVERY_WAKES  = 90;      // send the battery level every N wake-ups

// ---- Button -------------------------------------------------------------------------
const uint16_t BUTTON_HOME_MS  = 1500;  // hold this long, release = re-home (calibrate)
const uint16_t BUTTON_RESET_MS = 5000;  // hold this long = factory reset / re-pair

// ---- Zigbee identity ----------------------------------------------------------------
const uint8_t ZIGBEE_ENDPOINT = 10;
const char   *ZIGBEE_MAKER    = "FamilyHub";
const char   *ZIGBEE_MODEL    = "BlindTilt";

// =====================================================================================
//  END OF CONFIG
// =====================================================================================

// Distances worked out from the config, in encoder counts
const long TRAVEL_COUNTS         = (long)(COUNTS_PER_WAND_TURN * WAND_TURNS_FULL_TRAVEL);
const long TILT_SCALE_COUNTS     = (long)(COUNTS_PER_WAND_TURN * TILT_SCALE_TURNS);
const long SLOWDOWN_COUNTS       = (long)(COUNTS_PER_WAND_TURN * SLOWDOWN_TURNS);
const long HOME_BACKOFF_COUNTS   = (long)(COUNTS_PER_WAND_TURN * HOME_BACKOFF_TURNS);
const long HOME_APPROACH_COUNTS  = (long)(COUNTS_PER_WAND_TURN * HOME_APPROACH_TURNS);
const long HOME_OVERTRAVEL_COUNTS = (long)(COUNTS_PER_WAND_TURN * HOME_OVERTRAVEL_TURNS);
const long END_TOLERANCE_COUNTS  = (long)(COUNTS_PER_WAND_TURN * END_TOLERANCE_TURNS);
const long POSITION_TOLERANCE_COUNTS = 20;   // closer to the target than this = already there

// "Slats level" (open) as a tilt percentage: 50 with full-travel scale, 100 with half-travel scale
const uint8_t OPEN_PERCENT = (uint8_t)constrain(50.0f * WAND_TURNS_FULL_TRAVEL / TILT_SCALE_TURNS + 0.5f, 0.0f, 100.0f);

// Why a single motor run ended
enum StopReason : uint8_t {
  STOP_DONE,         // reached the target
  STOP_STALL,        // encoder stopped moving (hit a stop, or something is blocking)
  STOP_TIMEOUT,      // took longer than the time limit
  STOP_INTERRUPTED,  // a new command, the button or the serial console cut in
  STOP_WRONG_WAY     // encoder counted the opposite way
};

// Faults. The number is also how many times the LED blinks.
enum Fault : uint8_t {
  FAULT_NONE        = 0,
  FAULT_LOW_BATTERY = 2,  // battery below BATT_CUTOFF_MV, move refused
  FAULT_HOMING      = 3,  // could not find the home stop
  FAULT_BLOCKED     = 4,  // stalled in the middle twice, or a move ran out of time
  FAULT_ENCODER     = 5   // motor not turning, or encoder counting backwards / not counting
};

enum LedMode : uint8_t { LED_OFF, LED_SEARCHING, LED_HEARTBEAT, LED_SOLID, LED_HOMING, LED_FLICKER, LED_FAULT };

enum CommandType : uint8_t { CMD_NONE, CMD_GOTO, CMD_STOP, CMD_HOME };

ZigbeeWindowCovering zbCovering = ZigbeeWindowCovering(ZIGBEE_ENDPOINT);

// ---- State --------------------------------------------------------------------------
volatile long    encCount = 0;        // position in encoder counts, 0 = home stop, + = away from it
volatile uint8_t encPrev = 0;
volatile bool    encActive = false;   // counting only while the encoder is powered
portMUX_TYPE     encMux = portMUX_INITIALIZER_UNLOCKED;

bool  homed = false;                  // true once the home stop has been found
bool  homeTriedThisBoot = false;
Fault fault = FAULT_NONE;

volatile LedMode  ledMode = LED_OFF;
volatile uint8_t  ledFaultBlinks = 0;
volatile uint32_t identifyUntilMs = 0;

// One-slot command mailbox. Zigbee callbacks run in the Zigbee task and must return quickly,
// so they only drop a command here. loop() does the actual motor work.
portMUX_TYPE     cmdMux = portMUX_INITIALIZER_UNLOCKED;
volatile uint8_t cmdType = CMD_NONE;
volatile uint8_t cmdPercent = 0;

bool     wasConnected = false;
uint32_t awakeUntilMs = 0;
uint32_t lastBatteryReportMs = 0;

// These survive deep sleep (but not a power cut or reset button).
RTC_DATA_ATTR long     rtcPosition = 0;
RTC_DATA_ATTR bool     rtcHomed = false;
RTC_DATA_ATTR bool     rtcHomeTried = false;
RTC_DATA_ATTR uint32_t rtcWakeCount = 0;

// =====================================================================================
//  Encoder
// =====================================================================================

// Quadrature lookup: index = (previous AB << 2) | current AB, value = step (-1, 0, +1)
static DRAM_ATTR const int8_t QUAD_STEP[16] = { 0, -1, 1, 0, 1, 0, 0, -1, -1, 0, 0, 1, 0, 1, -1, 0 };

void ARDUINO_ISR_ATTR encoderISR() {
  portENTER_CRITICAL_ISR(&encMux);
  uint8_t now = (uint8_t)((digitalRead(PIN_ENC_A) << 1) | digitalRead(PIN_ENC_B));
  if (encActive) {
    int8_t step = QUAD_STEP[(encPrev << 2) | now];
    encCount += ENCODER_REVERSED ? -step : step;
  }
  encPrev = now;
  portEXIT_CRITICAL_ISR(&encMux);
}

long encRead() {
  portENTER_CRITICAL(&encMux);
  long v = encCount;
  portEXIT_CRITICAL(&encMux);
  return v;
}

void encWrite(long v) {
  portENTER_CRITICAL(&encMux);
  encCount = v;
  portEXIT_CRITICAL(&encMux);
}

void encoderOn() {
  if (PIN_ENC_POWER >= 0) {
    digitalWrite(PIN_ENC_POWER, HIGH);
    delay(10);  // let the hall sensors wake up
  }
  portENTER_CRITICAL(&encMux);
  encPrev = (uint8_t)((digitalRead(PIN_ENC_A) << 1) | digitalRead(PIN_ENC_B));
  encActive = true;
  portEXIT_CRITICAL(&encMux);
}

void encoderOff() {
  portENTER_CRITICAL(&encMux);
  encActive = false;  // ignore the edges made by switching the power off
  portEXIT_CRITICAL(&encMux);
  if (PIN_ENC_POWER >= 0) {
    digitalWrite(PIN_ENC_POWER, LOW);
  }
}

// =====================================================================================
//  Motor driver (DRV8833)
// =====================================================================================

// direction: +1 = away from the home stop, -1 = toward the home stop
void motorDrive(int direction, uint8_t pwm) {
  if (MOTOR_REVERSED) {
    direction = -direction;
  }
  if (direction > 0) {
    ledcWrite(PIN_MOTOR_IN2, 0);
    ledcWrite(PIN_MOTOR_IN1, pwm);
  } else {
    ledcWrite(PIN_MOTOR_IN1, 0);
    ledcWrite(PIN_MOTOR_IN2, pwm);
  }
}

void motorCoast() {  // both inputs low: motor freewheels, no force on the blind
  ledcWrite(PIN_MOTOR_IN1, 0);
  ledcWrite(PIN_MOTOR_IN2, 0);
}

void motorBrake() {  // both inputs high: motor terminals shorted, stops quickly
  ledcWrite(PIN_MOTOR_IN1, 255);
  ledcWrite(PIN_MOTOR_IN2, 255);
}

// Called once before a command's motor work ...
void beginMotion() {
  encoderOn();
  motorCoast();
  digitalWrite(PIN_MOTOR_SLEEP, HIGH);  // wake the DRV8833
  delay(3);                             // it needs about 1 ms to wake
}

// ... and ALWAYS once after it. Puts the DRV8833 back to sleep.
void endMotion() {
  motorCoast();
  digitalWrite(PIN_MOTOR_SLEEP, LOW);
  delay(SETTLE_MS);  // catch the last few counts while the motor spins down
  encoderOff();
  rtcPosition = encRead();
  rtcHomed = homed;
}

// =====================================================================================
//  Commands waiting
// =====================================================================================

void queueCommand(uint8_t type, uint8_t percent) {
  portENTER_CRITICAL(&cmdMux);
  cmdType = type;
  cmdPercent = percent;
  portEXIT_CRITICAL(&cmdMux);
}

bool takeCommand(uint8_t *type, uint8_t *percent) {
  portENTER_CRITICAL(&cmdMux);
  *type = cmdType;
  *percent = cmdPercent;
  cmdType = CMD_NONE;
  portEXIT_CRITICAL(&cmdMux);
  return *type != CMD_NONE;
}

// True when a running move should stop: new Zigbee command (including Stop), BOOT button
// pressed, or (bench mode) anything typed in the serial console.
bool interruptWaiting() {
  if (cmdType != CMD_NONE) {
    return true;
  }
  if (digitalRead(PIN_BUTTON) == LOW) {
    return true;
  }
#if STAY_AWAKE
  if (Serial.available() > 0) {
    return true;
  }
#endif
  return false;
}

// =====================================================================================
//  One motor run: the only place the motor is powered
// =====================================================================================

// Drives toward `target` (encoder counts) with soft start, slow-down before the target,
// stall detection and a time limit. Leaves the motor unpowered when it returns.
StopReason runTo(long target, uint8_t maxPwm, uint32_t timeLimitMs) {
  const long startPos = encRead();
  if (labs(target - startPos) < POSITION_TOLERANCE_COUNTS) {
    return STOP_DONE;
  }
  const int direction = (target > startPos) ? 1 : -1;
  const float rampStep = (255.0f - PWM_START) * CONTROL_TICK_MS / (float)RAMP_UP_MS;

  const uint32_t startMs = millis();
  uint32_t lastProgressMs = startMs + (START_GRACE_MS - STALL_TIME_MS);  // start-up grace
  long lastProgressPos = startPos;
  float pwm = PWM_START;
  StopReason why;

  for (;;) {
    const uint32_t now = millis();
    const long pos = encRead();
    const long remaining = (target - pos) * direction;

    if (remaining <= 0) {
      why = STOP_DONE;
      break;
    }
    if (interruptWaiting()) {
      why = STOP_INTERRUPTED;
      break;
    }
    if (now - startMs > timeLimitMs) {
      why = STOP_TIMEOUT;
      break;
    }
    if ((pos - startPos) * direction < -(long)WRONG_WAY_COUNTS) {
      why = STOP_WRONG_WAY;
      break;
    }
    // Stall check: has the encoder moved at all lately?
    if (labs(pos - lastProgressPos) >= (long)STALL_MIN_COUNTS) {
      lastProgressPos = pos;
      lastProgressMs = now;
    } else if ((int32_t)(now - lastProgressMs) > (int32_t)STALL_TIME_MS) {
      why = STOP_STALL;
      break;
    }

    // Speed: ramp up from PWM_START, and come down to PWM_APPROACH close to the target
    float limit = maxPwm;
    if (remaining < SLOWDOWN_COUNTS) {
      float nearTarget = PWM_APPROACH + ((float)maxPwm - PWM_APPROACH) * (float)remaining / (float)SLOWDOWN_COUNTS;
      if (nearTarget < limit) {
        limit = nearTarget;
      }
    }
    pwm += rampStep;
    if (pwm > limit) {
      pwm = limit;
    }
    motorDrive(direction, (uint8_t)pwm);
    delay(CONTROL_TICK_MS);
  }

  if (why == STOP_INTERRUPTED) {  // soft stop
    const float downStep = (255.0f - PWM_START) * CONTROL_TICK_MS / (float)RAMP_DOWN_MS;
    while (pwm > PWM_START) {
      motorDrive(direction, (uint8_t)pwm);
      delay(CONTROL_TICK_MS);
      pwm -= downStep;
    }
  }
  if (why == STOP_DONE || why == STOP_INTERRUPTED) {
    motorBrake();
    delay(BRAKE_MS);
  }
  // Stall, timeout, wrong way: power is simply cut at once (no brake, nothing pushing on the stop).
  motorCoast();
  return why;
}

uint32_t moveTimeLimit(long counts) {
  return MOVE_TIME_BASE_MS + (uint32_t)((float)labs(counts) * MOVE_TIME_PER_TURN_MS / COUNTS_PER_WAND_TURN);
}

// =====================================================================================
//  Homing
// =====================================================================================

// Turn gently toward the home stop until the encoder stops. `moved` = how far it went.
StopReason seekHomeStop(long *moved) {
  const long start = encRead();
  StopReason why = runTo(start - (TRAVEL_COUNTS + HOME_OVERTRAVEL_COUNTS), PWM_HOMING, HOMING_TIME_LIMIT_MS);
  delay(SETTLE_MS);
  *moved = labs(encRead() - start);
  return why;
}

// Full homing: back off a little, then feel for the home stop and call it 0.
// Returns true when the stop was found. Sets `fault` when it was not.
bool doHome() {
  homed = false;
  ledMode = LED_HOMING;
  Serial.println("Homing: feeling for the closed stop...");

  // 1. Back away a little. This is how we tell "already resting on the stop" from
  //    "the motor is not turning at all" (both look like an instant stall otherwise).
  const long start = encRead();
  StopReason why = runTo(start + HOME_BACKOFF_COUNTS, PWM_HOMING, BACKOFF_TIME_LIMIT_MS);
  delay(SETTLE_MS);
  const long movedBack = labs(encRead() - start);
  if (why == STOP_INTERRUPTED) {
    return false;
  }
  if (why == STOP_WRONG_WAY) {
    fault = FAULT_ENCODER;
    return false;
  }

  // 2. Feel for the stop at low power.
  long movedIn = 0;
  why = seekHomeStop(&movedIn);
  switch (why) {
    case STOP_STALL:
      if (movedBack < (long)MIN_MOVE_COUNTS && movedIn < (long)MIN_MOVE_COUNTS) {
        Serial.println("Homing failed: no encoder counts. Motor not turning (PWM_HOMING too low?) or encoder not wired.");
        fault = FAULT_ENCODER;
        return false;
      }
      encWrite(0);
      homed = true;
      Serial.printf("Homed. Travelled %ld counts to the stop.\n", movedIn);
      return true;
    case STOP_INTERRUPTED:
      return false;
    case STOP_WRONG_WAY:
      fault = FAULT_ENCODER;
      return false;
    default:  // STOP_DONE = went further than full travel with no stop, or STOP_TIMEOUT
      Serial.println("Homing failed: no stop found. Collar slipping, counts per turn wrong, or too slow for the time limit.");
      fault = FAULT_HOMING;
      return false;
  }
}

// =====================================================================================
//  Positions
// =====================================================================================

long percentToCounts(uint8_t percent) {
  long c = (long)((float)percent * (float)TILT_SCALE_COUNTS / 100.0f);
  return constrain(c, 0L, TRAVEL_COUNTS);
}

uint8_t countsToPercent(long counts) {
  long p = (counts * 100L + TILT_SCALE_COUNTS / 2) / TILT_SCALE_COUNTS;
  return (uint8_t)constrain(p, 0L, 100L);
}

// Move to a tilt percentage (0 = closed at the home stop). Homes first if needed.
// Returns true when it got there.
bool goToPercent(uint8_t percent) {
  if (!homed && !doHome()) {
    return false;
  }
  const long target = percentToCounts(percent);

  for (int attempt = 0; attempt < 2; attempt++) {
    ledMode = LED_SOLID;
    const long pos = encRead();
    StopReason why = STOP_DONE;

    if (target <= 0) {
      // Closing onto the home stop: quick for most of the way, then gentle until it stalls.
      // This also re-zeroes the position every time the blind is closed.
      if (pos > HOME_APPROACH_COUNTS) {
        why = runTo(HOME_APPROACH_COUNTS, PWM_RUN, moveTimeLimit(pos - HOME_APPROACH_COUNTS));
      }
      if (why == STOP_DONE || why == STOP_STALL) {
        long moved = 0;
        why = seekHomeStop(&moved);
        if (why == STOP_STALL) {
          if (moved < (long)MIN_MOVE_COUNTS) {
            return doHome();  // did not move at all: make sure it is really the stop
          }
          encWrite(0);
          return true;
        }
        if (why == STOP_DONE || why == STOP_TIMEOUT) {
          homed = false;
          fault = FAULT_HOMING;
          return false;
        }
      }
    } else {
      why = runTo(target, PWM_RUN, moveTimeLimit(target - pos));
      if (why == STOP_DONE) {
        return true;
      }
      if (why == STOP_STALL) {
        delay(SETTLE_MS);
        if (target > pos && encRead() >= TRAVEL_COUNTS - END_TOLERANCE_COUNTS) {
          return true;  // resting on the far stop, close enough to where we expected it
        }
        // Stalled earlier than expected: somebody turned the wand by hand, so the position
        // is wrong. Find home again and try once more.
        Serial.println("Stalled early: position was wrong (wand turned by hand?). Re-homing.");
        if (attempt == 0) {
          if (!doHome()) {
            return false;
          }
          continue;
        }
        fault = FAULT_BLOCKED;
        return false;
      }
    }

    if (why == STOP_INTERRUPTED) {
      return false;
    }
    if (why == STOP_WRONG_WAY) {
      homed = false;
      fault = FAULT_ENCODER;
      return false;
    }
    fault = FAULT_BLOCKED;  // time limit
    return false;
  }
  return false;
}

// =====================================================================================
//  Battery
// =====================================================================================

uint16_t readBatteryMv() {
  uint32_t sum = 0;
  for (int i = 0; i < 16; i++) {
    sum += analogReadMilliVolts(PIN_BATTERY);
    delay(1);
  }
  float pinMv = (float)sum / 16.0f;
  return (uint16_t)(pinMv * (BATT_R_TOP_OHMS + BATT_R_BOTTOM_OHMS) / BATT_R_BOTTOM_OHMS * BATT_CALIBRATION);
}

uint8_t batteryPercent(uint16_t mv) {
  if (mv <= BATT_EMPTY_MV) {
    return 0;
  }
  if (mv >= BATT_FULL_MV) {
    return 100;
  }
  return (uint8_t)(((uint32_t)(mv - BATT_EMPTY_MV) * 100UL) / (BATT_FULL_MV - BATT_EMPTY_MV));
}

bool batteryOkToMove() {
#if BATTERY_FITTED
  return readBatteryMv() >= BATT_CUTOFF_MV;
#else
  return true;
#endif
}

// =====================================================================================
//  Reports to Home Assistant
// =====================================================================================

void reportTilt() {
  if (!Zigbee.connected()) {
    return;
  }
  // Zigbee counts the other way round from Home Assistant: Zigbee 0 = open, 100 = closed.
  // ZHA shows 100 minus the Zigbee number, so we send 100 minus ours.
  zbCovering.setTiltPercentage(100 - countsToPercent(encRead()));
}

void reportBattery(bool sendNow) {
#if BATTERY_FITTED
  if (!Zigbee.connected()) {
    return;
  }
  uint16_t mv = readBatteryMv();
  zbCovering.setBatteryPercentage(batteryPercent(mv));
  zbCovering.setBatteryVoltage((uint8_t)(mv / 100));  // unit is 0.1 V
  if (sendNow) {
    zbCovering.reportBatteryPercentage();
  }
  lastBatteryReportMs = millis();
#else
  (void)sendNow;
#endif
}

// =====================================================================================
//  Zigbee callbacks (run in the Zigbee task: keep them tiny)
// =====================================================================================

void onZbOpen() {
  queueCommand(CMD_GOTO, OPEN_PERCENT);  // slats level
}

void onZbClose() {
  queueCommand(CMD_GOTO, 0);  // closed, at the home stop
}

void onZbStop() {
  queueCommand(CMD_STOP, 0);
}

void onZbGoToTilt(uint8_t zigbeePercent) {
  if (zigbeePercent > 100) {
    zigbeePercent = 100;
  }
  queueCommand(CMD_GOTO, 100 - zigbeePercent);
}

void onZbIdentify(uint16_t seconds) {  // "Identify" in ZHA blinks the LED so you can find this blind
  identifyUntilMs = millis() + (uint32_t)seconds * 1000UL;
}

// =====================================================================================
//  LED
// =====================================================================================

LedMode idleLedMode() {
  if (fault != FAULT_NONE) {
    return LED_FAULT;
  }
  if (!Zigbee.connected()) {
    return LED_SEARCHING;
  }
#if STAY_AWAKE
  return LED_HEARTBEAT;
#else
  return LED_OFF;
#endif
}

void ledTask(void *arg) {
  (void)arg;
  for (;;) {
    const uint32_t ms = millis();
    bool on = false;
    if ((int32_t)(identifyUntilMs - ms) > 0) {
      on = (ms / 250) % 2;  // identify: steady 2 blinks a second
    } else {
      switch (ledMode) {
        case LED_SEARCHING: on = (ms / 100) % 2; break;     // fast blink: looking for the network
        case LED_HEARTBEAT: on = (ms % 5000) < 40; break;   // tiny flash every 5 s: joined and idle
        case LED_SOLID:     on = true; break;               // moving (or button held 1.5 s)
        case LED_HOMING:    on = (ms / 500) % 2; break;     // slow blink: homing
        case LED_FLICKER:   on = (ms / 40) % 2; break;      // flicker: factory reset armed
        case LED_FAULT:
        {
          // N blinks, pause, repeat. N = fault number.
          const uint32_t n = ledFaultBlinks;
          const uint32_t phase = ms % (n * 400 + 1600);
          on = (phase < n * 400) && ((phase % 400) < 200);
          break;
        }
        default: on = false; break;
      }
    }
    digitalWrite(PIN_LED, on ? LED_ON_LEVEL : !LED_ON_LEVEL);
    vTaskDelay(pdMS_TO_TICKS(20));
  }
}

void showIdleLed() {
  ledFaultBlinks = (uint8_t)fault;
  ledMode = idleLedMode();
}

// =====================================================================================
//  Running a command
// =====================================================================================

void noteActivity() {
  uint32_t until = millis() + AFTER_ACTIVITY_AWAKE_MS;
  if ((int32_t)(until - awakeUntilMs) > 0) {
    awakeUntilMs = until;
  }
}

void runCommand(uint8_t type, uint8_t percent) {
  if (type == CMD_STOP) {
    // If a move was running it has already been stopped (the waiting command interrupted it).
    Serial.println("Stop.");
    reportTilt();
    return;
  }
  if (!batteryOkToMove()) {
    Serial.println("Battery too low, not moving.");
    fault = FAULT_LOW_BATTERY;
    showIdleLed();
    reportTilt();  // tell Home Assistant the slats did not move
    reportBattery(true);
    return;
  }

  fault = FAULT_NONE;
  beginMotion();
  bool ok;
  if (type == CMD_HOME) {
    Serial.println("Command: re-home");
    ok = doHome();
  } else {
    Serial.printf("Command: go to %u %%\n", percent);
    ok = goToPercent(percent);
  }
  endMotion();  // DRV8833 asleep, encoder off, position saved

  Serial.printf("%s. Position %ld counts = %u %%, fault %u\n", ok ? "Done" : "Not completed", encRead(), countsToPercent(encRead()), (unsigned)fault);
  reportTilt();
  reportBattery(true);
  showIdleLed();
}

// =====================================================================================
//  BOOT button: hold 1.5 s and release = re-home, hold 5 s = factory reset
// =====================================================================================

void handleButton() {
  if (digitalRead(PIN_BUTTON) != LOW) {
    return;
  }
  delay(50);  // debounce
  if (digitalRead(PIN_BUTTON) != LOW) {
    return;
  }
  const uint32_t pressedMs = millis();
  uint32_t held = 0;
  while (digitalRead(PIN_BUTTON) == LOW) {
    held = millis() - pressedMs;
    if (held >= BUTTON_RESET_MS) {
      ledMode = LED_FLICKER;  // "you can let go now"
    } else if (held >= BUTTON_HOME_MS) {
      ledMode = LED_SOLID;
    } else {
      ledMode = LED_OFF;
    }
    delay(20);
  }
  noteActivity();

  if (held >= BUTTON_RESET_MS) {
    Serial.println("Factory reset: forgetting the Zigbee network and restarting.");
    rtcHomed = false;
    rtcHomeTried = false;
    rtcPosition = 0;
    delay(500);
    Zigbee.factoryReset();  // erases the Zigbee pairing and restarts the board
    delay(5000);
    ESP.restart();
  } else if (held >= BUTTON_HOME_MS) {
    queueCommand(CMD_HOME, 0);
  } else {
    // short press: just clear a fault blink
    fault = FAULT_NONE;
  }
  showIdleLed();
}

// =====================================================================================
//  Serial console (bench testing, stay-awake mode only). 115200 baud, end lines with Enter.
// =====================================================================================
#if STAY_AWAKE

void printStatus() {
  const long pos = encRead();
  Serial.printf("Position: %ld counts = %.2f wand turns = %u %%   homed: %s   fault: %u\n", pos, (float)pos / COUNTS_PER_WAND_TURN, countsToPercent(pos),
                homed ? "yes" : "no", (unsigned)fault);
  Serial.printf("Counts per wand turn: %.1f   full travel: %ld counts\n", COUNTS_PER_WAND_TURN, TRAVEL_COUNTS);
  Serial.printf("Zigbee: %s   battery pin: %u mV%s\n", Zigbee.connected() ? "joined" : "not joined", readBatteryMv(), BATTERY_FITTED ? "" : " (BATTERY_FITTED is 0, not checked)");
}

void printHelp() {
  Serial.println("Commands:  0..100 = go to tilt %   o = open (level)   c = close   h = home");
  Serial.println("           s = stop (any key stops a move)   p = print status   ? = this help");
  Serial.println("           t2 / t-2 = turn the wand 2 turns away from / toward home (no limits! bench only)");
  Serial.println("           z = call the current position home WITHOUT moving (bench only)");
}

void handleSerial() {
  if (Serial.available() <= 0) {
    return;
  }
  String line = Serial.readStringUntil('\n');
  line.trim();
  if (line.length() == 0) {
    return;
  }
  const char c = line.charAt(0);
  if (c == 'p') {
    printStatus();
  } else if (c == '?') {
    printHelp();
  } else if (c == 's') {
    queueCommand(CMD_STOP, 0);
  } else if (c == 'h') {
    queueCommand(CMD_HOME, 0);
  } else if (c == 'o') {
    queueCommand(CMD_GOTO, OPEN_PERCENT);
  } else if (c == 'c') {
    queueCommand(CMD_GOTO, 0);
  } else if (c == 'z') {
    encWrite(0);
    homed = true;
    fault = FAULT_NONE;
    Serial.println("This position is now 0 (home). Nothing moved.");
  } else if (c == 't') {
    // Turn test for calibration: turn exactly N wand turns according to the current constants.
    const float turns = line.substring(1).toFloat();
    if (turns == 0.0f || fabsf(turns) > 20.0f) {
      Serial.println("Use t followed by a number of turns, for example t10 or t-0.5");
      return;
    }
    const long before = encRead();
    const long distance = (long)(turns * COUNTS_PER_WAND_TURN);
    beginMotion();
    StopReason why = runTo(before + distance, PWM_RUN, moveTimeLimit(distance));
    endMotion();
    homed = false;  // limits were ignored, so the position can no longer be trusted
    const char *names[] = { "reached target", "STALLED", "TIME LIMIT", "interrupted", "ENCODER COUNTS BACKWARDS" };
    Serial.printf("Turn test: asked %.2f turns, moved %ld counts (%s). Now not homed.\n", turns, encRead() - before, names[why]);
  } else if (isDigit(c)) {
    const long p = line.toInt();
    queueCommand(CMD_GOTO, (uint8_t)constrain(p, 0L, 100L));
  } else {
    printHelp();
  }
}

#endif  // STAY_AWAKE

// =====================================================================================
//  Deep sleep (battery mode only)
// =====================================================================================
#if !STAY_AWAKE

void goToSleep(uint32_t seconds) {
  rtcPosition = encRead();
  rtcHomed = homed;
  rtcHomeTried = homeTriedThisBoot;
  motorCoast();
  digitalWrite(PIN_MOTOR_SLEEP, LOW);
  encoderOff();
  ledMode = LED_OFF;
  digitalWrite(PIN_LED, !LED_ON_LEVEL);
  Serial.printf("Sleeping %lu s\n", (unsigned long)seconds);
  Serial.flush();
  esp_sleep_enable_timer_wakeup((uint64_t)seconds * 1000000ULL);
  esp_deep_sleep_start();  // the board restarts from setup() when it wakes
}

#endif  // !STAY_AWAKE

// =====================================================================================
//  setup / loop
// =====================================================================================

void setup() {
  // Motor driver first, so it is asleep before anything else happens
  pinMode(PIN_MOTOR_SLEEP, OUTPUT);
  digitalWrite(PIN_MOTOR_SLEEP, LOW);
  ledcAttach(PIN_MOTOR_IN1, PWM_FREQ_HZ, PWM_BITS);
  ledcAttach(PIN_MOTOR_IN2, PWM_FREQ_HZ, PWM_BITS);
  motorCoast();

  Serial.begin(115200);
  Serial.setTimeout(50);

  pinMode(PIN_LED, OUTPUT);
  digitalWrite(PIN_LED, !LED_ON_LEVEL);
  pinMode(PIN_BUTTON, INPUT_PULLUP);

  if (PIN_ENC_POWER >= 0) {
    pinMode(PIN_ENC_POWER, OUTPUT);
    digitalWrite(PIN_ENC_POWER, LOW);
  }
  pinMode(PIN_ENC_A, INPUT_PULLUP);
  pinMode(PIN_ENC_B, INPUT_PULLUP);
  attachInterrupt(digitalPinToInterrupt(PIN_ENC_A), encoderISR, CHANGE);
  attachInterrupt(digitalPinToInterrupt(PIN_ENC_B), encoderISR, CHANGE);

  // Woke from deep sleep? Then the position we saved is still good.
  const bool wokeFromSleep = (esp_reset_reason() == ESP_RST_DEEPSLEEP);
  if (wokeFromSleep) {
    encWrite(rtcPosition);
    homed = rtcHomed;
    homeTriedThisBoot = rtcHomeTried;
    rtcWakeCount++;
  } else {
    rtcPosition = 0;
    rtcHomed = false;
    rtcHomeTried = false;
    rtcWakeCount = 0;
  }

  ledMode = LED_SEARCHING;
  xTaskCreate(ledTask, "led", 2048, NULL, 1, NULL);

  // ---- Zigbee: a window covering that only tilts ----
  zbCovering.setManufacturerAndModel(ZIGBEE_MAKER, ZIGBEE_MODEL);
  zbCovering.setCoveringType(BLIND_TILT_ONLY);
  // operational, online, commands not reversed, lift closed loop (no), tilt closed loop (yes),
  // lift encoder (no), tilt encoder (yes)
  zbCovering.setConfigStatus(true, true, false, false, true, false, true);
  // motor not reversed, not in calibration mode, not in maintenance mode, LED feedback on
  zbCovering.setMode(false, false, false, true);
  // lift open/closed limits (unused), tilt open/closed limits in 0.1 degree steps
  zbCovering.setLimits(0, 100, 0, 1800);
  // Battery device: adds the Zigbee power cluster so Home Assistant shows a battery level
  zbCovering.setPowerSource(ZB_POWER_SOURCE_BATTERY, 100, 37);

  zbCovering.onOpen(onZbOpen);
  zbCovering.onClose(onZbClose);
  zbCovering.onStop(onZbStop);
  zbCovering.onGoToTiltPercentage(onZbGoToTilt);
  zbCovering.onIdentify(onZbIdentify);

  Zigbee.addEndpoint(&zbCovering);

#if STAY_AWAKE
  const bool started = Zigbee.begin();  // end device, radio always listening
#else
  // Battery mode: tell the network this is a sleepy device (the parent then holds messages
  // for a few seconds until we ask for them) and ask for messages every POLL_INTERVAL_MS.
  Zigbee.setRxOnWhenIdle(false);
  esp_zb_cfg_t zigbeeConfig = ZIGBEE_DEFAULT_ED_CONFIG();
  zigbeeConfig.nwk_cfg.zed_cfg.keep_alive = POLL_INTERVAL_MS;
  const bool started = Zigbee.begin(&zigbeeConfig, false);
#endif
  if (!started) {
    Serial.println("Zigbee failed to start. Restarting in 5 s.");
    delay(5000);
    ESP.restart();
  }

  awakeUntilMs = millis() + (wokeFromSleep ? JOIN_WAIT_MS : COLD_BOOT_AWAKE_MS);

#if STAY_AWAKE
  Serial.println("\nFamilyHub blind tilt. Stay-awake (bench) mode. Type ? for commands.");
  Serial.println("Not joined yet? Put ZHA in 'Add device' mode. The LED blinks fast while it searches.");
#endif
}

void loop() {
  handleButton();

  // ---- Just (re)joined the network ----
  const bool connected = Zigbee.connected();
  if (connected && !wasConnected) {
    Serial.println("Zigbee: joined.");
    reportTilt();
    reportBattery(rtcWakeCount % BATT_REPORT_EVERY_WAKES == 0);
#if !STAY_AWAKE
    if (esp_reset_reason() == ESP_RST_DEEPSLEEP) {
      awakeUntilMs = millis() + LISTEN_WINDOW_MS;  // short listening window, then back to sleep
    }
#endif
    // First boot after pairing (or after a power cut): find the home stop once.
    if (HOME_ON_FIRST_CONNECT && !homed && !homeTriedThisBoot) {
      homeTriedThisBoot = true;
      queueCommand(CMD_HOME, 0);
    }
  }
  wasConnected = connected;

  // ---- A command is waiting ----
  uint8_t type, percent;
  if (takeCommand(&type, &percent)) {
    noteActivity();
    runCommand(type, percent);
    noteActivity();
  }

#if STAY_AWAKE
  handleSerial();
  if (millis() - lastBatteryReportMs > BATT_REPORT_INTERVAL_MS) {
    lastBatteryReportMs = millis();
    reportBattery(true);
  }
#else
  // ---- Battery mode: time to sleep? ----
  if ((int32_t)(millis() - awakeUntilMs) > 0 && cmdType == CMD_NONE && digitalRead(PIN_BUTTON) != LOW) {
    uint32_t seconds = SLEEP_SECONDS;
    if (!connected) {
      seconds = NOT_JOINED_SLEEP_SECONDS;
    }
#if BATTERY_FITTED
    if (readBatteryMv() < BATT_CUTOFF_MV) {
      seconds = LOW_BATT_SLEEP_SECONDS;
    }
#endif
    goToSleep(seconds);
  }
#endif

  showIdleLed();
  delay(20);
}
