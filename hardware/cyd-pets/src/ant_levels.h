#pragma once

#include <stddef.h>
#include <stdint.h>

struct AntLevel {
  uint32_t minutes;
  const char *title;
  const char *skill;
  const char *quest;
};

constexpr AntLevel antLevels[] = {
    {0, "[Nest Worker]", "Scent Trail", "Carry a seed to the nest"},
    {30, "[Trail Finder]", "Trail Mark", "Mark a trail through clover"},
    {120, "[Pebble Porter]", "Strong Grip", "Clear pebbles from the trail"},
    {480, "[Seed Gatherer]", "Seed Sense", "Collect seeds before the rain"},
    {1440, "[Tunnel Scout]", "Low Light", "Scout the root tunnels"},
    {2160, "[Root Delver]", "Root Map", "Map the old oak roots"},
    {3600, "[Colony Guard]", "Alarm Scent", "Watch the eastern entrance"},
    {5760, "[Spore Keeper]", "Spore Craft", "Tend the mushroom beds"},
    {10080, "[Amber Warden]", "Amber Ward", "Guard the amber chamber"},
    {14400, "[Nest Marshal]", "Rally Trail", "Guide the workers home"},
    {20160, "[Crown Keeper]", "Colony Light", "Rest in the lantern chamber"},
};
constexpr size_t antMaxLevel = sizeof(antLevels) / sizeof(antLevels[0]);

inline size_t antLevelFor(uint32_t journeyMs) {
  size_t level = 1;
  while (level < antMaxLevel && journeyMs / 60000 >= antLevels[level].minutes) ++level;
  return level;
}

inline unsigned antLevelProgress(uint32_t journeyMs, size_t level) {
  if (level == antMaxLevel) return 100;
  const uint32_t start = antLevels[level - 1].minutes * 60000;
  const uint32_t span = antLevels[level].minutes * 60000 - start;
  return static_cast<unsigned>(100ULL * (journeyMs - start) / span);
}
