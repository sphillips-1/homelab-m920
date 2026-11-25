#include <Arduino.h>
#include <ArduinoOTA.h>
#include <WiFi.h>
#include <WiFiManager.h>
#include <TFT_eSPI.h>
#include <Preferences.h>
#include "BatteryMonitor.h"
#include "../../cyd-ota/ota.h"
#ifdef CYD_PET_CAT
constexpr char petTitle[] = "SHELF CAT";
constexpr char setupNetwork[] = "Shelf-Cat-Setup";
#else
constexpr char petTitle[] = "SHELF ANT";
constexpr char setupNetwork[] = "Shelf-Ant-Setup";
#endif

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
constexpr uint16_t bg = 0x0842, muted = 0x9CD3, accent = 0x4EBA;
uint32_t lastPoll = 0;
bool spriteReady = false;

int drawnEggOffset = 0;

int eggOffset(uint32_t now) {
  constexpr uint32_t twitchInterval = 11000;
  constexpr uint32_t twitchStep = 90;
  const uint32_t phase = now % twitchInterval;
  if (now < twitchInterval || phase >= 3 * twitchStep) return 0;
  return phase < twitchStep || phase >= 2 * twitchStep ? -3 : 3;
}

void drawEgg() {
  if (!spriteReady) return;
  pet.fillSprite(bg);
  drawnEggOffset = eggOffset(millis());
  const int x = 80 + drawnEggOffset;
  pet.fillEllipse(80, 90, 31, 5, 0x18C3);
  pet.fillEllipse(x, 56, 26, 32, 0x8BAC);
  pet.fillEllipse(x, 55, 23, 30, 0xF6D6);
  pet.fillEllipse(x, 44, 19, 22, 0xF6D6);
  pet.fillEllipse(x - 9, 41, 5, 9, 0xFFBD);
  pet.fillCircle(x + 11, 61, 3, 0xC58F);
  pet.fillCircle(x + 4, 71, 2, 0xC58F);
  pet.pushSprite((tft.width() - 160) / 2, 61);
}
void render() {
  tft.fillRect(0, 0, tft.width(), tft.height(), bg);
  tft.setTextColor(accent, bg);
  tft.drawString("unknown", 10, 7, 2);
  tft.drawFastHLine(10, 30, tft.width() - 20, muted);
  drawEgg();
  if (!spriteReady) {
    tft.setTextColor(accent, bg);
    tft.drawCentreString("Egg", tft.width() / 2, 105, 2);
  }
  tft.setTextColor(accent, bg);
  const int level = battery::batteryPercent();
  const auto charge = battery::chargeState();
  String batteryStatus = level < 0 ? "Battery unavailable" : "Battery " + String(level) + "%";
  batteryStatus += charge == battery::ChargeState::Charging ? " / Charging" :
      charge == battery::ChargeState::Idle ? " / Not charging" : " / Charge unknown";
  tft.drawCentreString(batteryStatus, tft.width() / 2, 197, 1);
  if (WiFi.status() == WL_CONNECTED) {
    tft.drawRightString(WiFi.localIP().toString(), 309, 13, 1);
  }
  tft.drawCentreString("BOOT: screen  |  Hold 5s: Wi-Fi",
                       tft.width() / 2, 217, 1);
}

void setup() {
  Serial.begin(115200);
  cydOta::configureOta(true);
  Serial.printf("%s / JC2432W328\n", petTitle);
  battery::begin();
  pinMode(0, INPUT_PULLUP);
  pinMode(TFT_BL, OUTPUT);
  tft.init(); tft.setRotation(1);
  guitionBacklightPwm = ledcSetup(guitionBacklightChannel, 5000, 8) > 0;
  if (guitionBacklightPwm) ledcAttachPin(TFT_BL, guitionBacklightChannel);
  setGuitionBacklight(true);
  pet.setColorDepth(16);
  spriteReady = pet.createSprite(160, 110) != nullptr;
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
  static bool reportedAddress = false;
  if (!reportedAddress && WiFi.status() == WL_CONNECTED) {
    Serial.println("CYD Wi-Fi connected: " + WiFi.localIP().toString());
    reportedAddress = true;
  }
  const bool portalActive = wifi.getConfigPortalActive();
  cydOta::serviceOta(WiFi.status() == WL_CONNECTED, portalActive);
  const uint32_t now = millis();
  static bool portalWasActive = false;
  static uint32_t pressedAt = 0;
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
        wifi.startConfigPortal(setupNetwork);
        tft.fillScreen(bg);
        tft.setTextColor(TFT_WHITE, bg);
        tft.drawString(String("Join ") + setupNetwork, 10, 65, 2);
        tft.drawString("Open 192.168.4.1 to set up Wi-Fi", 10, 95, 2);
      }
    } else if (!portalActive) {
      screenOn = !screenOn;
      if (screenOn) render();
      setGuitionBacklight(screenOn);
    }
  }

  if (screenOn && !wifi.getConfigPortalActive()) {
    if (portalWasActive || now - lastPoll >= 5000) {
      render();
      lastPoll = now;
    } else if (spriteReady && eggOffset(now) != drawnEggOffset) {
      drawEgg();
    }
  }
  portalWasActive = wifi.getConfigPortalActive();
  delay(20);
}
