#pragma once

#include <Arduino.h>
#include <Wire.h>
#include "touch_controls.h"

namespace waveshareTouch {
namespace {
constexpr uint8_t address = 0x15;
constexpr int resetPin = 13;
constexpr int irqPin = 14;
portMUX_TYPE irqLock = portMUX_INITIALIZER_UNLOCKED;
volatile bool irqPending = false;

void IRAM_ATTR touchInterrupt() {
  portENTER_CRITICAL_ISR(&irqLock);
  irqPending = true;
  portEXIT_CRITICAL_ISR(&irqLock);
}

bool readRegisters(uint8_t reg, uint8_t *values, size_t count) {
  Wire.beginTransmission(address);
  Wire.write(reg);
  if (Wire.endTransmission(false) != 0 ||
      Wire.requestFrom(address, count, true) != count) return false;
  for (size_t i = 0; i < count; ++i) values[i] = Wire.read();
  return true;
}

bool writeRegister(uint8_t reg, uint8_t value) {
  Wire.beginTransmission(address);
  Wire.write(reg);
  Wire.write(value);
  return Wire.endTransmission() == 0;
}
}

inline bool begin() {
  if (!Wire.begin(11, 10, 100000)) return false;
  Wire.setTimeOut(10);
  pinMode(resetPin, OUTPUT);
  digitalWrite(resetPin, LOW);
  delay(10);
  digitalWrite(resetPin, HIGH);
  delay(50);
  uint8_t chipId;
  if (!readRegisters(0xA7, &chipId, 1) ||
      !writeRegister(0xFE, 1) || !writeRegister(0xFA, 0x60)) return false;
  pinMode(irqPin, INPUT_PULLUP);
  attachInterrupt(digitalPinToInterrupt(irqPin), touchInterrupt, FALLING);
  Serial.printf("Touch: CST816T ready, chip ID 0x%02X\n", chipId);
  return true;
}

inline bool read(TouchPoint &point) {
  static bool pressed = false;
  portENTER_CRITICAL(&irqLock);
  const bool pending = irqPending;
  irqPending = false;
  portEXIT_CRITICAL(&irqLock);

  // Continue sampling while held because the controller may omit release IRQs.
  if (!pending && !pressed) return false;
  pressed = false;
  uint8_t sample[5];
  if (!readRegisters(0x02, sample, sizeof(sample)) || !(sample[0] & 0x0f)) return false;
  const int x = ((sample[1] & 0x0f) << 8) | sample[2];
  const int y = ((sample[3] & 0x0f) << 8) | sample[4];
  if (x >= 240 || y >= 280) return false;
  // Use roughly the same raw coordinate range as the resistive touch target.
  point = {x * 16, y * 16};
  pressed = true;
  return true;
}
}
