#include <Arduino.h>
#include <TFT_eSPI.h>
#include <Preferences.h>
#include <SPI.h>
#ifdef SHELF_GOBLIN_WAVESHARE
#include <atomic>
#include "waveshare_touch.h"
#include "waveshare_orientation.h"
#include "experience.h"
#else
#include <WiFi.h>
#include <HTTPClient.h>
#include <WiFiManager.h>
#include <ArduinoJson.h>
#include <XPT2046_Touchscreen.h>
#endif
#include <freertos/FreeRTOS.h>
#include <freertos/queue.h>
#include <math.h>
#include <esp_system.h>
#include "health.h"
#include "evolution.h"
#include "combat.h"
#include "scene_art.h"
#if defined(SHELF_PET_ANT) || defined(SHELF_PET_CAT)
#define SHELF_VIRTUAL_PET
using PetForm = unsigned;
constexpr PetForm starterForm = 0;
#else
using PetForm = Form;
constexpr PetForm starterForm = Form::Baby;
#endif
#ifdef SHELF_GOBLIN_WAVESHARE
#include <WiFi.h>
#include "camp_link.h"
#include "cyd_camp.h"
#include "pet_visits.h"
#include "virtual_pet_art.h"
#endif
#if defined(SHELF_GOBLIN_WAVESHARE) && !defined(SHELF_VIRTUAL_PET)
#include "display_link.h"
#endif
#include "touch_controls.h"

TFT_eSPI tft;
TFT_eSprite pet(&tft);
Preferences storage;
#ifdef SHELF_GOBLIN_WAVESHARE
constexpr int nativeWidth = waveshareOrientation::nativeWidth;
constexpr int nativeHeight = waveshareOrientation::nativeHeight;
int screenWidth = nativeWidth, screenHeight = nativeHeight, screenRotation = 0;
bool orientationReady = false;
std::atomic<int> pendingRotation{waveshareOrientation::noRotation};
std::atomic<bool> touchInProgress{false};
constexpr char calibrationKey[] = "touch-portrait";
uint32_t experience = 0;
uint32_t idleStartedAt = 0;
bool visitMenu = false;
void receivePeerPacket(const uint8_t *mac, const uint8_t *bytes, int length) {
  petVisits::receive(mac, bytes, length);
  cydCamp::receive(mac, bytes, length);
}
#ifdef SHELF_VIRTUAL_PET
constexpr uint32_t experienceCap = virtualPet::finalXp;
unsigned bestForm = 0;
bool revealing = false;
uint32_t revealAt = 0;
PetForm currentForm() { return virtualPet::rankFor(experience); }
#else
constexpr uint32_t experienceCap = MAX_XP;
uint32_t lastCyd = 0;
uint32_t patrolAt = 0, nextPatrol = 0;
bool patrolling = false, linkedFight = false;
Form patrolForm = Form::Baby;

bool cydAvailable(uint32_t now) {
  return lastCyd && now - lastCyd < displayLink::timeoutMs;
}

void schedulePatrol(uint32_t now) {
  nextPatrol = now + 180000 + esp_random() % 240001;
}

void findCyd() {
  displayLink::Received packet;
  if (displayLink::read(packet)) lastCyd = packet.at;
}
Form currentForm() { return formForXp(experience); }
#endif
#else
constexpr int screenWidth = 320, screenHeight = 240, screenRotation = 1;
constexpr char calibrationKey[] = "touch-v1";
constexpr char setupNetwork[] = "M920-Display";
WiFiManager wifi;
SPIClass touchBus(VSPI);
XPT2046_Touchscreen touchscreen(33, 36);
#endif
int screenCenter() { return screenWidth / 2; }
bool portrait() { return screenHeight > screenWidth; }
int petOffset() { return portrait() ? screenCenter() - 88 : 0; }
QueueHandle_t touchEvents = nullptr;
#ifndef SHELF_GOBLIN_WAVESHARE
volatile bool touchDown = false;
#endif
bool touchReady = false, calibrationActive = false, calibrated = false;
int calibrationStep = 0;
TouchCalibration calibration{}, candidate{};
TouchPoint calibrationRaw[3];
const char *calibrationHint = "Tap the target, then lift your finger";
#ifndef SHELF_GOBLIN_WAVESHARE
Readings readings;
Evolution evolution;
Form currentForm() { return formFor(evolution.healthMs); }
const char *newClass = nullptr;
uint32_t classObtainedAt = 0;
#endif
String fightReport;
const Opponent *fightOpponent = nullptr;
bool showDefeat = false;
PetForm fightForm = starterForm;
unsigned fightOpponentRank = 0;
uint32_t fightAt = 0;
uint32_t lastBattleFrame = 0;
struct FightButton {
  int x, y, width, height;
};
FightButton fightButton() {
#ifdef SHELF_GOBLIN_WAVESHARE
  return {screenCenter() - 108, screenHeight - 41, 114, 28};
#else
  return {175, 198, 135, 34};
#endif
}
#ifdef SHELF_GOBLIN_WAVESHARE
FightButton visitButton() { return {screenCenter() + 12, screenHeight - 41, 96, 28}; }
FightButton visitChoice(unsigned row) { return {screenCenter() - 80, 63 + 42 * static_cast<int>(row), 160, 34}; }
#endif
#if defined(SHELF_GOBLIN_WAVESHARE) && !defined(SHELF_VIRTUAL_PET)
constexpr uint32_t FIGHT_ANIMATION_MS = displayLink::fightMs;
#else
constexpr uint32_t FIGHT_ANIMATION_MS = 3600;
#endif
constexpr uint32_t DEFEAT_SCREEN_MS = 2000;
constexpr uint32_t FIGHT_REPORT_MS = 5000;
const uint16_t bg = 0x0842, muted = 0x9CD3, accent = 0x4EBA;
uint32_t pressed = 0, lastFrame = 0;
bool spriteReady = false, dirty = true, storeReady = false;
#ifndef SHELF_GOBLIN_WAVESHARE
Health health{Mood::Offline, "Waiting for metrics"};
uint32_t lastPoll = 0, lastGood = 0;
uint32_t lastSave = 0;
unsigned long hostUptime = 0;
bool hasData = false, online = false, longHandled = false;
int page = 0; // 0: goblin, 1: metrics.
#endif

// This task owns touch sampling and the Waveshare I2C bus after setup.
void sampleTouch(void *) {
  uint32_t started = 0, sumX = 0, sumY = 0;
  unsigned int count = 0, released = 0;
  TouchPoint first{}, last{};
  int maxMotion = 0;
  for (;;) {
    TouchPoint p{};
#ifdef SHELF_GOBLIN_WAVESHARE
    const bool down = touchReady && waveshareTouch::read(p);
#else
    const bool down = touchscreen.touched();
    if (down) {
      const TS_Point point = touchscreen.getPoint();
      p = {point.x, point.y};
    }
#endif
#ifndef SHELF_GOBLIN_WAVESHARE
    touchDown = down;
#endif
    if (down) {
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
#ifdef SHELF_GOBLIN_WAVESHARE
    touchInProgress.store(count != 0);
    if (orientationReady) pendingRotation.store(waveshareOrientation::sample(millis()));
#endif
    vTaskDelay(pdMS_TO_TICKS(20));
  }
}

#ifdef SHELF_GOBLIN_WAVESHARE
void setScreenRotation(int rotation) {
  if (rotation == screenRotation) return;
  screenRotation = rotation;
  tft.setRotation(rotation);
  screenWidth = tft.width();
  screenHeight = tft.height();
  dirty = true;
  Serial.printf("Orientation: %d (%dx%d)\n", screenRotation, screenWidth, screenHeight);
}
#endif

void startCalibration() {
  if (!touchReady) return;
#ifdef SHELF_GOBLIN_WAVESHARE
  setScreenRotation(0);
#endif
  calibrationActive = true; calibrationStep = 0;
  calibrationHint = "Tap the target, then lift your finger";
#ifndef SHELF_GOBLIN_WAVESHARE
  evolution = evolution.paused();
#endif
  xQueueReset(touchEvents);
  dirty = true;
}

void renderCalibration() {
  const TouchPoint targets[] = {{24, 24}, {screenWidth - 24, 24}, {24, screenHeight - 24}, {screenWidth - 24, screenHeight - 24}};
  tft.fillScreen(bg);
  tft.setTextColor(accent, bg);
  tft.drawCentreString("TOUCH SETUP", screenCenter(), 70, 2);
  tft.setTextColor(TFT_WHITE, bg);
  tft.drawCentreString("Target " + String(calibrationStep + 1) + " of 4", screenCenter(), 98, 2);
  tft.setTextColor(muted, bg);
  tft.drawCentreString(calibrationHint, screenCenter(), 130, 1);
#ifndef SHELF_GOBLIN_WAVESHARE
  tft.drawCentreString("Use a firm tap or a blunt stylus", screenCenter(), 148, 1);
#endif
  TouchPoint target = targets[calibrationStep];
  tft.drawCircle(target.x, target.y, 12, accent);
  tft.drawFastHLine(target.x - 16, target.y, 33, TFT_WHITE);
  tft.drawFastVLine(target.x, target.y - 16, 33, TFT_WHITE);
  dirty = false;
}

#ifndef SHELF_GOBLIN_WAVESHARE
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
#endif
#ifdef SHELF_GOBLIN_WAVESHARE
void saveXp(uint32_t updatedXp) {
  if (updatedXp != experience) {
    experience = updatedXp;
#ifdef SHELF_VIRTUAL_PET
    if (currentForm() > bestForm) {
      bestForm = currentForm();
      if (storeReady) storage.putUInt("best-form", bestForm);
    }
#endif
    if (storeReady) storage.putUInt("xp-v1", experience);
    dirty = true;
  }
}
#endif

void seekFight() {
  if (fightReport.length()) return;
  fightForm = currentForm();
  const unsigned rank = static_cast<unsigned>(fightForm);
  const unsigned first = firstOpponentRank(rank);
#ifdef SHELF_VIRTUAL_PET
  const unsigned foeRank = first + esp_random() % (lastOpponentRank(rank, virtualPet::formCount) - first + 1);
  fightOpponent = &virtualPet::stages[foeRank].opponent;
#else
  const unsigned foeRank = first + esp_random() % (lastOpponentRank(rank) - first + 1);
  fightOpponent = &OPPONENTS[foeRank][esp_random() % 2];
#endif
  fightOpponentRank = foeRank;
  const unsigned roll = esp_random() % 100;
#ifdef SHELF_GOBLIN_WAVESHARE
#ifndef SHELF_VIRTUAL_PET
  linkedFight = spriteReady && cydAvailable(millis());
#endif
  const uint32_t amount = battleXp(rank, foeRank);
  showDefeat = roll >= winChance(rank, foeRank);
  if (showDefeat) {
    const uint32_t remainingXp = removeXp(experience, amount);
    const uint32_t lostXp = experience - remainingXp;
    fightReport = lostXp ? "Defeat. -" + String(lostXp) + " XP" : "Defeat. 0 XP lost";
    saveXp(remainingXp);
  } else {
    const uint32_t updatedXp = addXp(experience, amount, experienceCap);
    const uint32_t earnedXp = updatedXp - experience;
    fightReport = earnedXp ? "Victory! +" + String(earnedXp) + " XP" : "Victory! Max level";
    saveXp(updatedXp);
  }
  if (currentForm() != fightForm) fightReport += showDefeat ? " | Level down" : " | Level up!";
#else
  const FightOutcome outcome = fightOutcome(rank, foeRank, roll);
  showDefeat = outcome == FightOutcome::Reborn;
  if (outcome != FightOutcome::Won) {
    evolution = Evolution(bankAfterFight(evolution.healthMs, rank, outcome));
    saveEvolution();
    newClass = nullptr;
  }
  const char *result = outcome == FightOutcome::Reborn ? "Reborn as baby" :
      outcome == FightOutcome::Evolved ? "Won and evolved" : "Won";
  fightReport = String(fightOpponent->name) + " L" + String(foeRank + 1) + ": " + result;
#endif
  fightAt = millis();
  dirty = true;
}

bool hitsButton(TouchPoint raw, const FightButton &button) {
  TouchPoint point = mapTouch(calibration, raw);
#ifdef SHELF_GOBLIN_WAVESHARE
  point = waveshareOrientation::rotateTouch(point, screenRotation);
#endif
  return point.x >= button.x && point.x < button.x + button.width &&
      point.y >= button.y && point.y < button.y + button.height;
}
void drawPet(PetForm form, int offsetX = 0, bool defeated = false) {
  if (!spriteReady) return;
#ifdef SHELF_VIRTUAL_PET
  const uint32_t now = millis();
  const uint32_t revealElapsed = revealing ? now - revealAt : virtualPet::revealMs;
  virtualPet::draw(pet, petVisits::local == petVisits::Ant, form, bg, now, defeated, revealElapsed);
#elif defined(SHELF_GOBLIN_WAVESHARE)
  sceneArt::goblin(pet, form, bg, (millis() / 500) % 2 ? 2 : 0, defeated);
#else
  sceneArt::goblin(pet, form, bg, (millis() / 500) % 2 ? 2 : 0, defeated,
      health.mood == Mood::Critical || health.mood == Mood::Warning,
      !online || health.mood == Mood::Unknown);
#endif
  pet.pushSprite(8 + offsetX, 61);
}

#ifdef SHELF_GOBLIN_WAVESHARE
void drawVisitButton(const FightButton &button, const char *label, uint16_t color = accent) {
  tft.drawRoundRect(button.x, button.y, button.width, button.height, 5, color);
  tft.setTextColor(color, bg);
  tft.drawCentreString(label, button.x + button.width / 2, button.y + 7, 2);
}

void renderVisits(uint32_t now) {
  using namespace petVisits;
  if (status == Home) {
    static unsigned shownPeers = 0;
    unsigned available = 0;
    for (unsigned i = 0; i < SpeciesCount; ++i) {
      if (nearby(static_cast<Species>(i), now)) available |= 1U << i;
    }
    if (cydCamp::available(now, channel)) available |= 1U << SpeciesCount;
    if (campLink::ready()) available |= 2U << SpeciesCount;
    dirty = dirty || available != shownPeers;
    shownPeers = available;
  }
  if (dirty) {
    tft.fillScreen(bg);
    tft.setTextColor(TFT_WHITE, bg);
    if (status == Home) {
      tft.drawCentreString("NEARBY PETS", screenCenter(), 22, 2);
      unsigned row = 0;
      for (unsigned i = 0; i < SpeciesCount; ++i) {
        const auto species = static_cast<Species>(i);
        if (species == local) continue;
        drawVisitButton(visitChoice(row++), names[species], nearby(species, now) ? accent : muted);
      }
      const bool cydReady = cydCamp::available(now, channel);
      drawVisitButton(visitChoice(2), cydReady ? "CYD Camp" : "Go to Camp",
          cydReady || campLink::ready() ? accent : muted);
      drawVisitButton(visitChoice(3), "Back");
    } else {
      String title = names[partner];
      if (status == Incoming) title += " wants to visit";
      if (status == Calling) title = "Calling " + title;
      if (status == Waiting) title += " is on the way";
      if (status == Away) title = "Visiting " + title;
      if (status == Hosting) title += " is visiting!";
      tft.drawCentreString(title, screenCenter(), 22, 2);
      if (status == Incoming) drawVisitButton(visitChoice(1), "Pair and accept");
      if (status < Away) drawVisitButton(visitChoice(3), "Cancel");
    }
    dirty = false;
  }
  if (!spriteReady || status < Away || now - lastBattleFrame < 100) return;
  lastBattleFrame = now;
  const uint32_t elapsed = now - started;
  const uint32_t leg = min(elapsed, visitMs - elapsed);
  const int edge = (screenWidth / 2 + 80) * min(leg, walkMs) / walkMs;
  tft.fillRect(0, 61, screenWidth, 110, bg);
  if (status == Away) {
    drawPet(currentForm(), screenCenter() - 88 + edge);
  } else {
    drawPet(currentForm(), screenWidth - 173);
    if (partner == Goblin) {
      sceneArt::goblin(pet, static_cast<Form>(guestForm), bg, now / 250 % 2 * 2);
    } else {
      virtualPet::draw(pet, partner == Ant, guestForm, bg, now, false, virtualPet::revealMs);
    }
    pet.pushSprite(edge - screenWidth / 2 - 80, 61, bg);
  }
}
#endif

void drawBattle(uint32_t elapsed) {
  if (!spriteReady) return;
  const bool clash = elapsed >= 800 && elapsed < 3000;
  const unsigned beat = (elapsed / 120) % 6;
#ifdef SHELF_GOBLIN_WAVESHARE
#ifndef SHELF_VIRTUAL_PET
  if (linkedFight) {
    const int lunge = clash ? (beat < 3 ? 24 : -12) : 0;
    tft.fillRect(0, 61, screenWidth, 110, bg);
    drawPet(fightForm, screenWidth - 142 + lunge, showDefeat && elapsed >= 3000);
    if (clash && (beat == 2 || beat == 5)) {
      tft.drawLine(screenWidth - 24, 106, screenWidth - 2, 129, TFT_YELLOW);
      tft.drawLine(screenWidth - 24, 129, screenWidth - 2, 106, TFT_YELLOW);
    }
    return;
  }
#endif
  // The goblin sprite repaints the left side, including its overlap with the opponent.
  tft.fillRect(168, 61, screenWidth - 168, 110, bg);
#endif
  drawPet(fightForm, clash && beat < 3 ? 12 : 0);
#ifdef SHELF_PET_CAT
  virtualPet::drawToy(pet, fightOpponentRank, elapsed, bg);
#else
  sceneArt::monster(pet, *fightOpponent, fightOpponentRank, elapsed, bg);
#endif
#ifdef SHELF_GOBLIN_WAVESHARE
  pet.pushSprite(screenWidth - 160, 61, bg);
#else
  pet.pushSprite(160, 61);
#endif
}
#ifndef SHELF_GOBLIN_WAVESHARE
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
#endif
void render() {
  tft.fillScreen(bg);
  tft.setTextColor(accent, bg);
#ifdef SHELF_VIRTUAL_PET
  tft.drawString(virtualPet::title, 10, 7, 2);
#else
  tft.drawString("SHELF GOBLIN", 10, 7, 2);
#endif
#ifdef SHELF_GOBLIN_WAVESHARE
  const PetForm form = currentForm();
  const unsigned level = static_cast<unsigned>(fightOpponent || showDefeat ? fightForm : form) + 1;
  tft.drawRightString("LEVEL " + String(level), screenWidth - 10, 7, 2);
#else
  tft.setTextColor(healthColor(), bg);
  tft.drawRightString(healthLabel(), screenWidth - 10, 7, 2);
#endif
  tft.drawFastHLine(10, 30, screenWidth - 20, muted);
#ifndef SHELF_GOBLIN_WAVESHARE
  tft.drawString(health.reason, 10, 36, 2);
#endif
  if (fightOpponent) {
    drawBattle(millis() - fightAt);
    tft.setTextColor(TFT_WHITE, bg);
    tft.drawCentreString(String("vs. ") + fightOpponent->name + "  L" + String(fightOpponentRank + 1), screenCenter(), 181, 2);
    dirty = false;
    return;
  }
  if (showDefeat) {
    drawPet(fightForm, screenCenter() - 88, true);
    tft.setTextColor(TFT_RED, bg);
    tft.setTextSize(2);
    if (!spriteReady) tft.drawCentreString("( X _ X )", screenCenter(), 107, 2);
    tft.drawCentreString("DEFEATED", screenCenter(), 179, 2);
    tft.setTextSize(1);
    dirty = false;
    return;
  }
#ifdef SHELF_GOBLIN_WAVESHARE
  drawPet(form, petOffset());
  tft.setTextColor(TFT_WHITE, bg);
  const bool tall = portrait();
  const int detailsX = tall ? screenCenter() : 221;
  if (!spriteReady) tft.drawCentreString("( ^ v ^ )", tall ? screenCenter() : 88, 105, 2);
#ifdef SHELF_VIRTUAL_PET
  const String name = virtualPet::stages[form].name;
#else
  const String name = milestone(form).name;
#endif
  tft.drawCentreString(name, detailsX, tall ? 170 : 78, !tall && tft.textWidth(name, 2) > 110 ? 1 : 2);

  const unsigned rank = static_cast<unsigned>(form);
#ifdef SHELF_VIRTUAL_PET
  const String progress = rank == virtualPet::formCount - 1 ? "MAX LEVEL" :
      String(experience) + " / " + String(virtualPet::threshold(rank + 1)) + " XP";
#else
  const String progress = rank == FORM_COUNT - 1 ? "MAX LEVEL  |  " + String(experience) + " XP" :
      String(experience) + " / " + String(XP_THRESHOLDS[rank + 1]) + " XP";
#endif
  tft.setTextColor(accent, bg);
  tft.drawCentreString(progress, detailsX, tall ? 192 : 106, 2);
  tft.setTextColor(muted, bg);
#ifdef SHELF_VIRTUAL_PET
  const char *bestName = virtualPet::stages[bestForm].name;
  if (tall) {
    tft.drawCentreString(String("Best: ") + bestName, detailsX, 209, 1);
  } else {
    tft.drawCentreString("BEST FORM", detailsX, 128, 1);
    tft.drawCentreString(bestName, detailsX, 140, 1);
  }
  if (fightReport.length()) tft.drawCentreString(fightReport, screenCenter(), screenHeight - 56, 1);
#else
  if (fightReport.length()) tft.drawCentreString(fightReport, screenCenter(), screenHeight - 65, 2);
#endif
  if (!touchReady) tft.drawCentreString("Touch unavailable", screenCenter(), screenHeight - 32, 2);
  else {
    const uint16_t buttonColor = fightReport.length() ? muted : accent;
    const FightButton button = fightButton();
    tft.drawRoundRect(button.x, button.y, button.width, button.height, 5, buttonColor);
    tft.setTextColor(buttonColor, bg);
#ifdef SHELF_VIRTUAL_PET
    tft.drawCentreString(virtualPet::action, button.x + button.width / 2, button.y + 6, 2);
#else
    tft.drawCentreString("FIGHT!", button.x + button.width / 2, button.y + 6, 2);
#endif
    drawVisitButton(visitButton(), "Visit", buttonColor);
  }
#else
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
    drawPet(formFor(evolution.healthMs), petOffset());
    if (!spriteReady) {
      tft.setTextColor(accent, bg);
      tft.drawCentreString("( ^ v ^ )", 75, 105, 2);
    }
    tft.setTextColor(TFT_WHITE, bg);
    const Form form = formFor(evolution.healthMs);
    const auto &current = milestone(form);
    const String classTitle = current.className ? String("[") + current.className + "]" : "";
    const bool bodyMilestone = form == Form::Adult || form == Form::Hobgoblin;
    const String title = !current.className || bodyMilestone ? String(current.name) : classTitle;
    tft.drawString(title, 182, 67, 2);
    tft.setTextColor(muted, bg);
    const String level = "L" + String(static_cast<unsigned>(form) + 1);
    tft.drawString(bodyMilestone ? classTitle + "  " + level : level, 182, 86, 1);
    tft.drawString("HEALTHY TIME", 182, 108, 1);
    tft.setTextColor(TFT_WHITE, bg);
    tft.drawString(duration(evolution.healthMs), 182, 121, 2);
    tft.setTextColor(muted, bg);
    const uint32_t dropMs = timeToDrop(evolution.healthMs, health.mood);
    if (dropMs) {
      tft.setTextColor(healthColor(), bg);
      tft.drawString("Drop in " + countdown(dropMs), 182, 146, 1);
    } else if (static_cast<unsigned>(form) < FORM_COUNT - 1) {
      const auto &next = milestone(static_cast<Form>(static_cast<unsigned>(form) + 1));
      tft.drawString(String("Next: ") + next.name, 182, 146, 1);
      const String remaining = countdown(next.thresholdMs - evolution.healthMs);
      tft.drawString(remaining, 182, 157, 1);
    }
    tft.setTextColor(TFT_WHITE, bg);
  }
  if (page == 0) {
    tft.setTextColor(muted, bg);
    String caption = fightReport.length() ? fightReport : newClass ? String("[Class Obtained: ") + newClass + "]" :
        !touchReady ? "Touch unavailable; restart device" : !online ?
        (hasData ? "Last update " + String((millis() - lastGood) / 1000) + "s ago" : "Waiting for server metrics...") : "Keeping watch over the lab.";
    const int captionFont = tft.textWidth(caption, 2) <= screenWidth - 16 ? 2 : 1;
    tft.drawCentreString(caption, screenCenter(), 176, captionFont);
    if (touchReady) {
      const uint16_t buttonColor = fightReport.length() ? muted : accent;
      const FightButton button = fightButton();
      tft.drawRoundRect(button.x, button.y, button.width, button.height, 5, buttonColor);
      tft.setTextColor(buttonColor, bg);
      tft.drawCentreString("Seek a Fight", button.x + button.width / 2, button.y + 9, 2);
    }
    tft.setTextColor(accent, bg);
    tft.drawString("< Swipe left for metrics", 10, 212, 1);
  } else {
    tft.setTextColor(muted, bg);
    tft.drawCentreString("Hold 2s to recalibrate touch", screenCenter(), 190, 1);
  }
  if (page == 1) {
    tft.setTextColor(accent, bg);
    tft.drawCentreString("Swipe right for goblin >", screenCenter(), 215, 2);
  }
#endif
  dirty = false;
}

void handleTouch(const TouchStroke &stroke) {
  if (calibrationActive) {
    if (!isCalibrationTap(stroke)) return;
    TouchPoint raw = stroke.average;
    if (calibrationStep < 3) {
      calibrationRaw[calibrationStep++] = raw;
      if (calibrationStep == 3 && !calibrateTouch(calibrationRaw, candidate, screenWidth, screenHeight)) {
        calibrationStep = 0;
        calibrationHint = "Targets too close; please try again";
      }
    } else if (confirmsCalibration(candidate, raw, screenWidth, screenHeight)) {
      calibration = candidate;
      calibrated = true; calibrationActive = false;
      if (storeReady) storage.putBytes(calibrationKey, &calibration, sizeof(calibration));
      Serial.println("Touch: calibration completed");
    } else {
      calibrationStep = 0;
      calibrationHint = "Alignment check failed; try again";
    }
    dirty = true;
    return;
  }
  if (!calibrated || fightOpponent || showDefeat) return;
#if defined(SHELF_GOBLIN_WAVESHARE) && !defined(SHELF_VIRTUAL_PET)
  if (patrolling) return;
#endif
#ifdef SHELF_GOBLIN_WAVESHARE
  const Gesture gesture = classifyGesture(calibration, stroke, nativeWidth, nativeHeight);
#else
  const Gesture gesture = classifyGesture(calibration, stroke, screenWidth, screenHeight);
#endif
  switch (gesture) {
#ifndef SHELF_GOBLIN_WAVESHARE
    case Gesture::Left: page = 1; dirty = true; break;
    case Gesture::Right: page = 0; dirty = true; break;
#endif
    case Gesture::Hold: startCalibration(); break;
    case Gesture::Tap:
#ifdef SHELF_GOBLIN_WAVESHARE
      {
        const auto tapped = [&](FightButton button) {
          return hitsButton(stroke.first, button) && hitsButton(stroke.last, button);
        };
        const uint32_t now = millis();
        using namespace petVisits;
        if (campLink::state != campLink::Home || cydCamp::state != cydCamp::Home) {
          if (tapped(visitChoice(3))) {
            campLink::leave(static_cast<unsigned>(currentForm()));
            cydCamp::leave(local, static_cast<unsigned>(currentForm()));
            dirty = true;
          }
          break;
        }
        if (status != Home || visitMenu) {
          if (status < Away && tapped(visitChoice(3))) {
            close(static_cast<unsigned>(currentForm()), now);
            visitMenu = false;
          } else if (status == Incoming && tapped(visitChoice(1))) {
            accept(now);
          } else if (status == Home) {
            if (tapped(visitChoice(2))) {
              if (cydCamp::available(now, channel)) {
                cydCamp::join(now);
                visitMenu = false;
              } else if (campLink::ready()) {
                campLink::join(now);
                visitMenu = false;
              }
            } else {
              unsigned row = 0;
              for (unsigned i = 0; i < SpeciesCount; ++i) {
                const auto species = static_cast<Species>(i);
                if (species == local) continue;
                if (tapped(visitChoice(row++))) invite(species, now);
              }
            }
          }
          dirty = true;
          break;
        }
        if (!fightReport.length() && tapped(visitButton())) {
          visitMenu = true;
          dirty = true;
          break;
        }
      }
#endif
#ifndef SHELF_GOBLIN_WAVESHARE
      if (page != 0) break;
#endif
      if (hitsButton(stroke.first, fightButton()) && hitsButton(stroke.last, fightButton())) seekFight();
      break;
    default: break;
  }
}
#ifndef SHELF_GOBLIN_WAVESHARE
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
#endif
void setup() {
  Serial.begin(115200);
  pinMode(0, INPUT_PULLUP);
  tft.init(); tft.setRotation(screenRotation);
  pinMode(TFT_BL, OUTPUT); digitalWrite(TFT_BL, TFT_BACKLIGHT_ON);
  pet.setColorDepth(16);
  spriteReady = pet.createSprite(160, 110) != nullptr;
#ifdef SHELF_VIRTUAL_PET
  storeReady = storage.begin(virtualPet::saveNamespace, false);
  experience = addXp(storeReady ? storage.getUInt("xp-v1", 0) : 0, 0, experienceCap);
  bestForm = storeReady ? storage.getUInt("best-form", 0) : 0;
  if (bestForm >= virtualPet::formCount || bestForm < currentForm()) bestForm = currentForm();
#else
  storeReady = storage.begin("shelf-goblin", false);
#ifdef SHELF_GOBLIN_WAVESHARE
  experience = addXp(storeReady ? storage.getUInt("xp-v1", 0) : 0, 0);
#else
  evolution = Evolution(storeReady ? storage.getUInt("health-v1", 0) : 0);
#endif
#endif
  calibrated = storeReady && storage.getBytesLength(calibrationKey) == sizeof(calibration) &&
      storage.getBytes(calibrationKey, &calibration, sizeof(calibration)) == sizeof(calibration) &&
      validCalibration(calibration);
#ifdef SHELF_GOBLIN_WAVESHARE
  touchReady = waveshareTouch::begin();
  orientationReady = waveshareOrientation::begin();
  Serial.printf("Orientation sensor: %s\n", orientationReady ? "ready" : "unavailable");
#else
  touchBus.begin(25, 39, 32, 33);
  touchReady = touchscreen.begin(touchBus);
  touchscreen.setRotation(1);
#endif
  touchEvents = xQueueCreate(8, sizeof(TouchStroke));
  touchReady = touchReady && touchEvents != nullptr;
#ifdef SHELF_GOBLIN_WAVESHARE
  if ((touchReady || orientationReady) &&
      xTaskCreate(sampleTouch, "input", 3072, nullptr, 1, nullptr) != pdPASS) {
    touchReady = orientationReady = false;
  }
#else
  if (touchReady) touchReady = xTaskCreate(sampleTouch, "touch", 3072, nullptr, 1, nullptr) == pdPASS;
#endif
  if (!calibrated) startCalibration();
#ifdef SHELF_GOBLIN_WAVESHARE
  idleStartedAt = millis();
  WiFi.mode(WIFI_STA);
  WiFi.setSleep(false);
  campLink::begin(storeReady ? &storage : nullptr);
#ifndef SHELF_VIRTUAL_PET
  schedulePatrol(idleStartedAt);
  displayLink::begin(displayLink::cydMac, receivePeerPacket);
  petVisits::begin(storeReady ? &storage : nullptr, false, idleStartedAt);
#else
  petVisits::begin(storeReady ? &storage : nullptr, true, idleStartedAt, receivePeerPacket);
#endif
  cydCamp::begin();
#endif
#ifndef SHELF_GOBLIN_WAVESHARE
  message("Starting Wi-Fi...", "Hold BOOT 5s to set up Wi-Fi");
  wifi.setConfigPortalBlocking(false);
  wifi.setDebugOutput(false);
  wifi.setAPCallback([](WiFiManager *) {
    message(String("Wi-Fi setup: ") + setupNetwork, "Join it; open 192.168.4.1");
  });
  wifi.autoConnect(setupNetwork);
#endif
  Serial.printf("Shelf Goblin ready: display=%dx%d touch=%s\n",
      tft.width(), tft.height(), touchReady ? "ready" : "unavailable");
}
void loop() {
#ifndef SHELF_GOBLIN_WAVESHARE
  wifi.process();
#else
  constexpr bool portalActive = false;
#endif
  uint32_t now = millis();
#ifdef SHELF_GOBLIN_WAVESHARE
  // Allow the deployment verifier to attach after USB re-enumeration.
  static uint32_t lastBootSignal = 0;
  if (now < 30000 && now - lastBootSignal >= 1000) {
    lastBootSignal = now;
#ifdef SHELF_VIRTUAL_PET
    Serial.printf("%s running\n", virtualPet::title);
#else
    Serial.println("Shelf Goblin running");
#endif
  }
#endif
  if (digitalRead(0) == LOW) {
    if (!pressed) pressed = now;
#ifndef SHELF_GOBLIN_WAVESHARE
    if (!longHandled && now - pressed >= 5000) {
      longHandled = true;
      wifi.startConfigPortal(setupNetwork);
    }
#endif
  } else if (pressed) {
    uint32_t duration = now - pressed;
#ifndef SHELF_GOBLIN_WAVESHARE
    if (longHandled || wifi.getConfigPortalActive()) duration = 0;
#endif
    if (duration >= 1000) startCalibration();
    else if (duration >= 40 && calibrationActive && calibrated) { calibrationActive = false; dirty = true; }
    pressed = 0;
#ifndef SHELF_GOBLIN_WAVESHARE
    longHandled = false;
#endif
  }
#ifndef SHELF_GOBLIN_WAVESHARE
  const bool portalActive = wifi.getConfigPortalActive();
#endif
  if (touchReady) {
    TouchStroke stroke;
    while (xQueueReceive(touchEvents, &stroke, 0) == pdTRUE) {
      if (!portalActive) handleTouch(stroke);
    }
  }
  now = millis();
#ifdef SHELF_GOBLIN_WAVESHARE
  bool radioFixed = false;
  bool canVisit = calibrated && touchReady && !calibrationActive && !pressed &&
      !fightOpponent && !showDefeat && !fightReport.length();
#ifndef SHELF_VIRTUAL_PET
  findCyd();
  now = millis();
  radioFixed = cydAvailable(now);
  canVisit = canVisit && !patrolling;
#endif
  const auto previousCamp = campLink::state;
  const bool campWasReady = campLink::ready();
  const auto form = static_cast<unsigned>(currentForm());
  campLink::tick(now, form, canVisit && petVisits::status == petVisits::Home &&
      cydCamp::state == cydCamp::Home);
  if (campWasReady != campLink::ready() || previousCamp != campLink::state) dirty = true;
  if (WiFi.status() == WL_CONNECTED) {
    uint8_t primary = 0;
    wifi_second_chan_t secondary;
    if (esp_wifi_get_channel(&primary, &secondary) == ESP_OK) petVisits::channel = primary;
    radioFixed = true;
  } else if (campLink::connecting) {
    radioFixed = true;
  }
  const auto previousCydCamp = cydCamp::state;
  cydCamp::clientTick(now, petVisits::local, form, petVisits::channel);
  if (previousCydCamp != cydCamp::state) dirty = true;
  radioFixed = radioFixed || cydCamp::state != cydCamp::Home ||
      cydCamp::available(now, petVisits::channel);
  const bool atAnyCamp = campLink::state != campLink::Home || cydCamp::state != cydCamp::Home;
  canVisit = canVisit && !atAnyCamp;
  const auto previousVisit = petVisits::status;
  if (!canVisit) petVisits::close(static_cast<unsigned>(currentForm()), now);
  petVisits::tick(now, static_cast<unsigned>(currentForm()), canVisit, radioFixed);
  if (previousVisit != petVisits::status) {
    if (petVisits::status == petVisits::Home || petVisits::status >= petVisits::Away) visitMenu = false;
    dirty = true;
  }
  const bool visiting = visitMenu || petVisits::status != petVisits::Home || atAnyCamp;
#ifndef SHELF_VIRTUAL_PET
  now = millis();
  displayLink::Frame frame;
  if (fightOpponent && linkedFight && !cydAvailable(now)) {
    linkedFight = false;
    dirty = true;
  }
  if (fightOpponent && linkedFight && now - fightAt < displayLink::fightMs) {
    frame.scene = displayLink::Fight;
    frame.elapsed = now - fightAt;
    frame.rank = fightOpponentRank;
    frame.opponent = fightOpponent == &OPPONENTS[fightOpponentRank][1];
    frame.defeated = !showDefeat;
  }
  if (patrolling && (now - patrolAt >= displayLink::patrolMs || !cydAvailable(now) || calibrationActive)) {
    patrolling = false;
    schedulePatrol(now);
    dirty = true;
  }
  if (!visiting && !patrolling && !pressed && !calibrationActive && !touchInProgress.load() &&
      !fightOpponent && !showDefeat && !fightReport.length() &&
      spriteReady && cydAvailable(now) && static_cast<int32_t>(now - nextPatrol) >= 0) {
    patrolling = true;
    patrolAt = now;
    patrolForm = currentForm();
    dirty = true;
  }
  if (patrolling) {
    frame.scene = displayLink::Patrol;
    frame.elapsed = now - patrolAt;
    frame.form = static_cast<uint8_t>(patrolForm);
    const int travel = screenWidth - screenCenter() + 80;
    frame.patrolX = displayLink::walkDistance(frame.elapsed, travel) - travel;
  }
  displayLink::send(frame, now, 65);
  if (patrolling) {
    if (dirty) {
      tft.fillScreen(bg);
      dirty = false;
    }
    if (now - lastBattleFrame >= 65) {
      lastBattleFrame = now;
      const int x = screenWidth + frame.patrolX;
      tft.fillRect(0, 61, screenWidth, 110, bg);
      if (x < screenWidth && spriteReady) {
        sceneArt::patrol(pet, patrolForm, bg, frame.elapsed, true);
        pet.pushSprite(x, 61);
      }
      tft.fillRect(screenCenter() - 82, 181, 164, 34, 0x6204);
      tft.drawRoundRect(screenCenter() - 82, 181, 164, 34, 4, TFT_GOLD);
      tft.setTextColor(TFT_WHITE, 0x6204);
      tft.drawCentreString("out on patrol", screenCenter(), 190, 2);
    }
    delay(10);
    return;
  }
#endif
  if (atAnyCamp && !calibrationActive) {
    idleStartedAt = now;
    if (dirty) {
      tft.fillScreen(bg);
      tft.setTextColor(TFT_WHITE, bg);
      const bool arrived = campLink::state == campLink::AtCamp || cydCamp::state == cydCamp::AtCamp;
      tft.drawCentreString(arrived ? "AT CAMP" : "HEADING TO CAMP",
          screenCenter(), 57, 2);
      drawVisitButton(visitChoice(3), "Come Home");
      dirty = false;
    }
    delay(10);
    return;
  }
  if (visiting && canVisit) {
    idleStartedAt = now;
    renderVisits(now);
    delay(10);
    return;
  }
  if (!calibrationActive && !fightOpponent && !showDefeat && !touchInProgress.load()) {
    const int rotation = pendingRotation.load();
    if (rotation != waveshareOrientation::noRotation) setScreenRotation(rotation);
  }
  if (pressed || calibrationActive || fightOpponent || showDefeat || fightReport.length()) {
    idleStartedAt = now;
  } else {
    const uint32_t reward = idleXpFor(now - idleStartedAt);
    if (reward) {
      idleStartedAt += reward * IDLE_XP_INTERVAL_MS;
      const PetForm previous = currentForm();
      saveXp(addXp(experience, reward, experienceCap));
      if (currentForm() != previous) {
#ifdef SHELF_VIRTUAL_PET
        revealAt = now;
        revealing = true;
#endif
        fightReport = "Level up from idle XP!";
        fightAt = now;
      }
    }
  }
#endif
#ifndef SHELF_GOBLIN_WAVESHARE
  if (now - lastSave >= 300000) saveEvolution();
  if (portalActive) {
    evolution = evolution.paused();
    dirty = true;
    delay(10);
    return;
  }
#endif
  if (calibrationActive) {
#ifndef SHELF_GOBLIN_WAVESHARE
    evolution = evolution.paused();
#endif
    if (dirty) renderCalibration();
    delay(10);
    return;
  }
  // Keep network polling out of the animation so an HTTP timeout cannot delay the reveal.
  if (fightOpponent) {
    const uint32_t elapsed = now - fightAt;
    if (elapsed >= FIGHT_ANIMATION_MS) {
      fightOpponent = nullptr;
      fightAt = now;
#ifdef SHELF_VIRTUAL_PET
      revealing = currentForm() > fightForm;
      revealAt = now;
#endif
      render();
    } else if (dirty || now - lastBattleFrame >= 80) {
      if (dirty) render();
      else drawBattle(elapsed);
      lastBattleFrame = now;
    }
    delay(10);
    return;
  }
  if (showDefeat) {
    if (now - fightAt >= DEFEAT_SCREEN_MS) {
      showDefeat = false;
      render();
    } else if (dirty) {
      render();
    }
    delay(10);
    return;
  }
#ifndef SHELF_GOBLIN_WAVESHARE
  // Avoid blocking requests during a button hold.
  if (!pressed && !touchDown && (lastPoll == 0 || now - lastPoll >= 5000)) {
    poll(); lastPoll = millis();
  }
  if (newClass && millis() - classObtainedAt >= 5000) {
    newClass = nullptr;
    dirty = true;
  }
#endif
  if (fightReport.length() && millis() - fightAt >= FIGHT_REPORT_MS) {
    fightReport = "";
    dirty = true;
  }
#ifdef SHELF_VIRTUAL_PET
  if (revealing && now - revealAt >= virtualPet::revealMs) {
    revealing = false;
    dirty = true;
  }
  if (dirty) render();
  else if (now - lastFrame >= (revealing ? 80 : 160)) {
    drawPet(currentForm(), petOffset());
    lastFrame = now;
  }
#else
  if (dirty) render();
#ifdef SHELF_GOBLIN_WAVESHARE
  else if (now - lastFrame >= 500) drawPet(currentForm(), petOffset());
#else
  else if (page == 0 && now - lastFrame >= 500) drawPet(currentForm(), petOffset());
#endif
  if (now - lastFrame >= 500) lastFrame = now;
#endif
  delay(10);
}
