#include <Arduino.h>
#include <ArduinoOTA.h>
#include <WiFi.h>
#include <WiFiManager.h>
#include <TFT_eSPI.h>
#include <Preferences.h>
#include "pet_levels.h"
#include "BatteryMonitor.h"
#include "../../cyd-ota/ota.h"
#include "../game.h"
#include "../../esp32-monitor/src/scene_art.h"
#include "../../esp32-monitor/src/virtual_pet.h"
#ifdef CYD_PET_CAT
constexpr char petTitle[] = "SHELF CAT";
constexpr char petNamespace[] = "shelf-cat";
constexpr char setupNetwork[] = "Shelf-Cat-Setup";
constexpr auto &opponents = virtualPet::catStages;
#else
constexpr char petTitle[] = "SHELF ANT";
constexpr char petNamespace[] = "shelf-ant";
constexpr char setupNetwork[] = "Shelf-Ant-Setup";
constexpr auto &opponents = virtualPet::antStages;
#endif

static_assert(maxLevel == virtualPet::formCount, "Every pet level needs an opponent");
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
uint32_t xp = 0;
cydPet::Battle battle;
cydPet::IdleProgress idleProgress;
String battleReport;
constexpr uint16_t bg = 0x0842, muted = 0x9CD3, accent = 0x4EBA;
uint32_t lastPoll = 0, lastFrame = 0;
bool spriteReady = false, storeReady = false;

void saveXp(uint32_t value) {
  if (value == xp) return;
  xp = value;
  if (storeReady) storage.putUInt("xp-v1", xp);
}

void drawPet(int x = 8) {
  if (!spriteReady) return;
  pet.fillSprite(bg);
  const size_t level = virtualPet::rankFor(xp) + 1;
#ifdef CYD_PET_CAT
  const bool kitten = level < 5;
  const bool elder = level >= 9;
  const int bob = (millis() / 500) % 2 ? 2 : 0;
  const int y = (kitten ? 45 : 40) + bob;
  const int headY = y - 10;
  const uint16_t sky = elder ? 0xB4BC : kitten ? 0xAEBF : 0x85BF;
  const uint16_t hill = elder ? 0x858C : kitten ? 0x8EA9 : 0x5D8B;
  const uint16_t grass = elder ? 0x6590 : kitten ? 0x9EED : 0x7E2A;
  pet.fillRoundRect(0, 0, 160, 110, 7, sky);
  pet.fillCircle(128, 19, 10, elder ? 0xFF7A : 0xFFE7);
  pet.fillEllipse(33, 23, 17, 5, 0xF79E);
  pet.fillCircle(31, 19, 6, 0xF79E);
  pet.fillEllipse(1, 75, 72, 27, hill);
  pet.fillEllipse(151, 72, 70, 27, hill);
  pet.fillRoundRect(0, 67, 160, 43, 7, grass);
  pet.fillEllipse(78, 91, 65, 12, 0xD6B0);
  pet.fillRect(12, 58, 4, 17, 0x9308);
  pet.fillCircle(14, 53, 12, 0x3D28);
  pet.fillCircle(12, 49, 7, 0x6E4C);
  pet.fillCircle(148, 79, 2, 0xFBD8);
  pet.fillCircle(143, 82, 2, 0xFF3A);
  if (elder) {
    pet.drawFastHLine(19, 22, 5, 0xDEFB);
    pet.drawFastVLine(21, 20, 5, 0xDEFB);
    pet.drawFastHLine(95, 14, 5, 0xDEFB);
    pet.drawFastVLine(97, 12, 5, 0xDEFB);
  }
  pet.fillEllipse(80, 96, 43, 5, 0xA4C9);
  constexpr uint16_t outline = 0x18C4;
  constexpr uint16_t grayFur = 0x9CF3;
  constexpr uint16_t darkFur = 0x3186;
  constexpr uint16_t lightFur = 0xBDF7;
  constexpr uint16_t armor = 0x432F;
  constexpr uint16_t armorLight = 0x95B9;
  // Overlapping ellipses keep the curled tail continuous at both bob heights.
  const int tailTip = 5 - bob;
  pet.fillEllipse(119, y + 27, 23, 9, outline);
  pet.fillEllipse(135, y + 18, 10, 15, outline);
  pet.fillEllipse(130, y + tailTip, 12, 8, outline);
  pet.fillEllipse(119, y + 27, 20, 6, darkFur);
  pet.fillEllipse(135, y + 18, 7, 12, darkFur);
  pet.fillEllipse(130, y + tailTip, 9, 5, darkFur);
  pet.fillEllipse(124, y + tailTip, 4, 4, lightFur);
  pet.fillRoundRect(59, y + 16, 42, 26, 8, outline);
  pet.fillRoundRect(50, y + 21, 13, 21, 6, outline);
  pet.fillRoundRect(97, y + 21, 13, 21, 6, outline);
  pet.fillRoundRect(55, y + 36, 21, 16, 5, outline);
  pet.fillRoundRect(84, y + 36, 21, 16, 5, outline);
  pet.fillTriangle(40, headY + 5, 45, headY - 27, 72, headY - 6, outline);
  pet.fillTriangle(88, headY - 6, 115, headY - 27, 120, headY + 5, outline);
  pet.fillRoundRect(39, headY - 14, 82, 49, 11, outline);
  for (int half = 0; half < 2; ++half) {
    const uint16_t fur = half == 0 ? grayFur : darkFur;
    pet.setViewport(half * 80, 0, 80, 110, false);
    pet.fillRoundRect(61, y + 18, 38, 22, 6, fur);
    pet.fillRoundRect(52, y + 23, 9, 17, 4, fur);
    pet.fillRoundRect(99, y + 23, 9, 17, 4, fur);
    pet.fillRoundRect(57, y + 38, 17, 12, 3, fur);
    pet.fillRoundRect(86, y + 38, 17, 12, 3, fur);
    pet.fillTriangle(43, headY + 4, 47, headY - 22, 69, headY - 6, fur);
    pet.fillTriangle(91, headY - 6, 113, headY - 22, 117, headY + 4, fur);
    pet.fillRoundRect(42, headY - 12, 76, 45, 9, fur);
  }
  pet.resetViewport();
  pet.fillRoundRect(62, y + 27, 36, 14, 5, outline);
  pet.fillRoundRect(64, y + 28, 32, 11, 4, armor);
  pet.drawFastHLine(68, y + 35, 24, armorLight);
  pet.fillRoundRect(49, y + 23, 14, 9, 4, outline);
  pet.fillRoundRect(97, y + 23, 14, 9, 4, outline);
  pet.fillRoundRect(51, y + 24, 10, 5, 2, armorLight);
  pet.fillRoundRect(99, y + 24, 10, 5, 2, armorLight);
  const uint16_t scarf = elder ? 0x921E : kitten ? 0xE986 : 0x14DC;
  pet.fillRoundRect(54, y + 24, 52, 10, 4, outline);
  pet.fillRoundRect(56, y + 25, 48, 6, 2, scarf);
  pet.fillTriangle(57, y + 28, 68, y + 28, 52, y + 40, scarf);
  pet.fillCircle(66, y + 29, 2, 0xFEC9);
  if (!kitten) {
    pet.drawRoundRect(117, y + 34, 13, 17, 2, 0xDE6F);
    pet.fillRect(120, y + 38, 7, 9, elder ? 0xAFFF : 0xFDC9);
    pet.drawFastHLine(120, y + 31, 7, 0xDE6F);
  }
  switch (level) {
    case 2: // Moth charm
      pet.fillEllipse(78, y + 37, 3, 2, 0xFFF1);
      pet.fillEllipse(84, y + 37, 3, 2, 0xFFF1);
      break;
    case 3: // Creek boots
      pet.fillRoundRect(56, y + 42, 19, 9, 2, 0x24B5);
      pet.fillRoundRect(85, y + 42, 19, 9, 2, 0x24B5);
      break;
    case 4: // Forager's satchel
      pet.fillRoundRect(101, y + 27, 18, 16, 4, 0xAAE5);
      pet.drawFastHLine(104, y + 33, 12, 0xFEB3);
      break;
    case 6: // Mist cloak
      pet.fillTriangle(48, y + 24, 32, y + 49, 64, y + 43, 0x73B8);
      break;
    case 7: // Bridge shield
      pet.fillRoundRect(38, y + 28, 20, 19, 5, 0x326F);
      pet.drawRoundRect(38, y + 28, 20, 19, 5, 0xDEFB);
      pet.drawFastVLine(47, y + 32, 10, 0xDEFB);
      break;
    case 8: // Map case and rolled chart
      pet.fillRoundRect(36, y + 33, 25, 9, 3, 0xDEAA);
      pet.drawFastVLine(41, y + 34, 7, 0xA2C4);
      pet.drawFastVLine(54, y + 34, 7, 0xA2C4);
      break;
    case 9: // Star brooch
      pet.drawFastHLine(75, y + 29, 11, 0xAFFE);
      pet.drawFastVLine(80, y + 25, 9, 0xAFFE);
      break;
    case 10: // Dawn mantle
      pet.fillTriangle(48, y + 24, 27, y + 49, 65, y + 44, 0xB426);
      pet.drawLine(27, y + 49, 65, y + 44, 0xF6C9);
      break;
    case 11: // Hearth circlet
      pet.drawFastHLine(64, headY - 5, 32, 0xF6C9);
      pet.fillTriangle(74, headY - 5, 80, headY - 13, 86, headY - 5, 0xF6C9);
      pet.fillCircle(80, headY - 7, 2, 0xF9A6);
      break;
  }
  pet.fillTriangle(52, headY - 3, 53, headY - 14, 64, headY - 5, 0xFBB5);
  pet.fillTriangle(96, headY - 5, 107, headY - 14, 108, headY - 3, 0xFBB5);
  const bool blink = (millis() / 500) % 9 == 0;
  const int eyeHeight = blink ? 2 : kitten ? 11 : 8;
  pet.fillRoundRect(60, headY + 4, 8, eyeHeight, 2, 0xF6A8);
  pet.fillRoundRect(92, headY + 4, 8, eyeHeight, 2, 0xF6A8);
  if (!blink) {
    pet.fillRect(63, headY + 5, 2, eyeHeight - 2, TFT_BLACK);
    pet.fillRect(95, headY + 5, 2, eyeHeight - 2, TFT_BLACK);
  }
  pet.fillEllipse(52, headY + 20, 4, 2, 0xD3B1);
  pet.fillEllipse(108, headY + 20, 4, 2, 0xD3B1);
  if (elder) {
    pet.drawLine(58, headY + 1, 68, headY, 0xDEDB);
    pet.drawLine(92, headY, 102, headY + 1, 0xDEDB);
  }
  const int muzzleRadius = elder ? 10 : 8;
  pet.fillEllipse(74, headY + 22, muzzleRadius, 6, lightFur);
  pet.fillEllipse(86, headY + 22, muzzleRadius, 6, lightFur);
  pet.fillTriangle(75, headY + 16, 85, headY + 16, 80, headY + 21, 0xC38E);
  pet.drawFastVLine(80, headY + 21, 4, outline);
  pet.drawLine(80, headY + 24, 76, headY + 25, outline);
  pet.drawLine(80, headY + 24, 84, headY + 25, outline);
  pet.drawLine(43, headY + 15, 59, headY + 18, 0x4208);
  pet.drawLine(43, headY + 23, 59, headY + 22, 0x4208);
  pet.drawLine(101, headY + 18, 117, headY + 15, 0xA514);
  pet.drawLine(101, headY + 22, 117, headY + 23, 0xA514);
#else
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
#endif
  pet.pushSprite(x, 61);
}
void render() {
  tft.fillRect(0, 0, tft.width(), tft.height(), bg);
  tft.setTextColor(accent, bg);
  tft.drawString(petTitle, 10, 7, 2);
  tft.drawFastHLine(10, 30, tft.width() - 20, muted);
  drawPet();
  if (!spriteReady) {
    tft.setTextColor(accent, bg);
    tft.drawString("( ^ v ^ )", 30, 105, 2);
  }
  tft.setTextColor(TFT_WHITE, bg);
  const unsigned rank = virtualPet::rankFor(xp);
  const auto &levelInfo = levels[rank];
  tft.drawString(levelInfo.title, 176, 67, 2);
  tft.setTextColor(accent, bg);
  tft.drawString("Level " + String(rank + 1), 182, 91, 2);
  const String progress = rank + 1 == maxLevel ? "Max level" :
      String(xp) + " / " + String(virtualPet::threshold(rank + 1)) + " XP";
  tft.drawString(progress, 176, 114, 2);
  tft.setTextColor(TFT_WHITE, bg);
  tft.drawString(levelInfo.skill, 182, 135, 2);
  tft.setTextColor(muted, bg);
  tft.drawCentreString(battleReport.isEmpty() ? levelInfo.quest : battleReport.c_str(),
                       tft.width() / 2, 179, 2);
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
  tft.drawCentreString("BOOT: fight  |  Hold 1s: screen  |  Hold 5s: Wi-Fi",
                       tft.width() / 2, 217, 1);
}

void startBattle(uint32_t now) {
  battle.start(virtualPet::rankFor(xp), maxLevel, now, [](unsigned rank) -> const Opponent & {
    return opponents[rank].opponent;
  });
  tft.fillScreen(bg);
  tft.setTextColor(TFT_WHITE, bg);
  tft.drawString(petTitle, 10, 7, 2);
  tft.drawFastHLine(10, 30, tft.width() - 20, TFT_ORANGE);
  tft.drawCentreString(String(battle.opponent->name) + "  L" + String(battle.foeRank + 1), 240, 180, 2);
  tft.drawCentreString("Battle in progress", 160, 222, 1);
}

void drawBattle(uint32_t now) {
  if (!spriteReady) return;
  drawPet(0);
  sceneArt::monster(pet, *battle.opponent, battle.foeRank, now - battle.started, bg, false);
  pet.pushSprite(160, 61);
}

void finishBattle() {
  const uint32_t next = battle.resultXp(xp, virtualPet::finalXp);
  battleReport = battle.won ? "Victory  +" + String(next - xp) + " XP" :
      "Defeat  -" + String(xp - next) + " XP";
  saveXp(next);
  battle = {};
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
  storeReady = storage.begin(petNamespace, false);
  if (storeReady) {
    if (storage.isKey("xp-v1")) {
      xp = addXp(storage.getUInt("xp-v1", 0), 0, virtualPet::finalXp);
    } else {
      const uint32_t journey = storage.getUInt("health-v1", 0);
      const unsigned level = levelFor(journey);
      const uint32_t base = virtualPet::threshold(level - 1);
      const uint32_t span = level == maxLevel ? 0 : virtualPet::threshold(level) - base;
      xp = base + span * levelProgress(journey, level) / 100;
      storage.putUInt("xp-v1", xp);
    }
  }
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
        wifi.startConfigPortal(setupNetwork);
        tft.fillScreen(bg);
        tft.setTextColor(TFT_WHITE, bg);
        tft.drawString(String("Join ") + setupNetwork, 10, 65, 2);
        tft.drawString("Open 192.168.4.1 to set up Wi-Fi", 10, 95, 2);
      }
    } else if (!portalActive && !battle.opponent) {
      const bool hold = now - pressedAt >= 1000;
      if (hold || !screenOn) {
        screenOn = !screenOn;
        setGuitionBacklight(screenOn);
        if (screenOn) {
          lastWake = now;
          lastFrame = now;
          render();
        }
      } else {
        startBattle(now);
        drawBattle(now);
        lastFrame = now;
      }
    }
  }

  const bool viewingPet = screenOn && !wifi.getConfigPortalActive() && !battle.opponent;
  const uint32_t reward = idleProgress.reward(now, viewingPet);
  if (reward) saveXp(addXp(xp, reward, virtualPet::finalXp));
  if (battle.opponent && !wifi.getConfigPortalActive()) {
    if (now - battle.started >= cydPet::battleDurationMs || portalWasActive) {
      finishBattle();
      render();
      lastFrame = now;
    } else if (now - lastFrame >= 65) {
      drawBattle(now);
      lastFrame = now;
    }
  } else if (viewingPet) {
    if (portalWasActive || reward || now - lastPoll >= 5000) {
      render();
      lastPoll = lastFrame = now;
    } else if (now - lastFrame >= (now - lastWake < 15000 ? 500U : 1250U)) {
      drawPet();
      lastFrame = now;
    }
  }
  portalWasActive = wifi.getConfigPortalActive();
  delay(20);
}
