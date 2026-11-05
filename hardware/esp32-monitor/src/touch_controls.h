#pragma once
#include <math.h>
#include <stdlib.h>

struct TouchPoint { int x, y; };
struct TouchCalibration { float a, b, c, d, e, f; };
static_assert(sizeof(TouchCalibration) == 24, "Stored touch calibration layout changed");

inline bool validCalibration(const TouchCalibration &v) {
  return isfinite(v.a) && isfinite(v.b) && isfinite(v.c) &&
      isfinite(v.d) && isfinite(v.e) && isfinite(v.f) &&
      fabsf(v.a) <= 1 && fabsf(v.b) <= 1 && fabsf(v.d) <= 1 && fabsf(v.e) <= 1 &&
      fabsf(v.c) <= 1000 && fabsf(v.f) <= 1000 && fabsf(v.a * v.e - v.b * v.d) > 0.00001f;
}

// Three raw points correspond to screen targets (24,24), (296,24), (24,216).
// The affine transform handles swapped, mirrored and slightly skewed axes.
inline bool calibrateTouch(const TouchPoint *raw, TouchCalibration &out) {
  float dx1 = raw[1].x - raw[0].x, dy1 = raw[1].y - raw[0].y;
  float dx2 = raw[2].x - raw[0].x, dy2 = raw[2].y - raw[0].y;
  float det = dx1 * dy2 - dx2 * dy1;
  if (fabsf(det) < 100000) return false;
  out.a = 272 * dy2 / det; out.b = -272 * dx2 / det;
  out.c = 24 - out.a * raw[0].x - out.b * raw[0].y;
  out.d = -192 * dy1 / det; out.e = 192 * dx1 / det;
  out.f = 24 - out.d * raw[0].x - out.e * raw[0].y;
  return validCalibration(out);
}

inline TouchPoint mapTouch(const TouchCalibration &v, TouchPoint raw) {
  return {static_cast<int>(roundf(v.a * raw.x + v.b * raw.y + v.c)),
          static_cast<int>(roundf(v.d * raw.x + v.e * raw.y + v.f))};
}
inline bool confirmsCalibration(const TouchCalibration &v, TouchPoint raw) {
  TouchPoint p = mapTouch(v, raw);
  return abs(p.x - 296) <= 24 && abs(p.y - 216) <= 24;
}

enum class TouchAction { None, Home, Feed, Play, Metrics, Activate, Calibrate };
constexpr TouchAction hitTouch(int x, int y, int page) {
  return x < 0 || x >= 320 || y < 0 || y >= 240 ? TouchAction::None :
      y >= 204 ? (x < 80 ? TouchAction::Home : x < 160 ? TouchAction::Feed :
                   x < 240 ? TouchAction::Play : TouchAction::Metrics) :
      (x >= 10 && x < 310 && y >= 174 && y < 202) ?
      (page == 1 || page == 2 ? TouchAction::Activate : page == 3 ? TouchAction::Calibrate : TouchAction::None) :
      TouchAction::None;
}
