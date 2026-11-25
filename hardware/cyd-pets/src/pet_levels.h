#pragma once

#include <stddef.h>
#include <stdint.h>

struct PetLevel {
  uint32_t minutes;
  const char *title;
  const char *skill;
  const char *quest;
};

constexpr PetLevel levels[] = {
#ifdef CYD_PET_CAT
    {0, "[Trail Kitten]", "Trail Sense", "Find the Briarwood trail"},
    {30, "[Moth Tracker]", "Softstep", "Follow the moths to Fern Hollow"},
    {120, "[Creek Runner]", "Surefoot", "Cross the flooded stepping stones"},
    {480, "[Briar Forager]", "Forager", "Trade berries for a lantern"},
    {1440, "[Lantern Scout]", "Lantern Ward", "Carry a lantern into Hollowmere"},
    {2160, "[Mist Prowler]", "Night Eyes", "Find the tower in the mist"},
    {3600, "[Bridge Guard]", "Bridgekeeper", "Guide travelers across Moonbridge"},
    {5760, "[Sky Cartographer]", "Wayfinder", "Chart a route to Starfall Pass"},
    {10080, "[Starwarden]", "Starlight Ward", "Light the beacon at Starfall Pass"},
    {14400, "[Dawn Marshal]", "Skywatch", "Guide the night caravan home"},
    {20160, "[Hearth Sentinel]", "Homeward Light", "The road is safe. Rest by the fire."},
#else
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
#endif
};
constexpr size_t maxLevel = sizeof(levels) / sizeof(levels[0]);

inline size_t levelFor(uint32_t journeyMs) {
  size_t level = 1;
  while (level < maxLevel && journeyMs / 60000 >= levels[level].minutes) ++level;
  return level;
}

inline unsigned levelProgress(uint32_t journeyMs, size_t level) {
  if (level == maxLevel) return 100;
  const uint32_t start = levels[level - 1].minutes * 60000;
  const uint32_t span = levels[level].minutes * 60000 - start;
  return static_cast<unsigned>(100ULL * (journeyMs - start) / span);
}
