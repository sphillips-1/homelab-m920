#pragma once
#include "evolution.h"

// Each row corresponds to one progression stage, starting at level 1.
enum class MonsterShape { Beast, Crawler, Winged, Biped };
struct Opponent { const char *name; MonsterShape shape; };
constexpr Opponent OPPONENTS[][2] = {
    {{"Cave Rat", MonsterShape::Beast}, {"Mud Beetle", MonsterShape::Crawler}},
    {{"Rock Crab", MonsterShape::Crawler}, {"Shield Spider", MonsterShape::Crawler}},
    {{"Face-Eater Moth", MonsterShape::Winged}, {"Cave Raptor", MonsterShape::Beast}},
    {{"Carn Wolf", MonsterShape::Beast}, {"Hobgoblin Raider", MonsterShape::Biped}},
    {{"Gnoll Skirmisher", MonsterShape::Biped}, {"Troll Guard", MonsterShape::Biped}},
    {{"Raskghar Hunter", MonsterShape::Beast}, {"Armored Ogre", MonsterShape::Biped}},
    {{"Young Wyvern", MonsterShape::Winged}, {"Minotaur Champion", MonsterShape::Biped}},
    {{"Wyvern Lord", MonsterShape::Winged}, {"Adult Creler", MonsterShape::Crawler}},
};
static_assert(sizeof(OPPONENTS) / sizeof(OPPONENTS[0]) == FORM_COUNT, "Each stage needs opponents");

constexpr unsigned firstOpponentRank(unsigned rank) { return rank ? rank - 1 : 0; }
constexpr unsigned lastOpponentRank(unsigned rank) { return rank + 1 < FORM_COUNT ? rank + 1 : rank; }
constexpr unsigned winChance(unsigned rank, unsigned foeRank) {
  return foeRank < rank ? 85 : foeRank == rank ? 65 : 40;
}

enum class FightOutcome { Reborn, Won, Evolved };
constexpr FightOutcome fightOutcome(unsigned rank, unsigned foeRank, unsigned roll) {
  return roll >= winChance(rank, foeRank) ? FightOutcome::Reborn :
      foeRank >= rank && rank + 1 < FORM_COUNT ? FightOutcome::Evolved : FightOutcome::Won;
}
constexpr uint32_t bankAfterFight(uint32_t bank, unsigned rank, FightOutcome outcome) {
  return outcome == FightOutcome::Reborn ? 0 : outcome == FightOutcome::Evolved ?
      MILESTONES[rank + 1].thresholdMs : bank;
}
