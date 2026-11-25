#pragma once

#include <TFT_eSPI.h>

namespace petScene {

constexpr int width = 160;
constexpr int height = 110;
constexpr uint16_t houseWall = 0xA4B2;

enum class Habitat { Camp, Tunnel, House };

inline void drawBackground(TFT_eSprite &frame, Habitat habitat) {
  switch (habitat) {
    case Habitat::Camp:
      frame.fillSprite(0x214A);
      frame.fillCircle(128, 17, 8, 0xE639);
      frame.fillTriangle(0, 63, 43, 22, 103, 63, 0x29AD);
      frame.fillTriangle(62, 63, 118, 31, 159, 63, 0x318D);
      frame.fillRect(0, 63, width, height - 63, 0x4A46);
      frame.fillTriangle(1, 79, 22, 44, 48, 79, 0x9B66);
      frame.fillTriangle(16, 79, 24, 61, 34, 79, 0x3964);
      frame.fillTriangle(117, 79, 140, 46, 159, 79, 0x8367);
      frame.fillTriangle(132, 79, 140, 61, 149, 79, 0x3964);
      frame.fillEllipse(138, 97, 17, 6, 0x6306);
      frame.fillTriangle(131, 97, 140, 80, 146, 97, 0xFA85);
      frame.fillTriangle(136, 97, 140, 89, 143, 97, 0xFDC8);
      break;
    case Habitat::Tunnel:
      frame.fillSprite(0x5A66);
      frame.fillEllipse(80, 65, 71, 57, 0x3944);
      frame.fillEllipse(80, 67, 59, 48, 0x20C2);
      frame.fillEllipse(80, 104, 78, 23, 0x7248);
      frame.drawLine(18, 9, 30, 27, 0x8B48);
      frame.drawLine(145, 14, 130, 31, 0x8B48);
      frame.fillEllipse(16, 89, 9, 5, 0xA4AB);
      frame.fillEllipse(142, 97, 11, 5, 0xA4AB);
      frame.fillEllipse(30, 103, 5, 3, 0x946A);
      break;
    case Habitat::House:
      frame.fillSprite(houseWall);
      frame.fillRect(0, 73, width, height - 73, 0x8B07);
      frame.drawFastHLine(0, 72, width, 0xD691);
      frame.fillRect(13, 12, 34, 32, 0x6A46);
      frame.fillRect(16, 15, 28, 26, 0x8E7A);
      frame.drawFastVLine(29, 15, 26, 0xD691);
      frame.drawFastHLine(16, 27, 28, 0xD691);
      frame.fillRect(119, 42, 34, 27, 0x6A46);
      frame.fillRect(122, 45, 28, 19, 0xC491);
      frame.fillCircle(144, 55, 2, 0xF6B4);
      frame.fillEllipse(80, 100, 57, 8, 0x9270);
      break;
  }
}

inline bool begin(TFT_eSprite &sprite) {
  sprite.setColorDepth(16);
  return sprite.createSprite(width, height) != nullptr;
}

template <typename Draw>
void draw(TFT_eSprite &sprite, int x, int y, Habitat habitat, Draw drawArt) {
  drawBackground(sprite, habitat);
  drawArt(sprite);
  sprite.pushSprite(x, y);
}

}  // namespace petScene
