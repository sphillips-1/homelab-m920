#pragma once

#include <stdint.h>

namespace cydPet {

class Egg {
 public:
  const char *label() const { return "unknown"; }

  bool needsRedraw(uint32_t now) const { return offsetAt(now) != drawnOffset; }

  int drawOffset(uint32_t now) {
    drawnOffset = offsetAt(now);
    return drawnOffset;
  }

 private:
  static int offsetAt(uint32_t now) {
    constexpr uint32_t intervalMs = 11000;
    constexpr uint32_t stepMs = 90;
    if (now < intervalMs) return 0;
    switch ((now % intervalMs) / stepMs) {
      case 0:
      case 2:
        return -3;
      case 1:
        return 3;
      default:
        return 0;
    }
  }

  int drawnOffset = 0;
};

}  // namespace cydPet
