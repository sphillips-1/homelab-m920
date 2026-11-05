// Host-side tests for touch calibration and swipe recognition; no hardware access.
#include "../hardware/esp32-monitor/src/touch_controls.h"
#include <assert.h>
#include <limits>

constexpr TouchStroke tap{{2000,2000}, {2000,2000}, {2000,2000}, 200, 20};
static_assert(isCalibrationTap(tap), "Stationary taps can calibrate");
constexpr TouchStroke drag{{3500,2000}, {500,2000}, {2000,2000}, 400, 3000};
static_assert(!isCalibrationTap(drag), "Swipes cannot advance calibration");
constexpr TouchStroke hold{{2000,2000}, {2000,2000}, {2000,2000}, 2200, 20};
static_assert(!isCalibrationTap(hold), "Long holds cannot advance calibration");

int main() {
  TouchCalibration cal{};
  TouchPoint normal[] = {{300, 300}, {3700, 300}, {300, 3700}};
  assert(calibrateTouch(normal, cal));
  TouchPoint center = mapTouch(cal, {2000, 2000});
  assert(center.x == 160 && center.y == 120);
  assert(confirmsCalibration(cal, {3700, 3700}));
  assert(!confirmsCalibration(cal, {2000, 2000}));

  assert(classifyGesture(cal, drag) == Gesture::Left);
  TouchStroke right{{500,2000}, {3500,2000}, {2000,2000}, 400, 3000};
  assert(classifyGesture(cal, right) == Gesture::Right);
  assert(classifyGesture(cal, tap) == Gesture::Tap);
  assert(classifyGesture(cal, hold) == Gesture::Hold);
  TouchStroke vertical{{2000,500}, {2000,3500}, {2000,2000}, 400, 3000};
  assert(classifyGesture(cal, vertical) == Gesture::None);
  TouchStroke diagonal{{3500,500}, {500,3500}, {2000,2000}, 400, 3000};
  assert(classifyGesture(cal, diagonal) == Gesture::None);
  TouchStroke shortDrag{{2000,2000}, {1500,2000}, {1750,2000}, 400, 500};
  assert(classifyGesture(cal, shortDrag) == Gesture::None);
  TouchStroke returned{{2000,2000}, {2000,2000}, {2000,2000}, 400, 1500};
  assert(classifyGesture(cal, returned) == Gesture::None);
  TouchStroke fast = drag;
  fast.durationMs = 79;
  assert(classifyGesture(cal, fast) == Gesture::None);
  TouchStroke slow = drag;
  slow.durationMs = 2501;
  assert(classifyGesture(cal, slow) == Gesture::None);
  TouchStroke movingHold = hold;
  movingHold.maxMotion = 251;
  assert(classifyGesture(cal, movingHold) == Gesture::None);
  TouchStroke outside{{-1000,2000}, {2000,2000}, {500,2000}, 400, 3000};
  assert(classifyGesture(cal, outside) == Gesture::None);

  TouchPoint mirroredSwapped[] = {{3700, 3700}, {3700, 300}, {300, 3700}};
  assert(calibrateTouch(mirroredSwapped, cal));
  center = mapTouch(cal, {2000, 2000});
  assert(center.x == 160 && center.y == 120);
  assert(confirmsCalibration(cal, {300, 300}));
  TouchStroke mirroredLeft{{2000,500}, {2000,3500}, {2000,2000}, 400, 3000};
  assert(classifyGesture(cal, mirroredLeft) == Gesture::Left);
  TouchStroke mirroredRight{{2000,3500}, {2000,500}, {2000,2000}, 400, 3000};
  assert(classifyGesture(cal, mirroredRight) == Gesture::Right);

  TouchPoint skewed[] = {{500, 400}, {3600, 550}, {650, 3600}};
  assert(calibrateTouch(skewed, cal));
  assert(confirmsCalibration(cal, {3750, 3750}));

  TouchPoint identical[] = {{300, 300}, {300, 300}, {300, 300}};
  assert(!calibrateTouch(identical, cal));
  TouchPoint collinear[] = {{300, 300}, {1500, 1500}, {3000, 3000}};
  assert(!calibrateTouch(collinear, cal));
  TouchPoint tiny[] = {{300, 300}, {310, 300}, {300, 310}};
  assert(!calibrateTouch(tiny, cal));
  cal = {};
  assert(!validCalibration(cal));
  cal.a = std::numeric_limits<float>::quiet_NaN();
  assert(!validCalibration(cal));
}
