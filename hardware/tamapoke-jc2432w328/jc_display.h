#pragma once

#include <Arduino_GFX_Library.h>
#include <TFT_eSPI.h>
#include <Wire.h>

class JcDisplay : public Arduino_GFX {
public:
  JcDisplay() : Arduino_GFX(LCD_WIDTH, LCD_HEIGHT) {}

  bool begin(int32_t) override {
    pixels = static_cast<uint16_t *>(calloc(side * side, sizeof(uint16_t)));
    if (!pixels) return false;
    panel.init();
    panel.setRotation(1);
    panel.fillScreen(TFT_BLACK);
    panel.setSwapBytes(true);
    return true;
  }

  void writePixelPreclipped(int16_t x, int16_t y, uint16_t color) override {
    pixels[(y / 2) * side + x / 2] = color;
  }

  void flush() override {
    panel.pushImage(left, top, side, side, pixels);
  }

  int16_t touchPoint(int16_t *x, int16_t *y) {
#if defined(JC_TOUCH_RESISTIVE)
    uint16_t rawX, rawY;
    if (panel.getTouchRawZ() < 350) return 0;
    panel.getTouchRaw(&rawX, &rawY);
    const int px = map(rawY, 250, 3850, 0, panelWidth - 1);
    const int py = map(rawX, 3850, 250, 0, panelHeight - 1);
#else
    constexpr uint8_t address = 0x15;
    Wire.beginTransmission(address);
    Wire.write(0x02);
    if (Wire.endTransmission(false) || Wire.requestFrom(address, uint8_t{5}) != 5) return 0;
    const uint8_t fingers = Wire.read();
    const uint8_t xHigh = Wire.read();
    const uint8_t xLow = Wire.read();
    const uint8_t yHigh = Wire.read();
    const uint8_t yLow = Wire.read();
    if ((fingers & 0x0f) == 0) return 0;
    const int px = ((yHigh & 0x0f) << 8) | yLow;
    const int py = panelHeight - 1 - (((xHigh & 0x0f) << 8) | xLow);
#endif
    if (px < left || px >= left + side || py < top || py >= top + side) return 0;
    *x = 2 * (px - left);
    *y = 2 * (py - top);
    return 1;
  }

private:
  static constexpr int side = LCD_WIDTH / 2;
  static constexpr int panelWidth = 320;
  static constexpr int panelHeight = 240;
  static constexpr int left = (panelWidth - side) / 2;
  static constexpr int top = (panelHeight - side) / 2;
  TFT_eSPI panel;
  uint16_t *pixels = nullptr;
};
