#include <Arduino.h>
#include <ArduinoOTA.h>
#include <WiFi.h>
#include <WiFiManager.h>
#include <TFT_eSPI.h>
#include <Preferences.h>
#include "ant_levels.h"
uint32_t antLevelAnnouncement = 0;
#include "BatteryMonitor.h"
#include "../../cyd-ota/ota.h"
#include "../../esp32-monitor/src/evolution.h"
constexpr uint8_t guitionBacklightChannel = 0;
constexpr uint8_t guitionBacklightDuty = 102; // 40% of the 8-bit PWM range.
bool guitionBacklightPwm = false;

void setGuitionBacklight(bool on) {
  if (guitionBacklightPwm) ledcWrite(guitionBacklightChannel, on ? guitionBacklightDuty : 0);
  else digitalWrite(TFT_BL, on ? HIGH : LOW);
}

TFT_eSPI tft;
TFT_eSprite pet(&tft);
WiFiManager wifi;
Preferences storage;
Evolution evolution;
constexpr uint16_t bg = 0x0842, muted = 0x9CD3, accent = 0x4EBA;
uint32_t lastPoll = 0, lastFrame = 0, lastSave = 0;
bool spriteReady = false, storeReady = false;

const char *stage() {
  return antLevels[antLevelFor(evolution.healthMs) - 1].title;
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
  const size_t level = antLevelFor(evolution.healthMs);
  const int bob = (millis() / 500) % 2 ? 2 : 0;
  const int y = 60 + bob;
  const uint16_t shell[] = {0xB3A8, 0xBB48, 0xCB28, 0xCB8B, 0x9B4C, 0x7B50,
      0x6350, 0x6C26, 0xB4A6, 0xCD07, 0xDD8A};
  const uint16_t carapace = shell[level - 1];
  constexpr uint16_t edge = 0x2926;
  pet.fillRoundRect(0, 0, 160, 110, 7, 0x5288);
  pet.fillEllipse(96, 56, 69, 43, 0x6B08);
  pet.fillRoundRect(0, 73, 160, 37, 6, 0x8C4B);
  pet.fillEllipse(79, 91, 51, 7, 0x62E6);
  for (int leg = 0; leg < 3; ++leg) {
    const int x = 67 + leg * 10;
    pet.drawLine(x, y, x - 15, y + 11, edge);
    pet.drawLine(x - 15, y + 11, x - 20, y + 21, edge);
    pet.drawLine(x, y, x + 16, y + 10, edge);
    pet.drawLine(x + 16, y + 10, x + 22, y + 20 - bob, edge);
  }
  pet.fillEllipse(107, y - 2, 24, 18, edge);
  pet.fillEllipse(107, y - 2, 21, 15, carapace);
  pet.fillEllipse(78, y + 1, 15, 12, edge);
  pet.fillEllipse(78, y + 1, 12, 9, carapace);
  pet.drawLine(50, y - 14, 40, y - 32, edge);
  pet.drawLine(40, y - 32, 32, y - 35, edge);
  pet.drawLine(60, y - 14, 65, y - 33, edge);
  pet.drawLine(65, y - 33, 74, y - 36, edge);
  pet.fillEllipse(53, y - 5, 21, 18, edge);
  pet.fillEllipse(53, y - 5, 18, 15, carapace);
  const int eyeHeight = (millis() / 500) % 9 == 0 ? 1 : 4;
  pet.fillEllipse(46, y - 9, 3, eyeHeight, 0xFFF2);
  pet.fillEllipse(58, y - 9, 3, eyeHeight, 0xFFF2);
  if (level >= 5) {
    pet.fillRoundRect(27, y + 8, 12, 16, 3, edge);
    pet.fillRect(30, y + 12, 6, 8, level >= 9 ? 0xFDC5 : 0xB7E8);
  }
  if (level >= 9) {
    pet.drawFastHLine(41, y - 17, 25, 0xFEE8);
    pet.fillTriangle(47, y - 17, 53, y - 24, 59, y - 17, 0xFEE8);
  }
  pet.pushSprite(8, 61);
}
void render() {
  tft.fillRect(0, 0, tft.width(), tft.height(), bg);
  tft.setTextColor(accent, bg);
  tft.drawString("SHELF ANT", 10, 7, 2);
  tft.drawFastHLine(10, 30, tft.width() - 20, muted);
  drawPet();
  if (!spriteReady) {
    tft.setTextColor(accent, bg);
    tft.drawString("( ^ v ^ )", 30, 105, 2);
  }
  tft.setTextColor(TFT_WHITE, bg);
  const size_t petLevel = antLevelFor(evolution.healthMs);
  tft.drawString(stage(), 176, 67, 2);
  tft.setTextColor(accent, bg);
  tft.drawString("Level " + String(petLevel), 182, 91, 2);
  tft.drawRoundRect(182, 116, 113, 8, 3, muted);
  const unsigned progress = antLevelProgress(evolution.healthMs, petLevel);
  if (progress) tft.fillRect(184, 118, (109 * progress + 99) / 100, 4, accent);
  tft.setTextColor(TFT_WHITE, bg);
  tft.drawString(antLevels[petLevel - 1].skill, 182, 135, 2);
  tft.setTextColor(muted, bg);
  const bool announce = antLevelAnnouncement && millis() - antLevelAnnouncement < 15000;
  tft.drawCentreString(announce ? "Level up! Skill gained" : antLevels[petLevel - 1].quest,
                       tft.width() / 2, 179, 2);
  tft.setTextColor(accent, bg);
  const int level = battery::batteryPercent();
  const auto charge = battery::chargeState();
  String batteryStatus = level < 0 ? "Battery unavailable" : "Battery " + String(level) + "%";
  batteryStatus += charge == battery::ChargeState::Charging ? " / Charging" :
      charge == battery::ChargeState::Idle ? " / Not charging" : " / Charge unknown";
  tft.drawCentreString(batteryStatus, tft.width() / 2, 197, 1);
  const String network = WiFi.status() == WL_CONNECTED ?
      "Wi-Fi " + WiFi.localIP().toString() : "Hold BOOT 5s for Wi-Fi setup";
  tft.drawCentreString(network, tft.width() / 2, 217, 1);
}

void setup() {
  Serial.begin(115200);
  cydOta::configureOta();
  Serial.println("Shelf Ant / JC2432W328");
  battery::begin();
  pinMode(0, INPUT_PULLUP);
  pinMode(TFT_BL, OUTPUT);
  tft.init(); tft.setRotation(1);
  guitionBacklightPwm = ledcSetup(guitionBacklightChannel, 5000, 8) > 0;
  if (guitionBacklightPwm) ledcAttachPin(TFT_BL, guitionBacklightChannel);
  setGuitionBacklight(true);
  pet.setColorDepth(16);
  spriteReady = pet.createSprite(160, 110) != nullptr;
  storeReady = storage.begin("shelf-ant", false);
  // Keep the existing evolution bank; retired care meters are no longer read.
  evolution = Evolution(storeReady ? storage.getUInt("health-v1", 0) : 0);
  WiFi.mode(WIFI_STA);
  WiFi.setAutoReconnect(true);
  WiFi.begin();
  wifi.setConfigPortalBlocking(false);
  wifi.setConfigPortalTimeout(180);
  wifi.setDebugOutput(false);
  render();
}
void loop() {
  wifi.process();
  const bool portalActive = wifi.getConfigPortalActive();
  cydOta::serviceOta(WiFi.status() == WL_CONNECTED, portalActive);
  const uint32_t now = millis();
  static bool portalWasActive = false;
  static uint32_t pressedAt = 0;
  static int64_t observation = 0;
  static uint32_t lastWake = now;
  static uint32_t buttonChanged = now;
  static bool sampledDown = false, stableDown = false, screenOn = true;
  const bool down = digitalRead(0) == LOW;
  if (down != sampledDown) {
    sampledDown = down;
    buttonChanged = now;
  }
  if (sampledDown != stableDown && now - buttonChanged >= 40) {
    stableDown = sampledDown;
    if (stableDown) {
      pressedAt = now;
    } else if (now - pressedAt >= 5000) {
      if (!portalActive) {
        setGuitionBacklight(true);
        screenOn = true;
        wifi.startConfigPortal("Shelf-Ant-Setup");
        tft.fillScreen(bg);
        tft.setTextColor(TFT_WHITE, bg);
        tft.drawString("Join Shelf-Ant-Setup", 10, 65, 2);
        tft.drawString("Open 192.168.4.1 to set up Wi-Fi", 10, 95, 2);
      }
    } else if (!portalActive) {
      screenOn = !screenOn;
      if (screenOn) {
        lastWake = now;
        lastFrame = now;
        render();
      }
      setGuitionBacklight(screenOn);
    }
  }
  if (portalWasActive && !portalActive && screenOn) render();
  portalWasActive = portalActive;
  if (now - lastPoll >= 5000) {
    const size_t previousLevel = antLevelFor(evolution.healthMs);
    evolution = evolution.observed(Mood::Healthy, now, ++observation);
    if (antLevelFor(evolution.healthMs) != previousLevel) {
      antLevelAnnouncement = now;
      saveEvolution();
    }
    lastPoll = now;
    if (screenOn && !wifi.getConfigPortalActive()) render();
    lastFrame = now;
  } else if (screenOn && !wifi.getConfigPortalActive() && now - lastFrame >= (now - lastWake < 15000 ? 500U : 1250U)) {
    drawPet();
    lastFrame = now;
  }
  if (now - lastSave >= 300000) saveEvolution();
  delay(20);
}
