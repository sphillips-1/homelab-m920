#include <Arduino.h>
#include <WiFi.h>
#include <HTTPClient.h>
#include <WiFiManager.h>
#include <TFT_eSPI.h>
#include <ArduinoJson.h>
#include <Preferences.h>
#include <SPI.h>
#include <XPT2046_Touchscreen.h>
#include <freertos/FreeRTOS.h>
#include <freertos/queue.h>
#include <math.h>
#include "health.h"
#include "evolution.h"
#include "touch_controls.h"

TFT_eSPI tft;
TFT_eSprite pet(&tft);
WiFiManager wifi;
Preferences storage;
SPIClass touchBus(VSPI);
XPT2046_Touchscreen touchscreen(33, 36);
QueueHandle_t touchEvents = nullptr;
volatile bool touchDown = false;
bool touchReady = false, calibrationActive = false, calibrated = false;
int calibrationStep = 0;
TouchCalibration calibration{}, candidate{};
TouchPoint calibrationRaw[3];
const char *calibrationHint = "Tap the target, then lift your finger";
Readings readings;
Evolution evolution;
const char *newClass = nullptr;
uint32_t classObtainedAt = 0;
Health health{Mood::Offline, "Waiting for metrics"};
const uint16_t bg = 0x0842, muted = 0x9CD3, accent = 0x4EBA;
uint32_t lastPoll = 0, lastGood = 0, pressed = 0, lastFrame = 0;
uint32_t lastSave = 0;
unsigned long hostUptime = 0;
bool hasData = false, online = false, longHandled = false;
bool spriteReady = false, dirty = true, storeReady = false;
int page = 0; // 0: goblin, 1: metrics.

// Only this task accesses the touch SPI bus. Queue gestures during HTTP requests
// instead of dropping them while the UI thread is waiting for the server.
void sampleTouch(void *) {
  uint32_t started = 0, sumX = 0, sumY = 0;
  unsigned int count = 0, released = 0;
  TouchPoint first{}, last{};
  int maxMotion = 0;
  for (;;) {
    bool down = touchscreen.touched();
    touchDown = down;
    if (down) {
      TS_Point p = touchscreen.getPoint();
      if (!count) { started = millis(); first = {p.x, p.y}; maxMotion = 0; }
      last = {p.x, p.y};
      maxMotion = max(maxMotion, max(abs(p.x - first.x), abs(p.y - first.y)));
      if (count < 100) { sumX += p.x; sumY += p.y; ++count; }
      released = 0;
    } else if (count && ++released >= 2) {
      uint32_t held = millis() - started;
      if (count >= 2 && held >= 40 && held <= 5000) {
        TouchStroke stroke{first, last,
            {static_cast<int>(sumX / count), static_cast<int>(sumY / count)}, held, maxMotion};
        xQueueSend(touchEvents, &stroke, 0);
      }
      count = 0; sumX = 0; sumY = 0;
    }
    vTaskDelay(pdMS_TO_TICKS(20));
  }
}

void startCalibration() {
  if (!touchReady) return;
  calibrationActive = true; calibrationStep = 0;
  calibrationHint = "Tap the target, then lift your finger";
  evolution = evolution.paused();
  xQueueReset(touchEvents);
  dirty = true;
}

void renderCalibration() {
  static const TouchPoint targets[] = {{24, 24}, {296, 24}, {24, 216}, {296, 216}};
  tft.fillScreen(bg);
  tft.setTextColor(accent, bg);
  tft.drawCentreString("TOUCH SETUP", 160, 70, 2);
  tft.setTextColor(TFT_WHITE, bg);
  tft.drawCentreString("Target " + String(calibrationStep + 1) + " of 4", 160, 98, 2);
  tft.setTextColor(muted, bg);
  tft.drawCentreString(calibrationHint, 160, 130, 1);
  tft.drawCentreString("Use a firm tap or a blunt stylus", 160, 148, 1);
  TouchPoint target = targets[calibrationStep];
  tft.drawCircle(target.x, target.y, 12, accent);
  tft.drawFastHLine(target.x - 16, target.y, 33, TFT_WHITE);
  tft.drawFastVLine(target.x, target.y - 16, 33, TFT_WHITE);
  dirty = false;
}

const char *healthLabel() {
  switch (health.mood) {
    case Mood::Healthy: return "HEALTHY";
    case Mood::Busy: return "BUSY";
    case Mood::Warning: return "WARNING";
    case Mood::Critical: return "ALERT";
    case Mood::Unknown: return "UNKNOWN";
    default: return "OFFLINE";
  }
}
uint16_t healthColor() {
  switch (health.mood) {
    case Mood::Critical: return TFT_RED;
    case Mood::Warning: return TFT_ORANGE;
    case Mood::Busy: return TFT_CYAN;
    case Mood::Healthy: return accent;
    default: return muted;
  }
}
void message(const String &title, const String &detail) {
  tft.fillScreen(bg);
  tft.setTextColor(accent, bg);
  tft.drawString("SHELF GOBLIN / M920Q", 10, 10, 2);
  tft.setTextColor(TFT_WHITE, bg);
  tft.drawString(title, 10, 65, 2);
  tft.setTextColor(muted, bg);
  tft.drawString(detail, 10, 100, 2);
}
void saveEvolution() {
  if (storeReady) {
    storage.putUInt("health-v1", evolution.healthMs);
  }
  lastSave = millis();
}
void drawPet() {
  if (!spriteReady) return;
  pet.fillSprite(bg);
  Form form = formFor(evolution.healthMs);
  const bool small = form < Form::Adult;
  const bool hob = form >= Form::Hobgoblin;
  int y = (small ? 32 : hob ? 17 : 22) + ((millis() / 500) % 2 ? 2 : 0);
  uint16_t skin = hob ? TFT_RED : TFT_GREEN;
  uint16_t cloth = hob ? 0x3186 : small ? 0xE6FA : 0x92A8;
  int width = small ? 64 : hob ? 64 : 56;
  int left = 80 - width / 2;
  int headHeight = small ? 42 : 38;
  pet.fillEllipse(80, 99, 46, 5, 0x18C3);
  pet.fillTriangle(24, y + 5, left + 9, y + 14, left, y + 31, skin);
  pet.fillTriangle(136, y + 5, 151 - left, y + 14, 160 - left, y + 31, skin);
  pet.fillRect(left, y, width, headHeight, skin);
  pet.fillRect(left - 6, y + 10, width + 12, 23, skin);
  pet.fillRect(56, y + headHeight, 48, small ? 15 : 33, cloth);
  pet.fillRect(49, y + (small ? 57 : 71), 22, 7, skin);
  pet.fillRect(89, y + (small ? 57 : 71), 22, 7, skin);
  if (!small) {
    pet.fillRect(45, y + 42, 11, 23, skin);
    pet.fillRect(104, y + 42, 11, 23, skin);
    pet.fillRect(54, y + 37, 52, 6, hob ? 0xBDF7 : TFT_ORANGE);
    pet.fillRect(56, y + 61, 48, 5, 0x6204);
    pet.fillRect(76, y + 60, 8, 7, TFT_YELLOW);
  }
  if (hob) {
    const uint16_t armor = form == Form::GoblinLord ? 0x3ACB : 0xBDF7;
    pet.fillRect(left - 1, y - 5, width + 2, 10, armor);
    pet.fillRect(75, y - 12, 10, 9, TFT_RED);
    pet.fillRect(43, y + 39, 18, 9, armor);
    pet.fillRect(99, y + 39, 18, 9, armor);
  } else if (small) {
    pet.fillRect(71, y - 4, 6, 7, 0x4C63);
  }
  if (form == Form::Scavenger || form == Form::Adult) {
    // Patchwork satchel and the first scavenged tool.
    pet.drawLine(62, y + 39, 101, y + 54, 0x6204);
    pet.fillRoundRect(97, y + 42, 21, 16, 3, 0xA344);
    pet.fillRect(103, y + 45, 8, 5, TFT_ORANGE);
    pet.drawLine(114, y + 48, 124, y + 36, 0xBDF7);
    pet.fillCircle(124, y + 35, 3, 0xBDF7);
  } else if (form == Form::Tactician || form == Form::Hobgoblin) {
    // A folded map and a crossbow carry over when the Tactician grows into a Hob.
    pet.fillRect(24, y + 47, 23, 18, 0xE6D0);
    pet.drawLine(31, y + 49, 31, y + 62, 0xA344);
    pet.drawLine(39, y + 49, 39, y + 62, 0xA344);
    pet.fillRect(123, y + 42, 5, 28, 0xA344);
    pet.drawLine(108, y + 52, 125, y + 43, TFT_YELLOW);
    pet.drawLine(125, y + 43, 143, y + 52, TFT_YELLOW);
    pet.drawFastHLine(108, y + 52, 36, 0xDEFB);
  } else if (form >= Form::Chieftain) {
    pet.fillRect(124, 6, 4, 84, 0xA344);
    pet.fillTriangle(128, 8, 156, 8, 128, 27, TFT_RED);
    if (form >= Form::GreatChieftain) {
      pet.fillTriangle(128, 24, 152, 24, 128, 41, TFT_GOLD);
      pet.fillTriangle(128, 39, 148, 39, 128, 54, TFT_CYAN);
      pet.fillTriangle(43, y + 48, 60, y + 43, 41, y + 73, 0x3ACB);
      pet.fillTriangle(117, y + 48, 100, y + 43, 119, y + 73, 0x3ACB);
    }
    if (form == Form::GoblinLord) {
      const int flame = 4 + (millis() / 500) % 2;
      pet.fillTriangle(72, y + 58, 88, y + 58, 80, y + 43 - flame, TFT_GREEN);
      pet.fillCircle(80, y + 54, 3, TFT_YELLOW);
    }
  }
  bool blink = (millis() / 500) % 9 == 0;
  pet.fillRect(56, y + 15, 14, blink ? 3 : 10, TFT_BLACK);
  pet.fillRect(90, y + 15, 14, blink ? 3 : 10, TFT_BLACK);
  if (health.mood == Mood::Critical || health.mood == Mood::Warning) {
    pet.drawLine(55, y + 8, 70, y + 12, TFT_BLACK);
    pet.drawLine(90, y + 12, 105, y + 8, TFT_BLACK);
    pet.drawLine(70, y + 34, 80, y + 29, TFT_BLACK);
    pet.drawLine(80, y + 29, 90, y + 34, TFT_BLACK);
  } else if (!online || health.mood == Mood::Unknown) {
    pet.fillRect(72, y + 32, 16, 3, TFT_BLACK);
  } else {
    pet.fillRect(68, y + 30, 24, 4, TFT_BLACK);
    pet.fillRect(72, y + 34, 16, 4, TFT_BLACK);
    pet.fillRect(70, y + 30, 4, 5, TFT_WHITE);
  }
  if (hob) {
    pet.fillTriangle(66, y + 35, 71, y + 35, 68, y + 28, TFT_WHITE);
    pet.fillTriangle(89, y + 35, 94, y + 35, 92, y + 28, TFT_WHITE);
  }
  pet.pushSprite(8, 61);
}
String metric(float value, const char *unit = "%") {
  return value < 0 ? "--" : String(value, 0) + unit;
}
String duration(uint32_t ms) {
  uint32_t hours = ms / 3600000;
  return hours >= 24 ? String(hours / 24) + "d " + String(hours % 24) + "h" :
      String(hours) + "h " + String((ms / 60000) % 60) + "m";
}
String countdown(uint32_t ms) {
  return ms < 60000 ? String((ms + 999) / 1000) + "s" : duration(ms);
}
void render() {
  tft.fillScreen(bg);
  tft.setTextColor(accent, bg);
  tft.drawString("SHELF GOBLIN", 10, 7, 2);
  tft.setTextColor(healthColor(), bg);
  tft.drawRightString(healthLabel(), 310, 7, 2);
  tft.drawFastHLine(10, 30, 300, muted);
  tft.drawString(health.reason, 10, 36, 2);
  if (page == 1) {
    tft.setTextColor(TFT_WHITE, bg);
    tft.drawString("CPU " + metric(readings.cpu) + "   RAM " + metric(readings.ram), 10, 68, 2);
    tft.drawString("CPU temperature " + metric(readings.temp, " C"), 10, 93, 2);
    tft.drawString("System " + metric(readings.root) + "   Media " + metric(readings.media), 10, 118, 2);
    String containers = readings.total < 0 ? "Containers unknown" :
        "Containers " + String(readings.running) + "/" + readings.total + "  Bad " + readings.unhealthy;
    tft.drawString(containers, 10, 143, 2);
    tft.setTextColor(muted, bg);
    String up = online ? "Up " + String(hostUptime / 86400) + "d " + String((hostUptime / 3600) % 24) + "h" : "No live metrics";
    tft.drawString(up + "  Wi-Fi " + String(WiFi.RSSI()) + "dBm", 10, 160, 1);
  } else {
    drawPet();
    if (!spriteReady) {
      tft.setTextColor(accent, bg);
      tft.drawString("( ^ v ^ )", 30, 105, 2);
    }
    tft.setTextColor(TFT_WHITE, bg);
    const Form form = formFor(evolution.healthMs);
    const auto &current = milestone(form);
    const String classTitle = current.className ? String("[") + current.className + "]" : "";
    const bool bodyMilestone = form == Form::Adult || form == Form::Hobgoblin;
    tft.drawString(!current.className || bodyMilestone ? String(current.name) : classTitle, 182, 67, 2);
    tft.setTextColor(muted, bg);
    if (bodyMilestone) tft.drawString(classTitle, 182, 86, 1);
    tft.drawString("HEALTHY TIME", 182, 108, 1);
    tft.setTextColor(TFT_WHITE, bg);
    tft.drawString(duration(evolution.healthMs), 182, 121, 2);
    tft.setTextColor(muted, bg);
    const uint32_t dropMs = timeToDrop(evolution.healthMs, health.mood);
    if (dropMs) {
      tft.setTextColor(healthColor(), bg);
      tft.drawString("Drop in " + countdown(dropMs), 182, 146, 1);
    } else if (form != Form::GoblinLord) {
      const auto &next = milestone(static_cast<Form>(static_cast<unsigned>(form) + 1));
      tft.drawString(String("Next: ") + next.name, 182, 146, 1);
      tft.drawString(countdown(next.thresholdMs - evolution.healthMs), 182, 157, 1);
    }
    tft.setTextColor(TFT_WHITE, bg);
  }
  if (page == 0) {
    tft.setTextColor(muted, bg);
    String caption = newClass ? String("[Class Obtained: ") + newClass + "]" :
        !touchReady ? "Touch unavailable; restart device" : !online ?
        (hasData ? "Last update " + String((millis() - lastGood) / 1000) + "s ago" : "Waiting for server metrics...") : "Keeping watch over the lab.";
    tft.drawCentreString(caption, 160, 180, 2);
  } else {
    tft.setTextColor(muted, bg);
    tft.drawCentreString("Hold 2s to recalibrate touch", 160, 190, 1);
  }
  tft.setTextColor(accent, bg);
  tft.drawCentreString(page == 0 ? "< Swipe left for metrics" : "Swipe right for goblin >", 160, 215, 2);
  dirty = false;
}

void handleTouch(const TouchStroke &stroke) {
  if (calibrationActive) {
    if (!isCalibrationTap(stroke)) return;
    TouchPoint raw = stroke.average;
    if (calibrationStep < 3) {
      calibrationRaw[calibrationStep++] = raw;
      if (calibrationStep == 3 && !calibrateTouch(calibrationRaw, candidate)) {
        calibrationStep = 0;
        calibrationHint = "Targets too close; please try again";
      }
    } else if (confirmsCalibration(candidate, raw)) {
      calibration = candidate;
      calibrated = true; calibrationActive = false;
      if (storeReady) storage.putBytes("touch-v1", &calibration, sizeof(calibration));
      Serial.println("Touch: calibration completed");
    } else {
      calibrationStep = 0;
      calibrationHint = "Alignment check failed; try again";
    }
    dirty = true;
    return;
  }
  if (!calibrated) return;
  switch (classifyGesture(calibration, stroke)) {
    case Gesture::Left: page = 1; dirty = true; break;
    case Gesture::Right: page = 0; dirty = true; break;
    case Gesture::Hold: startCalibration(); break;
    default: break;
  }
}
float reading(JsonVariant value, float maximum) {
  if (!value.is<float>()) return -1;
  float number = value.as<float>();
  return isfinite(number) && number >= 0 && number <= maximum ? number : -1;
}
void poll() {
  int64_t sampleTimestamp = 0;
  online = false; readings = Readings{};
  if (WiFi.status() == WL_CONNECTED) {
    WiFiClient client;
    HTTPClient http;
    http.setConnectTimeout(1500); http.setTimeout(1500);
    http.begin(client, "http://192.168.4.27:8091/status");
    int code = http.GET();
    JsonDocument doc;
    // The feed sends Content-Length. Bound allocations before reading the body.
    bool valid = code == 200 && http.getSize() > 0 && http.getSize() <= 4096;
    if (valid) valid = !deserializeJson(doc, http.getString()) && doc["sampled_at"].is<long>();
    if (valid) {
      readings.cpu = reading(doc["cpu"], 100);
      readings.ram = reading(doc["ram"], 100);
      readings.temp = reading(doc["temp"], 150);
      readings.root = reading(doc["disks"]["root"], 100);
      readings.media = reading(doc["disks"]["media"], 100);
      auto containers = doc["containers"];
      if (containers["running"].is<int>() && containers["total"].is<int>() && containers["unhealthy"].is<int>()) {
        int running = containers["running"], total = containers["total"], bad = containers["unhealthy"];
        if (running >= 0 && total >= running && bad >= 0 && bad <= running) {
          readings.running = running; readings.total = total; readings.unhealthy = bad;
        }
      }
      hostUptime = doc["uptime"] | 0UL;
      sampleTimestamp = doc["sampled_at"].as<int64_t>();
      lastGood = millis(); hasData = true; online = true;
    }
    http.end();
  }
  health = assess(readings, online);
  if (WiFi.status() != WL_CONNECTED) health = {Mood::Offline, "Wi-Fi disconnected"};
  Form oldForm = formFor(evolution.healthMs);
  evolution = evolution.observed(health.mood, millis(), sampleTimestamp);
  const Form form = formFor(evolution.healthMs);
  if (form != oldForm) {
    saveEvolution();
    newClass = form > oldForm && form != Form::Adult && form != Form::Hobgoblin ? milestone(form).className : nullptr;
    classObtainedAt = millis();
  }
  dirty = true;
}
void setup() {
  Serial.begin(115200);
  pinMode(0, INPUT_PULLUP);
  tft.init(); tft.setRotation(1);
  pinMode(21, OUTPUT); digitalWrite(21, HIGH);
  pet.setColorDepth(16);
  spriteReady = pet.createSprite(160, 110) != nullptr;
  storeReady = storage.begin("shelf-goblin", false);
  // Keep the existing evolution bank; retired care meters are no longer read.
  evolution = Evolution(storeReady ? storage.getUInt("health-v1", 0) : 0);
  calibrated = storeReady && storage.getBytesLength("touch-v1") == sizeof(calibration) &&
      storage.getBytes("touch-v1", &calibration, sizeof(calibration)) == sizeof(calibration) &&
      validCalibration(calibration);
  touchBus.begin(25, 39, 32, 33);
  touchReady = touchscreen.begin(touchBus);
  touchscreen.setRotation(1);
  touchEvents = xQueueCreate(8, sizeof(TouchStroke));
  touchReady = touchReady && touchEvents != nullptr;
  if (touchReady) touchReady = xTaskCreate(sampleTouch, "touch", 3072, nullptr, 1, nullptr) == pdPASS;
  if (!calibrated) startCalibration();
  message("Starting Wi-Fi...", "Hold BOOT 5s to set up Wi-Fi");
  wifi.setConfigPortalBlocking(false);
  wifi.setDebugOutput(false);
  wifi.setAPCallback([](WiFiManager *) {
    message("Wi-Fi setup: M920-Display", "Join it; open 192.168.4.1");
  });
  wifi.autoConnect("M920-Display");
}
void loop() {
  wifi.process();
  uint32_t now = millis();
  if (digitalRead(0) == LOW) {
    if (!pressed) pressed = now;
    if (!longHandled && now - pressed >= 5000) {
      longHandled = true;
      wifi.startConfigPortal("M920-Display");
    }
  } else if (pressed) {
    uint32_t duration = now - pressed;
    if (!longHandled && !wifi.getConfigPortalActive()) {
      if (duration >= 1000) startCalibration();
      else if (duration >= 40 && calibrationActive && calibrated) { calibrationActive = false; dirty = true; }
    }
    pressed = 0; longHandled = false;
  }
  now = millis();
  if (touchReady) {
    TouchStroke stroke;
    while (xQueueReceive(touchEvents, &stroke, 0) == pdTRUE) {
      if (!wifi.getConfigPortalActive()) handleTouch(stroke);
    }
  }
  now = millis();
  if (now - lastSave >= 300000) saveEvolution();
  if (!wifi.getConfigPortalActive()) {
    if (calibrationActive) {
      evolution = evolution.paused();
      if (dirty) renderCalibration();
      delay(10);
      return;
    }
    // Avoid blocking requests during a button hold.
    if (!pressed && !touchDown && (lastPoll == 0 || now - lastPoll >= 5000)) {
      poll(); lastPoll = millis();
    }
    if (newClass && millis() - classObtainedAt >= 5000) {
      newClass = nullptr;
      dirty = true;
    }
    if (dirty) render();
    else if (page == 0 && now - lastFrame >= 500) drawPet();
    if (now - lastFrame >= 500) lastFrame = now;
  } else { evolution = evolution.paused(); dirty = true; }
  delay(10);
}
