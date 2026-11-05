// Compile-only regression tests: every assertion is evaluated by the compiler.
// g++ -std=c++14 -fsyntax-only tests/test_esp32_health.cpp
#include "../hardware/esp32-monitor/src/health.h"
#include "../hardware/esp32-monitor/src/evolution.h"
constexpr Readings good{20, 40, 45, 30, 50, 8, 10, 0};
static_assert(assess(good, true).mood == Mood::Healthy, "Stopped containers can be intentional");
static_assert(assess(good, false).mood == Mood::Offline, "Cached readings cannot imply online health");
static_assert(assess(Readings{}, true).mood == Mood::Unknown, "Missing metrics are not healthy");
constexpr bool thresholds() {
  Readings r = good;
  r.cpu = 84.9;
  if (assess(r, true).mood != Mood::Healthy) return false;
  r.cpu = 85;
  if (assess(r, true).mood != Mood::Busy) return false;
  r.temp = 70;
  if (assess(r, true).mood != Mood::Warning) return false;
  r.temp = 85;
  if (assess(r, true).mood != Mood::Critical) return false;
  r = good;
  r.unhealthy = 1;
  if (assess(r, true).mood != Mood::Critical) return false;
  r.temp = -1;
  if (assess(r, true).mood != Mood::Critical) return false;
  r = good;
  r.unhealthy = -1;
  if (assess(r, true).mood != Mood::Unknown) return false;
  r.root = 95;
  if (assess(r, true).mood != Mood::Critical) return false;
  r = good;
  r.root = 84.9;
  if (assess(r, true).mood != Mood::Healthy) return false;
  r.root = 85;
  if (assess(r, true).mood != Mood::Warning) return false;
  r.root = 95;
  if (assess(r, true).mood != Mood::Critical) return false;
  r = good;
  r.media = 85;
  if (assess(r, true).mood != Mood::Warning) return false;
  r.media = 95;
  if (assess(r, true).mood != Mood::Critical) return false;
  r = good;
  r.ram = 85;
  if (assess(r, true).mood != Mood::Warning) return false;
  r.ram = 95;
  return assess(r, true).mood == Mood::Critical;
}
static_assert(thresholds(), "Health threshold or alert precedence regression");

static_assert(formFor(ADULT_AT_MS - 1) == Form::Baby, "Baby until one healthy day");
static_assert(formFor(ADULT_AT_MS) == Form::Adult, "Adult at one healthy day");
static_assert(formFor(WARRIOR_AT_MS - 1) == Form::Adult, "Adult until seven healthy days");
static_assert(formFor(WARRIOR_AT_MS) == Form::Warrior, "Warrior at seven healthy days");
static_assert(healthDelta(Mood::Healthy, Mood::Busy, 5000) == 5000, "Busy is healthy work");
static_assert(healthDelta(Mood::Healthy, Mood::Warning, 5000) == -5000, "Warnings drain 1x");
static_assert(healthDelta(Mood::Critical, Mood::Healthy, 5000) == -20000, "Critical recovery drains 4x");
static_assert(healthDelta(Mood::Warning, Mood::Critical, 5000) == -20000, "Use worse severity");
static_assert(healthDelta(Mood::Healthy, Mood::Unknown, 5000) == 0, "Unknown pauses");
static_assert(healthDelta(Mood::Offline, Mood::Healthy, 5000) == 0, "No credit for missing time");
static_assert(healthDelta(Mood::Healthy, Mood::Healthy, 20001) == 0, "Long gaps do not accrue");
static_assert(applyHealthDelta(0, -20000) == 0, "No unsigned underflow");
static_assert(applyHealthDelta(MAX_HEALTH_MS - 1, 5000) == MAX_HEALTH_MS, "Cap healthy-time bank");
static_assert(formFor(applyHealthDelta(ADULT_AT_MS, -5000)) == Form::Baby, "Adult can devolve");
static_assert(formFor(applyHealthDelta(WARRIOR_AT_MS, -20000)) == Form::Adult, "Warrior can devolve");

constexpr bool evolutionTimeline() {
  Evolution pet;
  pet = pet.observed(Mood::Healthy, 100, 1000);
  if (!(pet.healthMs == 0)) return false; // First sample establishes a baseline.
  pet = pet.observed(Mood::Busy, 5100, 1005);
  if (!(pet.healthMs == 5000)) return false;
  pet = pet.observed(Mood::Healthy, 10100, 1005); // Cached sample.
  if (!(pet.healthMs == 5000)) return false;
  pet = pet.observed(Mood::Healthy, 15100, 1015);
  if (!(pet.healthMs == 5000)) return false;
  pet = pet.observed(Mood::Healthy, 20100, 1020);
  if (!(pet.healthMs == 10000)) return false;
  pet = pet.observed(Mood::Offline, 25100, 0);
  pet = pet.observed(Mood::Healthy, 30100, 1030);
  if (!(pet.healthMs == 10000)) return false;
  pet = pet.observed(Mood::Critical, 35100, 1035);
  if (!(pet.healthMs == 0)) return false;

  pet = Evolution(WARRIOR_AT_MS + 5000);
  pet = pet.paused();
  pet = pet.observed(Mood::Warning, 40100, 1040);
  pet = pet.observed(Mood::Warning, 50100, 1050);
  if (!(formFor(pet.healthMs) == Form::Adult)) return false;
  pet = Evolution(0xFFFFFFFFU);
  if (!(pet.healthMs == MAX_HEALTH_MS)) return false;

  pet = Evolution(0);
  pet = pet.paused();
  pet = pet.observed(Mood::Healthy, 0xFFFFFF00U, 2000);
  pet = pet.observed(Mood::Healthy, 4744, 2005); // millis() rollover.
  if (!(pet.healthMs == 5000)) return false;
  pet = pet.observed(Mood::Healthy, 60000, 2060); // Long unobserved gap.
  if (!(pet.healthMs == 5000)) return false;
  pet = pet.observed(Mood::Healthy, 65000, 1000); // Server clock moved backwards.
  pet = pet.observed(Mood::Healthy, 70000, 1005);
  if (!(pet.healthMs == 5000)) return false;
  pet = pet.observed(Mood::Healthy, 75000, 1010);
  if (!(pet.healthMs == 10000)) return false;
  return true;
}
static_assert(evolutionTimeline(), "Evolution observation timeline regression");
int main() { return evolutionTimeline() ? 0 : 1; }
