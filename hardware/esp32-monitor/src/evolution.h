#pragma once
#include <stdint.h>
#include "health.h"

constexpr uint32_t HEALTHY_HOUR_MS = 60UL * 60 * 1000;
constexpr uint32_t HEALTHY_DAY_MS = 24UL * HEALTHY_HOUR_MS;
constexpr uint32_t MAX_HEALTH_MS = 35UL * HEALTHY_DAY_MS;
constexpr uint32_t MAX_OBSERVATION_GAP_MS = 20000;
enum class Form { Baby, Scavenger, Adult, Tactician, Hobgoblin, Chieftain, GreatChieftain, GoblinLord, Count };
struct Milestone { uint32_t thresholdMs; const char *name; const char *className; };
constexpr Milestone MILESTONES[] = {
    {0, "Baby Goblin", nullptr},
    {8UL * HEALTHY_HOUR_MS, "Scavenger", "Scavenger"},
    {HEALTHY_DAY_MS, "Adult Goblin", "Scavenger"},
    {3UL * HEALTHY_DAY_MS, "Tactician", "Tactician"},
    {7UL * HEALTHY_DAY_MS, "Red Hobgoblin", "Tactician"},
    {10UL * HEALTHY_DAY_MS, "Chieftain", "Chieftain"},
    {21UL * HEALTHY_DAY_MS, "Great Chieftain", "Great Chieftain"},
    {28UL * HEALTHY_DAY_MS, "Goblin Lord", "Goblin Lord"},
};
constexpr unsigned FORM_COUNT = sizeof(MILESTONES) / sizeof(MILESTONES[0]);
static_assert(FORM_COUNT == static_cast<unsigned>(Form::Count), "Each form needs a milestone");
constexpr const Milestone &milestone(Form form) { return MILESTONES[static_cast<unsigned>(form)]; }
constexpr Form formFor(uint32_t healthMs, unsigned stage = FORM_COUNT - 1) {
  return healthMs >= MILESTONES[stage].thresholdMs ? static_cast<Form>(stage) :
      formFor(healthMs, stage - 1);
}
constexpr bool knownHealth(Mood mood) {
  return mood != Mood::Unknown && mood != Mood::Offline;
}
constexpr unsigned int decayRate(Mood mood) {
  return mood == Mood::Critical ? 4 : mood == Mood::Warning ? 1 : 0;
}
// A form changes only once the bank falls strictly below its threshold.
constexpr uint32_t timeToDrop(uint32_t healthMs, Mood mood) {
  return formFor(healthMs) != Form::Baby && decayRate(mood) ?
      (healthMs - milestone(formFor(healthMs)).thresholdMs) / decayRate(mood) + 1 : 0;
}
// Credit only intervals bracketed by fresh, known observations. An alert at
// either end uses the worse severity; transitions never award healthy time.
constexpr int32_t healthDelta(Mood previous, Mood current, uint32_t elapsedMs) {
  return !knownHealth(previous) || !knownHealth(current) ||
      elapsedMs > MAX_OBSERVATION_GAP_MS ? 0 :
      (decayRate(previous) || decayRate(current)) ?
      -static_cast<int32_t>(elapsedMs *
          (decayRate(previous) > decayRate(current) ? decayRate(previous) : decayRate(current))) :
      static_cast<int32_t>(elapsedMs);
}
constexpr uint32_t applyHealthDelta(uint32_t healthMs, int32_t delta) {
  return delta < 0 ? (static_cast<uint32_t>(-delta) >= healthMs ? 0 : healthMs + delta) :
      (static_cast<uint32_t>(delta) >= MAX_HEALTH_MS - healthMs ? MAX_HEALTH_MS : healthMs + delta);
}

class Evolution {
 public:
  uint32_t healthMs;
  constexpr Evolution(uint32_t savedMs = 0)
      : healthMs(savedMs > MAX_HEALTH_MS ? MAX_HEALTH_MS : savedMs) {}

  constexpr Evolution paused() const {
    return Evolution(healthMs, false, lastObserved, lastSample, lastMood);
  }
  // Return a new state so entire observation timelines can be checked at compile time.
  constexpr Evolution observed(Mood mood, uint32_t now, int64_t sampleTimestamp) const {
    return !knownHealth(mood) || sampleTimestamp <= 0 ? paused() :
        sampleTimestamp <= lastSample ?
        Evolution(healthMs, false, lastObserved, sampleTimestamp, lastMood) :
        Evolution(tracking ? applyHealthDelta(healthMs, healthDelta(lastMood, mood, now - lastObserved)) : healthMs,
                  true, now, sampleTimestamp, mood);
  }

 private:
  bool tracking = false;
  uint32_t lastObserved = 0;
  int64_t lastSample = 0;
  Mood lastMood = Mood::Unknown;
  constexpr Evolution(uint32_t value, bool active, uint32_t observedAt, int64_t timestamp, Mood mood)
      : healthMs(value), tracking(active), lastObserved(observedAt), lastSample(timestamp), lastMood(mood) {}
};
