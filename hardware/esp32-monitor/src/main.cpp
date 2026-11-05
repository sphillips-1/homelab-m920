#include <Arduino.h>
#include <WiFi.h>
#include <HTTPClient.h>
#include <WiFiManager.h>
#include <TFT_eSPI.h>
#include <ArduinoJson.h>
#include <Preferences.h>
#include <math.h>
#include "health.h"
#include "evolution.h"

TFT_eSPI tft;
TFT_eSprite pet(&tft);
WiFiManager wifi;
Preferences storage;
Readings readings;
Evolution evolution;
Health health{Mood::Offline, "Waiting for metrics"};
const uint16_t bg = 0x0842, muted = 0x9CD3, accent = 0x4EBA;
uint32_t lastPoll = 0, lastGood = 0, pressed = 0, lastFrame = 0;
uint32_t lastMinute = 0, lastSave = 0, lastCare = 0, feedbackAt = 0;
unsigned long hostUptime = 0;
bool hasData = false, online = false, longHandled = false, cared = false;
bool spriteReady = false, dirty = true, storeReady = false;
int page = 0, fullness = 80, happiness = 80;
const char *feedback = "";

const char *stage() {
  return formFor(evolution.healthMs) == Form::Warrior ? "Hobgoblin" :
      formFor(evolution.healthMs) == Form::Adult ? "Adult goblin" : "Baby goblin";
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
void savePet() {
  if (storeReady) {
    // A single NVS value prevents mixing generations on power loss.
    uint32_t value = fullness | (happiness << 7);
    storage.putUInt("care", value);
    storage.putUInt("health-v1", evolution.healthMs);
  }
  lastSave = millis();
}
void care() {
  if (page != 1 && page != 2) return;
  feedbackAt = millis();
  if (cared && millis() - lastCare < 30000) {
    feedback = "Let me enjoy that first!";
  } else {
    if (page == 1) fullness = min(100, fullness + 20);
    else happiness = min(100, happiness + 20);
    cared = true; lastCare = millis();
    feedback = page == 1 ? "Crunch! Thanks for the snack." : "That was fun!";
    savePet();
  }
  dirty = true;
}
void drawPet() {
  if (!spriteReady) return;
  pet.fillSprite(bg);
  Form form = formFor(evolution.healthMs);
  bool warrior = form == Form::Warrior, baby = form == Form::Baby;
  int y = (baby ? 32 : 19) + ((millis() / 500) % 2 ? 2 : 0);
  uint16_t skin = warrior ? TFT_RED : TFT_GREEN;
  uint16_t cloth = warrior ? 0x3186 : baby ? 0xE6FA : 0x92A8;
  int left = baby ? 48 : 52, width = baby ? 64 : 56;
  int headHeight = baby ? 42 : 38;
  pet.fillEllipse(80, 99, 46, 5, 0x18C3);
  pet.fillTriangle(24, y + 5, left + 9, y + 14, left, y + 31, skin);
  pet.fillTriangle(136, y + 5, 151 - left, y + 14, 160 - left, y + 31, skin);
  pet.fillRect(left, y, width, headHeight, skin);
  pet.fillRect(left - 6, y + 10, width + 12, 23, skin);
  pet.fillRect(56, y + headHeight, 48, baby ? 15 : 33, cloth);
  pet.fillRect(49, y + (baby ? 57 : 71), 22, 7, skin);
  pet.fillRect(89, y + (baby ? 57 : 71), 22, 7, skin);
  if (!baby) {
    pet.fillRect(45, y + 42, 11, 23, skin);
    pet.fillRect(104, y + 42, 11, 23, skin);
    pet.fillRect(54, y + 37, 52, 6, warrior ? 0xBDF7 : TFT_ORANGE);
    pet.fillRect(56, y + 61, 48, 5, 0x6204);
    pet.fillRect(76, y + 60, 8, 7, TFT_YELLOW);
  }
  if (warrior) {
    // Steel helmet, pauldrons, sword and shield distinguish the final form.
    pet.fillRect(51, y - 5, 58, 10, 0xBDF7);
    pet.fillRect(75, y - 12, 10, 9, TFT_RED);
    pet.fillRect(45, y + 39, 16, 9, 0xBDF7);
    pet.fillRect(99, y + 39, 16, 9, 0xBDF7);
    pet.fillRect(126, y + 17, 5, 44, 0xDEFB);
    pet.fillTriangle(126, y + 17, 130, y + 17, 128, y + 9, TFT_WHITE);
    pet.fillRect(121, y + 60, 15, 4, TFT_YELLOW);
    pet.fillRect(126, y + 64, 5, 11, 0x6204);
    pet.fillRect(23, y + 43, 24, 24, 0x738E);
    pet.fillTriangle(23, y + 67, 47, y + 67, 35, y + 79, 0x738E);
    pet.fillRect(33, y + 47, 4, 23, TFT_RED);
  } else if (baby) {
    pet.fillRect(71, y - 4, 6, 7, 0x4C63);
  }
  bool blink = (millis() / 500) % 9 == 0;
  pet.fillRect(56, y + 15, 14, blink ? 3 : 10, TFT_BLACK);
  pet.fillRect(90, y + 15, 14, blink ? 3 : 10, TFT_BLACK);
  if (health.mood == Mood::Critical || health.mood == Mood::Warning) {
    pet.drawLine(55, y + 8, 70, y + 12, TFT_BLACK);
    pet.drawLine(90, y + 12, 105, y + 8, TFT_BLACK);
    pet.drawLine(70, y + 34, 80, y + 29, TFT_BLACK);
    pet.drawLine(80, y + 29, 90, y + 34, TFT_BLACK);
  } else if (fullness < 30 || happiness < 30 || !online || health.mood == Mood::Unknown) {
    pet.fillRect(72, y + 32, 16, 3, TFT_BLACK);
  } else {
    pet.fillRect(68, y + 30, 24, 4, TFT_BLACK);
    pet.fillRect(72, y + 34, 16, 4, TFT_BLACK);
    pet.fillRect(70, y + 30, 4, 5, TFT_WHITE);
  }
  if (warrior) {
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
void bar(const char *label, int value, int x, int y) {
  tft.setTextColor(muted, bg);
  tft.drawString(String(label) + " " + value, x, y, 1);
  tft.fillRect(x, y + 12, 116, 6, 0x2945);
  tft.fillRect(x, y + 12, value * 116 / 100, 6, value < 30 ? TFT_ORANGE : accent);
}
void render() {
  tft.fillScreen(bg);
  tft.setTextColor(accent, bg);
  tft.drawString("SHELF GOBLIN", 10, 7, 2);
  tft.setTextColor(healthColor(), bg);
  tft.drawRightString(healthLabel(), 310, 7, 2);
  tft.drawFastHLine(10, 30, 300, muted);
  tft.drawString(health.reason, 10, 36, 2);
  if (page == 3) {
    tft.setTextColor(TFT_WHITE, bg);
    tft.drawString("CPU " + metric(readings.cpu) + "   RAM " + metric(readings.ram), 10, 68, 2);
    tft.drawString("CPU temperature " + metric(readings.temp, " C"), 10, 93, 2);
    tft.drawString("System " + metric(readings.root) + "   Media " + metric(readings.media), 10, 118, 2);
    String containers = readings.total < 0 ? "Containers unknown" :
        "Containers " + String(readings.running) + "/" + readings.total + "  Bad " + readings.unhealthy;
    tft.drawString(containers, 10, 143, 2);
    tft.setTextColor(muted, bg);
    String up = online ? "Up " + String(hostUptime / 86400) + "d " + String((hostUptime / 3600) % 24) + "h" : "No live metrics";
    tft.drawString(up + "  Wi-Fi " + String(WiFi.RSSI()) + "dBm", 10, 174, 2);
  } else {
    drawPet();
    if (!spriteReady) {
      tft.setTextColor(accent, bg);
      tft.drawString("( ^ v ^ )", 30, 105, 2);
    }
    tft.setTextColor(TFT_WHITE, bg);
    tft.drawString(stage(), 182, 67, 2);
    tft.setTextColor(muted, bg);
    Form form = formFor(evolution.healthMs);
    tft.drawString(form == Form::Warrior ? "Red warrior" : form == Form::Adult ? "Green adult" : "Green baby", 182, 86, 1);
    bar("Fullness", fullness, 182, 102);
    bar("Happiness", happiness, 182, 128);
    tft.setTextColor(muted, bg);
    tft.drawString("Health " + duration(evolution.healthMs), 182, 153, 1);
    String next = form == Form::Baby ? "Adult in " + duration(ADULT_AT_MS - evolution.healthMs) :
        form == Form::Adult ? "Warrior " + duration(WARRIOR_AT_MS - evolution.healthMs) : "Final form";
    tft.drawString(next, 182, 165, 1);
    tft.setTextColor(TFT_WHITE, bg);
    const char *caption = page == 1 ? "Hold BOOT 1s: feed" : page == 2 ? "Hold BOOT 1s: play" :
        fullness < 30 ? "A snack would be lovely." : happiness < 30 ? "Come play with me!" : "Keeping watch over the lab.";
    tft.drawString(caption, 10, 178, 2);
  }
  tft.setTextColor(accent, bg);
  tft.drawString(page == 0 ? "HOME" : page == 1 ? "FEED" : page == 2 ? "PLAY" : "METRICS", 10, 203, 1);
  tft.setTextColor(muted, bg);
  if (*feedback && millis() - feedbackAt < 4000) tft.drawString(feedback, 65, 203, 1);
  else if (!online) tft.drawString(hasData ? "Last update " + String((millis() - lastGood) / 1000) + "s ago" : "Waiting for first sample", 65, 203, 1);
  else tft.drawString("CPU " + metric(readings.cpu) + " / RAM " + metric(readings.ram), 65, 203, 1);
  tft.drawString("BOOT: next | hold 5s: Wi-Fi setup", 10, 224, 1);
  dirty = false;
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
  if (formFor(evolution.healthMs) != oldForm) savePet();
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
  uint32_t saved = storeReady ? storage.getUInt("care", 80U | (80U << 7)) : (80U | (80U << 7));
  fullness = min(100U, saved & 127U);
  happiness = min(100U, (saved >> 7) & 127U);
  // Migrate care needs, but never turn old feed/play points into healthy time.
  evolution = Evolution(storeReady ? storage.getUInt("health-v1", 0) : 0);
  message("Starting Wi-Fi...", "Hold BOOT 5s to set up Wi-Fi");
  wifi.setConfigPortalBlocking(false);
  wifi.setDebugOutput(false);
  wifi.setAPCallback([](WiFiManager *) {
    message("Wi-Fi setup: M920-Display", "Join it; open 192.168.4.1");
  });
  wifi.autoConnect("M920-Display");
  lastMinute = millis();
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
      if (duration >= 1000) care();
      else if (duration >= 40) { page = (page + 1) % 4; dirty = true; }
    }
    pressed = 0; longHandled = false;
  }
  now = millis();
  // One point per 15 powered minutes; unplugging never punishes the goblin.
  if (now - lastMinute >= 900000) {
    unsigned int ticks = (now - lastMinute) / 900000;
    lastMinute += ticks * 900000;
    fullness = max(0, fullness - static_cast<int>(ticks));
    happiness = max(0, happiness - static_cast<int>(ticks));
    dirty = true;
  }
  if (now - lastSave >= 300000) savePet();
  if (!wifi.getConfigPortalActive()) {
    // Avoid blocking requests during a button hold.
    if (!pressed && (lastPoll == 0 || now - lastPoll >= 5000)) {
      poll(); lastPoll = millis();
    }
    if (*feedback && now - feedbackAt >= 4000) { feedback = ""; dirty = true; }
    if (dirty) render();
    else if (page != 3 && now - lastFrame >= 500) drawPet();
    if (now - lastFrame >= 500) lastFrame = now;
  } else { evolution = evolution.paused(); dirty = true; }
  delay(10);
}
