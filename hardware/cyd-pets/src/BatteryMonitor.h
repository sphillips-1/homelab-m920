#pragma once

#include <Arduino.h>

namespace battery {
// Set these only after verifying the actual sensing circuit and GPIOs.
constexpr int batteryAdcPin = -1;
constexpr int chargeStatusPin = -1;
constexpr int batteryDividerRatio = 2;
constexpr int chargeActiveLevel = LOW;

enum class ChargeState { Unknown, Charging, Idle };

inline int batteryPercent() {
  if (batteryAdcPin < 0) return -1;

  uint32_t sum = 0;
  constexpr int sampleCount = 16;
  for (int sample = 0; sample < sampleCount; ++sample) {
    sum += analogReadMilliVolts(batteryAdcPin);
    delay(2);
  }
  const int voltage = sum * batteryDividerRatio / sampleCount;
  if (voltage < 2800 || voltage > 4300) return -1;

  // Approximate single-cell LiPo curve. Load and charging affect voltage.
  constexpr int millivolts[] = {3300, 3600, 3700, 3800, 3900, 4000, 4200};
  constexpr int percent[] = {0, 10, 25, 50, 70, 85, 100};
  if (voltage <= millivolts[0]) return 0;
  for (size_t i = 1; i < sizeof(millivolts) / sizeof(millivolts[0]); ++i) {
    if (voltage <= millivolts[i]) {
      return map(voltage, millivolts[i - 1], millivolts[i], percent[i - 1], percent[i]);
    }
  }
  return 100;
}

inline ChargeState chargeState() {
  if (chargeStatusPin < 0) return ChargeState::Unknown;
  return digitalRead(chargeStatusPin) == chargeActiveLevel
             ? ChargeState::Charging
             : ChargeState::Idle;
}

inline void begin() {
  if (batteryAdcPin >= 0) analogSetPinAttenuation(batteryAdcPin, ADC_11db);
  if (chargeStatusPin >= 0) pinMode(chargeStatusPin, INPUT);
}
}
