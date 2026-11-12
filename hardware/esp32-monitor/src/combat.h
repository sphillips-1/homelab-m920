#pragma once
#include "evolution.h"

// Each row corresponds to one progression stage, starting at level 1.
constexpr const char *OPPONENTS[][2] = {
    {"Cave Rat", "Mud Beetle"},
    {"Rock Crab", "Shield Spider"},
    {"Face-Eater Moth", "Cave Raptor"},
    {"Carn Wolf", "Hobgoblin Raider"},
    {"Gnoll Skirmisher", "Troll Guard"},
    {"Raskghar Hunter", "Armored Ogre"},
    {"Young Wyvern", "Minotaur Champion"},
    {"Wyvern Lord", "Adult Creler"},
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
