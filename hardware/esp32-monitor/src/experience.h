#pragma once
#include "combat.h"

constexpr uint32_t XP_THRESHOLDS[] = {0, 60, 150, 280, 460, 700, 1010, 1400, 1900};
static_assert(sizeof(XP_THRESHOLDS) / sizeof(XP_THRESHOLDS[0]) == FORM_COUNT,
              "Each form needs an XP threshold");

constexpr uint32_t MAX_XP = XP_THRESHOLDS[FORM_COUNT - 1];
constexpr uint32_t IDLE_XP_INTERVAL_MS = 5UL * 60 * 1000;

constexpr Form formForXp(uint32_t xp, unsigned stage = FORM_COUNT - 1) {
  return xp >= XP_THRESHOLDS[stage] ? static_cast<Form>(stage) : formForXp(xp, stage - 1);
}

constexpr uint32_t battleXp(unsigned rank, unsigned foeRank) {
  return foeRank < rank ? 20 : foeRank == rank ? 25 : 35;
}

constexpr uint32_t addXp(uint32_t xp, uint32_t reward) {
  return xp >= MAX_XP || reward >= MAX_XP - xp ? MAX_XP : xp + reward;
}

constexpr uint32_t idleXpFor(uint32_t elapsedMs) {
  return elapsedMs / IDLE_XP_INTERVAL_MS;
}

constexpr uint32_t removeXp(uint32_t xp, uint32_t penalty) {
  return penalty >= xp ? 0 : xp - penalty;
}

static_assert(formForXp(addXp(0, battleXp(0, 1))) == Form::Baby,
              "A win against a stronger foe does not grant an instant evolution");
static_assert(formForXp(addXp(35, battleXp(0, 0))) == Form::Scavenger,
              "Reaching the threshold grants the next form");
static_assert(removeXp(100, battleXp(1, 1)) == 75, "A defeat deducts the matching XP reward");
static_assert(removeXp(70, battleXp(1, 2)) == 35 &&
              formForXp(removeXp(70, battleXp(1, 2))) == Form::Baby,
              "A defeat that crosses a threshold restores the previous form");
static_assert(formForXp(removeXp(85, battleXp(1, 1))) == Form::Scavenger,
              "Landing exactly on a threshold keeps that form");
static_assert(removeXp(0, battleXp(0, 0)) == 0, "XP cannot drop below zero");
static_assert(addXp(MAX_XP - 1, 35) == MAX_XP, "XP caps at the final threshold");
static_assert(idleXpFor(IDLE_XP_INTERVAL_MS - 1) == 0, "Idle XP requires a full interval");
static_assert(idleXpFor(IDLE_XP_INTERVAL_MS) == 1, "A full idle interval grants one XP");
