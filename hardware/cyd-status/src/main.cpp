#include <Arduino.h>
#include <ArduinoJson.h>
#include <HTTPClient.h>
#include <TFT_eSPI.h>
#include <WiFiManager.h>

#include "../../esp32-monitor/src/health.h"

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

void poll(bool connected) {
  Readings data;
  if (!connected) {
    render(data, {Mood::Offline, "Wi-Fi disconnected"}, "--");
    return;
  }

  WiFiClient client;
  HTTPClient http;
  http.setConnectTimeout(1500);
  http.setTimeout(1500);
  JsonDocument doc;
  const bool valid = http.begin(client, statusUrl) && http.GET() == 200 &&
      http.getSize() > 0 && http.getSize() <= 4096 &&
      !deserializeJson(doc, http.getString()) && doc["sampled_at"].is<uint32_t>();
  http.end();

  String uptime = "--";
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
      const uint32_t minutes = doc["uptime"].as<uint32_t>() / 60;
      uptime = String(minutes / 1440) + "d " + String(minutes / 60 % 24) + "h " +
          String(minutes % 60) + "m";
    }
  }
  render(data, assess(data, valid), uptime);
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
  if (!portalActive && (portalWasActive || connected != wasConnected || now - lastPoll >= refreshMs)) {
    lastPoll = now;
    poll(connected);
  }
  portalWasActive = portalActive;
  wasConnected = connected;
  delay(20);
}
