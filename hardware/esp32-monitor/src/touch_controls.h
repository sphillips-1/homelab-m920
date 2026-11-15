#pragma once
#include <math.h>
#include <stdlib.h>
#include <stdint.h>

struct TouchPoint { int x, y; };
struct TouchCalibration { float a, b, c, d, e, f; };
static_assert(sizeof(TouchCalibration) == 24, "Stored touch calibration layout changed");

inline bool validCalibration(const TouchCalibration &v) {
  return isfinite(v.a) && isfinite(v.b) && isfinite(v.c) &&
      isfinite(v.d) && isfinite(v.e) && isfinite(v.f) &&
      fabsf(v.a) <= 1 && fabsf(v.b) <= 1 && fabsf(v.d) <= 1 && fabsf(v.e) <= 1 &&
      fabsf(v.c) <= 1000 && fabsf(v.f) <= 1000 && fabsf(v.a * v.e - v.b * v.d) > 0.00001f;
}

// Three raw points correspond to screen targets (24,24), (width - 24,24), (24,height - 24).
// The affine transform handles swapped, mirrored and slightly skewed axes.
inline bool calibrateTouch(const TouchPoint *raw, TouchCalibration &out, int width = 320, int height = 240) {
  float dx1 = raw[1].x - raw[0].x, dy1 = raw[1].y - raw[0].y;
  float dx2 = raw[2].x - raw[0].x, dy2 = raw[2].y - raw[0].y;
  float det = dx1 * dy2 - dx2 * dy1;
  if (fabsf(det) < 100000) return false;
  const int span = width - 48;
  out.a = span * dy2 / det; out.b = -span * dx2 / det;
  out.c = 24 - out.a * raw[0].x - out.b * raw[0].y;
  const int verticalSpan = height - 48;
  out.d = -verticalSpan * dy1 / det; out.e = verticalSpan * dx1 / det;
  out.f = 24 - out.d * raw[0].x - out.e * raw[0].y;
  return validCalibration(out);
}

inline TouchPoint mapTouch(const TouchCalibration &v, TouchPoint raw) {
  return {static_cast<int>(roundf(v.a * raw.x + v.b * raw.y + v.c)),
          static_cast<int>(roundf(v.d * raw.x + v.e * raw.y + v.f))};
}
inline bool confirmsCalibration(const TouchCalibration &v, TouchPoint raw, int width = 320, int height = 240) {
  TouchPoint p = mapTouch(v, raw);
  return abs(p.x - (width - 24)) <= 24 && abs(p.y - (height - 24)) <= 24;
}

struct TouchStroke {
  TouchPoint first, last, average;
  uint32_t durationMs;
  int maxMotion; // Largest raw displacement from the starting point.
};
enum class Gesture { None, Tap, Left, Right, Hold };
constexpr bool isCalibrationTap(const TouchStroke &stroke) {
  return stroke.durationMs >= 40 && stroke.durationMs <= 1500 && stroke.maxMotion <= 350;
}
inline bool nearScreen(TouchPoint p, int width = 320, int height = 240) {
  return p.x >= -12 && p.x <= width + 11 && p.y >= -12 && p.y <= height + 11;
}
inline Gesture classifyGesture(const TouchCalibration &cal, const TouchStroke &stroke, int width = 320, int height = 240) {
  TouchPoint first = mapTouch(cal, stroke.first), last = mapTouch(cal, stroke.last);
  if (!nearScreen(first, width, height) || !nearScreen(last, width, height)) return Gesture::None;
  int dx = last.x - first.x, dy = last.y - first.y;
  if (stroke.durationMs >= 80 && stroke.durationMs <= 2500 &&
      abs(dx) >= 70 && abs(dy) <= 40 && abs(dx) >= 2 * abs(dy))
    return dx < 0 ? Gesture::Left : Gesture::Right;
  if (stroke.durationMs >= 2000 && stroke.durationMs <= 5000 && stroke.maxMotion <= 250)
    return Gesture::Hold;
  return isCalibrationTap(stroke) ? Gesture::Tap : Gesture::None;
}
