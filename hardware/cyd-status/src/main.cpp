#include <Arduino.h>
#include <ArduinoJson.h>
#include <HTTPClient.h>
#include <TFT_eSPI.h>
#include <WiFiManager.h>

#include "../../esp32-monitor/src/health.h"
#include "../../esp32-monitor/src/display_link.h"
#include "../../esp32-monitor/src/scene_art.h"

namespace {
constexpr char statusUrl[] = "http://192.168.4.27:8091/status";
constexpr char setupNetwork[] = "M920-Display";
constexpr uint32_t refreshMs = 5000;
constexpr int bootPin = 0;
TFT_eSPI display;
WiFiManager wifi;
uint32_t lastPoll = 0;
uint32_t pressedAt = 0;
bool pressing = false;
bool setupRequested = false;
bool portalWasActive = false;
bool wasConnected = false;
TFT_eSprite actor(&display);
bool actorReady = false;
QueueHandle_t pollRequests, pollResults;
struct Sample {
  Readings data;
  Health health{Mood::Offline, "Connecting to Wi-Fi"};
  uint32_t uptimeMinutes = 0;
  bool hasUptime = false;
};
Sample latest;
displayLink::Received remote{};
displayLink::Scene drawnScene = displayLink::Idle;
uint32_t lastAnimation = 0;

String uptimeText(const Sample &sample) {
  const uint32_t minutes = sample.uptimeMinutes;
  return sample.hasUptime ? String(minutes / 1440) + "d " + String(minutes / 60 % 24) +
      "h " + String(minutes % 60) + "m" : "--";
}

float reading(JsonVariantConst value, float maximum) {
  if (!value.is<float>()) return -1;
  const float number = value.as<float>();
  return number >= 0 && number <= maximum ? number : -1;
}

String metric(float value, const char *unit = "%") {
  return value < 0 ? String("--") : String(value, 0) + unit;
}

void row(int y, const char *label, const String &value) {
  display.setTextColor(TFT_LIGHTGREY, TFT_BLACK);
  display.drawString(label, 12, y, 2);
  display.setTextColor(TFT_WHITE, TFT_BLACK);
  display.drawRightString(value, 308, y, 2);
}

void render(const Readings &data, Health health, const String &uptime) {
  const char *label = "OFFLINE";
  uint16_t color = TFT_RED;
  switch (health.mood) {
    case Mood::Healthy: label = "HEALTHY"; color = TFT_GREEN; break;
    case Mood::Busy: label = "BUSY"; color = TFT_CYAN; break;
    case Mood::Warning: label = "WARNING"; color = TFT_YELLOW; break;
    case Mood::Critical: label = "CRITICAL"; break;
    case Mood::Unknown: label = "UNKNOWN"; color = TFT_LIGHTGREY; break;
    case Mood::Offline: break;
  }
  display.fillScreen(TFT_BLACK);
  display.setTextColor(TFT_WHITE, TFT_BLACK);
  display.drawString("M920Q HOMELAB", 12, 8, 2);
  display.setTextColor(color, TFT_BLACK);
  display.drawRightString(label, 308, 8, 2);
  display.drawFastHLine(12, 30, 296, color);
  display.drawString(health.reason, 12, 36, 2);
  row(59, "CPU", metric(data.cpu) + "  /  " + metric(data.temp, " C"));
  row(82, "Memory", metric(data.ram));
  row(105, "System disk", metric(data.root));
  row(128, "Media disk", metric(data.media));
  row(151, "Containers", data.total < 0 ? String("--") :
      String(data.running) + "/" + String(data.total) + " up, " + String(data.unhealthy) + " unhealthy");
  row(174, "Uptime", uptime);
  row(197, "Wi-Fi", WiFi.status() == WL_CONNECTED ? String(WiFi.RSSI()) + " dBm" : String("--"));
  display.setTextColor(TFT_LIGHTGREY, TFT_BLACK);
  display.drawString("Hold BOOT 5s for Wi-Fi setup", 12, 221, 1);
}

Sample poll(bool connected) {
  Sample sample;
  if (!connected) {
    sample.health = {Mood::Offline, "Wi-Fi disconnected"};
    return sample;
  }
  Readings &data = sample.data;

  WiFiClient client;
  HTTPClient http;
  http.setConnectTimeout(1500);
  http.setTimeout(1500);
  JsonDocument doc;
  const bool valid = http.begin(client, statusUrl) && http.GET() == 200 &&
      http.getSize() > 0 && http.getSize() <= 4096 &&
      !deserializeJson(doc, http.getString()) && doc["sampled_at"].is<uint32_t>();
  http.end();

  if (valid) {
    data.cpu = reading(doc["cpu"], 100);
    data.temp = reading(doc["temp"], 150);
    data.ram = reading(doc["ram"], 100);
    data.root = reading(doc["disks"]["root"], 100);
    data.media = reading(doc["disks"]["media"], 100);
    const auto containers = doc["containers"];
    const int running = containers["running"] | -1;
    const int total = containers["total"] | -1;
    const int unhealthy = containers["unhealthy"] | -1;
    if (unhealthy >= 0 && unhealthy <= running && running <= total) {
      data.running = running;
      data.total = total;
      data.unhealthy = unhealthy;
    }
    if (doc["uptime"].is<uint32_t>()) {
      sample.uptimeMinutes = doc["uptime"].as<uint32_t>() / 60;
      sample.hasUptime = true;
    }
  }
  sample.health = assess(data, valid);
  return sample;
}

void sampleMetrics(void *) {
  bool connected;
  for (;;) {
    if (xQueueReceive(pollRequests, &connected, portMAX_DELAY) == pdTRUE) {
      const Sample sample = poll(connected);
      xQueueOverwrite(pollResults, &sample);
    }
  }
}

void drawPatrolMetrics() {
  display.fillRect(160, 34, 160, 206, TFT_BLACK);
  display.setTextColor(TFT_WHITE, TFT_BLACK);
  const auto &data = latest.data;
  display.drawString(latest.health.reason, 169, 57, 1);
  display.drawString("CPU " + metric(data.cpu) + " / " + metric(data.temp, " C"), 169, 79, 2);
  display.drawString("Memory " + metric(data.ram), 169, 101, 2);
  display.drawString("System disk " + metric(data.root), 169, 123, 2);
  display.drawString("Media disk " + metric(data.media), 169, 145, 2);
  display.drawString("Containers " + (data.total < 0 ? String("--") :
      String(data.running) + "/" + String(data.total)), 169, 167, 2);
  display.drawString(uptimeText(latest), 169, 189, 2);
}

void drawScene(displayLink::Scene scene, uint32_t elapsed, bool changed, bool updated) {
  constexpr uint16_t arena = 0x0842;
  const auto &frame = remote.frame;
  if (scene == displayLink::Fight) {
    const Opponent &opponent = OPPONENTS[frame.rank][frame.opponent];
    if (changed) {
      display.fillScreen(arena);
      display.setTextColor(TFT_WHITE, arena);
      display.drawString("SHELF GOBLIN", 12, 8, 2);
      display.drawFastHLine(12, 30, 296, TFT_ORANGE);
      display.drawCentreString(String(opponent.name) + "  L" + String(frame.rank + 1), 160, 181, 2);
    }
    sceneArt::monster(actor, opponent, frame.rank, elapsed, arena, frame.defeated && elapsed >= 3000);
    actor.pushSprite((display.width() - actor.width()) / 2, 61);
  } else {
    if (changed) {
      display.fillScreen(TFT_BLACK);
      display.setTextColor(TFT_WHITE, TFT_BLACK);
      display.drawString("M920Q HOMELAB", 12, 8, 2);
      display.drawFastHLine(12, 30, 296, TFT_GREEN);
      display.drawCentreString("On patrol", 80, 181, 2);
    }
    if (changed || updated) drawPatrolMetrics();
    const int actorEdge = max(0, 160 + frame.patrolX);
    if (actorEdge < 160) display.fillRect(actorEdge, 61, 160 - actorEdge, 110, TFT_BLACK);
    if (actorEdge > 0) {
      const bool walking = elapsed < displayLink::walkMs || elapsed >= displayLink::patrolMs - displayLink::walkMs;
      sceneArt::patrol(actor, static_cast<Form>(frame.form), TFT_BLACK, elapsed, walking);
      actor.pushSprite(frame.patrolX, 61);
    }
  }
}
}

void setup() {
  Serial.begin(115200);
  pinMode(bootPin, INPUT_PULLUP);
  display.init();
  display.setRotation(1);
  pinMode(TFT_BL, OUTPUT);
  digitalWrite(TFT_BL, TFT_BACKLIGHT_ON);
  render({}, {Mood::Offline, "Connecting to Wi-Fi"}, "--");
  WiFi.mode(WIFI_STA);
  WiFi.setAutoReconnect(true);
  wifi.setConnectTimeout(8);
  wifi.setConfigPortalBlocking(false);
  wifi.setDebugOutput(false);
  wifi.setAPCallback([](WiFiManager *) {
    display.fillScreen(TFT_BLACK);
    display.setTextColor(TFT_WHITE, TFT_BLACK);
    display.drawString("Join M920-Display on your phone or PC", 12, 35, 2);
    display.drawString("Open http://192.168.4.1", 12, 59, 2);
  });
  wifi.autoConnect(setupNetwork);
  WiFi.setSleep(false);
  actor.setColorDepth(16);
  actorReady = actor.createSprite(160, 110) != nullptr;
  if (actorReady) displayLink::begin(displayLink::waveshareMac);
  pollRequests = xQueueCreate(1, sizeof(bool));
  pollResults = xQueueCreate(1, sizeof(Sample));
  if (pollRequests && pollResults &&
      xTaskCreate(sampleMetrics, "metrics", 8192, nullptr, 1, nullptr) != pdPASS) {
    pollRequests = nullptr;
  }
  lastPoll = millis() - refreshMs;
}

void loop() {
  wifi.process();
  const uint32_t now = millis();
  if (digitalRead(bootPin) == LOW) {
    if (!pressing) pressedAt = now;
    pressing = true;
    if (!setupRequested && now - pressedAt >= 5000) {
      setupRequested = true;
      if (!wifi.getConfigPortalActive()) wifi.startConfigPortal(setupNetwork);
    }
  } else {
    pressing = false;
    setupRequested = false;
  }

  const bool portalActive = wifi.getConfigPortalActive();
  const bool connected = WiFi.status() == WL_CONNECTED;
  if (!portalActive) {
    bool updated = false;
    if (portalWasActive || connected != wasConnected || now - lastPoll >= refreshMs) {
      lastPoll = now;
      if (pollRequests && pollResults) xQueueOverwrite(pollRequests, &connected);
      else {
        latest = poll(connected);
        updated = true;
      }
    }
    displayLink::send({}, now, 125);
    displayLink::Received packet;
    if (displayLink::read(packet)) remote = packet;
    const uint32_t packetAge = millis() - remote.at;
    const uint32_t elapsed = remote.frame.elapsed + packetAge;
    auto scene = displayLink::Idle;
    if (actorReady && remote.at && packetAge < displayLink::timeoutMs &&
        ((remote.frame.scene == displayLink::Fight && elapsed < displayLink::fightMs) ||
         (remote.frame.scene == displayLink::Patrol && elapsed < displayLink::patrolMs))) {
      scene = remote.frame.scene;
    }
    if (pollResults && xQueueReceive(pollResults, &latest, 0) == pdTRUE) updated = true;
    const bool changed = scene != drawnScene || portalWasActive;
    if (scene == displayLink::Idle) {
      if (changed || updated || connected != wasConnected) {
        render(latest.data, latest.health, uptimeText(latest));
      }
    } else if (changed || updated || now - lastAnimation >= 65) {
      drawScene(scene, elapsed, changed, updated);
      lastAnimation = now;
    }
    drawnScene = scene;
  } else {
    remote = {};
  }
  portalWasActive = portalActive;
  wasConnected = connected;
  delay(20);
}
