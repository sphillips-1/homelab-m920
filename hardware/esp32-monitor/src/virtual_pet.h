#pragma once

#include "experience.h"

namespace virtualPet {

constexpr unsigned formCount = 11;
constexpr uint32_t finalXp = 3200;
constexpr uint32_t revealMs = 1400;

struct Stage {
  const char *name;
  uint16_t color;
  Opponent opponent;
};

constexpr Stage antStages[] = {
    {"Hatchling Ant", 0xF555, {"Pill Bug", MonsterShape::Crawler}},
    {"Pebblejaw", 0xEB08, {"Mud Beetle", MonsterShape::Crawler}},
    {"Trailnose", 0xFC4D, {"Root Cricket", MonsterShape::Crawler}},
    {"Sporeback", 0xD35F, {"Spore Moth", MonsterShape::Winged}},
    {"Shieldhead", 0xA50D, {"Bark Roach", MonsterShape::Crawler}},
    {"Drummer", 0xF9E7, {"Cave Cricket", MonsterShape::Crawler}},
    {"Deepdrill", 0x5E7F, {"Crystal Beetle", MonsterShape::Crawler}},
    {"Mapweaver", 0xBCF7, {"Thread Spider", MonsterShape::Crawler}},
    {"Lantern Gardener", 0xAFE2, {"Lantern Moth", MonsterShape::Winged}},
    {"Gatekeeper", 0xBDF7, {"Stone Scarab", MonsterShape::Crawler}},
    {"Colony Conductor", 0xFE65, {"Crown Beetle", MonsterShape::Crawler}},
};
constexpr Stage catStages[] = {
    {"Pocket Kitten", 0xFD8E, {"Runaway Sock", MonsterShape::Beast}},
    {"Sockstalker", 0xE489, {"Bouncy Sock", MonsterShape::Beast}},
    {"Blanket Burrito", 0xFD8E, {"Yarn Ball", MonsterShape::Crawler}},
    {"Curtain Climber", 0xDD2B, {"Ribbon", MonsterShape::Biped}},
    {"Bellpaw", 0xF76D, {"Jingle Ball", MonsterShape::Crawler}},
    {"Whisker Detective", 0xC618, {"Wind-Up Mouse", MonsterShape::Beast}},
    {"Rooftop Rover", 0xF52B, {"Paper Bird", MonsterShape::Winged}},
    {"Pillow Fort Cat", 0xDE9F, {"Feather Wand", MonsterShape::Biped}},
    {"Moonlight Sleuth", 0x9D7F, {"Glow Mouse", MonsterShape::Beast}},
    {"Comet Pouncer", 0xEF54, {"Comet Toy", MonsterShape::Winged}},
    {"Thunderpurr", 0xB5BF, {"Storm Star", MonsterShape::Winged}},
};
#ifdef SHELF_PET_ANT
constexpr char title[] = "COLONY ANT";
constexpr char action[] = "CHALLENGE!";
constexpr char saveNamespace[] = "colony-ant";
constexpr auto &stages = antStages;
#elif defined(SHELF_PET_CAT)
constexpr char title[] = "WINDOWSILL CAT";
constexpr char action[] = "POUNCE!";
constexpr char saveNamespace[] = "windowsill-cat";
constexpr auto &stages = catStages;
#endif

static_assert(sizeof(antStages) / sizeof(antStages[0]) == formCount &&
              sizeof(catStages) / sizeof(catStages[0]) == formCount, "Each pet needs ten evolutions");
constexpr uint32_t threshold(unsigned rank) {
  return rank < FORM_COUNT ? XP_THRESHOLDS[rank] : rank == FORM_COUNT ? 2500 : finalXp;
}
constexpr unsigned rankFor(uint32_t xp, unsigned rank = formCount - 1) {
  return xp >= threshold(rank) ? rank : rankFor(xp, rank - 1);
}
constexpr bool validThresholds(unsigned rank = formCount - 1) {
  return rank == 0 ? rankFor(0) == 0 :
      rankFor(threshold(rank)) == rank && rankFor(threshold(rank) - 1) == rank - 1 &&
      validThresholds(rank - 1);
}
static_assert(validThresholds(), "Every evolution must begin at its own XP threshold");
static_assert(lastOpponentRank(9, formCount) == 10 && lastOpponentRank(10, formCount) == 10,
              "Final forms only encounter opponents in the roster");

}  // namespace virtualPet
