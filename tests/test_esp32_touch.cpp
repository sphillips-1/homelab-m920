// Host-side tests for touch calibration and button geometry; no hardware access.
#include "../hardware/esp32-monitor/src/touch_controls.h"
#include <assert.h>
#include <limits>

static_assert(hitTouch(0, 204, 0) == TouchAction::Home, "Home tab starts at left edge");
static_assert(hitTouch(79, 239, 3) == TouchAction::Home, "Home tab right edge");
static_assert(hitTouch(80, 206, 0) == TouchAction::Feed, "Feed tab starts at 80");
static_assert(hitTouch(159, 239, 0) == TouchAction::Feed, "Feed tab right edge");
static_assert(hitTouch(160, 206, 0) == TouchAction::Play, "Play tab starts at 160");
static_assert(hitTouch(239, 239, 0) == TouchAction::Play, "Play tab right edge");
static_assert(hitTouch(240, 206, 0) == TouchAction::Metrics, "Metrics tab starts at 240");
static_assert(hitTouch(319, 239, 0) == TouchAction::Metrics, "Metrics tab includes screen edge");
static_assert(hitTouch(-1, 220, 0) == TouchAction::None, "Off-screen touches are rejected");
static_assert(hitTouch(320, 220, 0) == TouchAction::None, "Right overflow is rejected");
static_assert(hitTouch(160, 240, 0) == TouchAction::None, "Bottom overflow is rejected");
static_assert(hitTouch(160, 190, 0) == TouchAction::None, "Home caption is not an action");
static_assert(hitTouch(160, 190, 1) == TouchAction::Activate, "Feed action");
static_assert(hitTouch(160, 190, 2) == TouchAction::Activate, "Play action");
static_assert(hitTouch(160, 190, 3) == TouchAction::Calibrate, "Calibration action");
static_assert(hitTouch(160, 203, 1) == TouchAction::None, "Action and navigation do not overlap");

int main() {
  TouchCalibration cal{};
  TouchPoint normal[] = {{300, 300}, {3700, 300}, {300, 3700}};
  assert(calibrateTouch(normal, cal));
  TouchPoint center = mapTouch(cal, {2000, 2000});
  assert(center.x == 160 && center.y == 120);
  assert(confirmsCalibration(cal, {3700, 3700}));
  assert(!confirmsCalibration(cal, {2000, 2000}));

  TouchPoint mirroredSwapped[] = {{3700, 3700}, {3700, 300}, {300, 3700}};
  assert(calibrateTouch(mirroredSwapped, cal));
  center = mapTouch(cal, {2000, 2000});
  assert(center.x == 160 && center.y == 120);
  assert(confirmsCalibration(cal, {300, 300}));

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
