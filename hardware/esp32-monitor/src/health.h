#pragma once

enum class Mood { Healthy, Busy, Warning, Critical, Unknown, Offline };
struct Health { Mood mood; const char *reason; };
// Negative readings mean unavailable. Independent of Arduino for testing.
struct Readings {
  float cpu = -1, ram = -1, temp = -1, root = -1, media = -1;
  int running = -1, total = -1, unhealthy = -1;
};
// One expression permits compile-time threshold regression tests on the ESP toolchain.
constexpr Health assess(const Readings &r, bool online) {
  return !online ? Health{Mood::Offline, "Feed unavailable"}
    : r.unhealthy > 0 ? Health{Mood::Critical, "Unhealthy containers"}
    : r.temp >= 85 ? Health{Mood::Critical, "CPU too hot"}
    : r.root >= 95 ? Health{Mood::Critical, "System disk nearly full"}
    : r.media >= 95 ? Health{Mood::Critical, "Media disk nearly full"}
    : r.ram >= 95 ? Health{Mood::Critical, "Memory nearly full"}
    : r.temp >= 70 ? Health{Mood::Warning, "CPU running warm"}
    : r.root >= 85 ? Health{Mood::Warning, "System disk filling"}
    : r.media >= 85 ? Health{Mood::Warning, "Media disk filling"}
    : r.ram >= 85 ? Health{Mood::Warning, "Memory running high"}
    // Stopped containers may be intentional. Keep counts visible without an alarm.
    : (r.cpu < 0 || r.ram < 0 || r.temp < 0 || r.root < 0 || r.media < 0 ||
       r.running < 0 || r.total < 0 || r.unhealthy < 0)
        ? Health{Mood::Unknown, "Some metrics unknown"}
    : r.cpu >= 85 ? Health{Mood::Busy, "Working hard"}
    : Health{Mood::Healthy, "Homelab looking good"};
}
