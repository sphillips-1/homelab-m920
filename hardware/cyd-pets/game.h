#pragma once

#include <Arduino.h>
#include "../esp32-monitor/src/experience.h"

namespace cydPet {
constexpr uint32_t battleDurationMs = 3600;

struct Battle {
  const Opponent *opponent = nullptr;
  unsigned rank = 0;
  unsigned foeRank = 0;
  uint32_t started = 0;
  bool won = false;

  template <typename OpponentFor>
  void start(unsigned currentRank, unsigned forms, uint32_t now, OpponentFor opponentFor) {
    rank = currentRank;
    const auto first = firstOpponentRank(rank);
    foeRank = first + esp_random() % (lastOpponentRank(rank, forms) - first + 1);
    opponent = &opponentFor(foeRank);
    started = now;
    won = esp_random() % 100 < winChance(rank, foeRank);
  }

  uint32_t resultXp(uint32_t xp, uint32_t cap = MAX_XP) const {
    const uint32_t amount = battleXp(rank, foeRank);
    return won ? addXp(xp, amount, cap) : removeXp(xp, amount);
  }
};

class IdleProgress {
 public:
  uint32_t reward(uint32_t now, bool onPetScreen) {
    if (!onPetScreen) {
      active = false;
      return 0;
    }
    if (!active) {
      since = now;
      active = true;
    }
    const uint32_t xp = idleXpFor(now - since);
    since += xp * IDLE_XP_INTERVAL_MS;
    return xp;
  }

 private:
  uint32_t since = 0;
  bool active = false;
};
}
