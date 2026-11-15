#pragma once

#include <Arduino.h>
#include <Wire.h>
#include "touch_controls.h"

namespace waveshareOrientation {
constexpr int nativeWidth = 240;
constexpr int nativeHeight = 280;
constexpr int noRotation = -1;

constexpr TouchPoint rotateTouch(TouchPoint point, int rotation) {
  return rotation == 1 ? TouchPoint{point.y, nativeWidth - 1 - point.x} :
      rotation == 2 ? TouchPoint{nativeWidth - 1 - point.x, nativeHeight - 1 - point.y} :
      rotation == 3 ? TouchPoint{nativeHeight - 1 - point.y, point.x} : point;
}

static_assert(rotateTouch({0, 0}, 1).y == 239, "Landscape touch follows the TFT");
static_assert(rotateTouch({0, 0}, 2).x == 239 && rotateTouch({0, 0}, 2).y == 279,
              "Inverted portrait touch follows the TFT");
static_assert(rotateTouch({0, 0}, 3).x == 279, "Inverted landscape touch follows the TFT");

namespace {
constexpr uint8_t address = 0x6B;

bool readRegisters(uint8_t reg, uint8_t *data, size_t length) {
  Wire.beginTransmission(address);
  Wire.write(reg);
  if (Wire.endTransmission(false) != 0 ||
      Wire.requestFrom(address, length, true) != length) return false;
  for (size_t i = 0; i < length; ++i) data[i] = Wire.read();
  return true;
}

bool writeRegister(uint8_t reg, uint8_t value) {
  Wire.beginTransmission(address);
  Wire.write(reg);
  Wire.write(value);
  return Wire.endTransmission() == 0;
}

int axis(const uint8_t *data) {
  return static_cast<int16_t>(data[0] | (data[1] << 8));
}
}

inline bool begin() {
  uint8_t id;
  return readRegisters(0x00, &id, 1) && id == 0x05 &&
      writeRegister(0x02, 0x40) && // Auto-increment registers during reads.
      writeRegister(0x03, 0x0E) && // Accelerometer: +/-2 g, 11 Hz.
      writeRegister(0x08, 0x01);
}

inline int sample(uint32_t now) {
  static uint32_t lastSample = 0, stableSince = 0;
  static int candidate = noRotation, settled = noRotation;
  if (now - lastSample < 100) return settled;
  lastSample = now;

  int next = noRotation;
  uint8_t data[6];
  if (readRegisters(0x35, data, sizeof(data))) {
    // Map the chip's axes to the display's native right and down directions.
    const int x = axis(data + 2), y = -axis(data), z = axis(data + 4);
    const int ax = abs(x), ay = abs(y);
    // At +/-2 g the scale is 16384 counts per g. Ignore flat and diagonal poses.
    if (abs(z) < 10000) {
      if (ax >= 11000 && ax * 2 > ay * 3) next = x > 0 ? 1 : 3;
      else if (ay >= 11000 && ay * 2 > ax * 3) next = y < 0 ? 0 : 2;
    }
  }
  if (candidate != next) {
    candidate = next;
    stableSince = now;
    settled = noRotation;
  }
  if (candidate != noRotation && now - stableSince >= 400) settled = candidate;
  return settled;
}
}
