#pragma once

#include "scene_art.h"
#include "virtual_pet.h"

namespace virtualPet {

inline void draw(TFT_eSprite &sprite, bool ant, unsigned rank, uint16_t bg, uint32_t now,
                 bool defeated, uint32_t revealElapsed) {
  sprite.fillSprite(bg);
  const uint16_t color = (ant ? antStages : catStages)[rank].color;
  const int bob = (now / 250) % 2 * 2;
  const int prop = (now / 160) % 5;
  const bool revealing = revealElapsed < revealMs;
  const bool hidden = revealing && revealElapsed < revealMs / 2;
  const int y = 59 + bob + (defeated ? 13 : 0) -
      (revealing && !hidden ? (revealMs - revealElapsed) / 35 : 0);
  const bool blink = defeated || now % 3000 < 150;
  if (ant) {
    sprite.fillEllipse(80, 98, 65, 7, 0x6266);
    if (hidden) {
      sprite.fillEllipse(81, 98, 20 + prop, 5, TFT_BLACK);
      sprite.fillCircle(66 - prop * 2, 93 - prop, 2, TFT_ORANGE);
      sprite.fillCircle(96 + prop * 2, 93 - prop, 2, TFT_ORANGE);
      return;
    }
    for (int leg = 0; leg < 3; ++leg) {
      const int x = 56 + leg * 12;
      sprite.drawLine(x, y + 3, x - 9, y + 17, color);
      sprite.drawLine(x - 9, y + 17, x - 15 + bob, y + 28, color);
      sprite.drawLine(x, y + 6, x + 10, y + 18, color);
      sprite.drawLine(x + 10, y + 18, x + 17 - bob, y + 27, color);
    }
    sprite.fillEllipse(42, y - 3, 23 + (rank == 9 ? 5 : 0), 15, color);
    sprite.fillEllipse(68, y + 1, 13, 10, color);
    sprite.fillEllipse(94, y - 5, rank == 4 ? 22 : 16, 14, color);
    const int antenna = rank == 2 || rank == 10 ? 24 : 14;
    sprite.drawLine(90, y - 15, 79, y - 15 - antenna, color);
    sprite.drawLine(98, y - 15, 109 + prop, y - 15 - antenna, color);
    sprite.fillCircle(109 + prop, y - 15 - antenna, 2, color);
    sprite.fillRect(98, y - 10, 6, blink ? 2 : 6, TFT_BLACK);
    sprite.drawLine(104, y + 1, 117, y - 3, color);
    sprite.drawLine(103, y + 5, 117, y + 8, color);
    switch (rank) {
      case 1:
        sprite.fillTriangle(105, y - 1, 126, y - 9, 116, y + 7, TFT_ORANGE);
        sprite.fillCircle(126 + prop, 92 - prop, 5, TFT_LIGHTGREY);
        break;
      case 2:
        for (int dot = 0; dot < 5; ++dot)
          sprite.drawPixel(119 + dot * 5, 94 - (dot + prop) % 4, TFT_YELLOW);
        break;
      case 3:
      case 8: {
        const int base = rank == 3 ? y - 12 : 93;
        for (int i = 0; i < 3; ++i) {
          const int x = (rank == 3 ? 31 : 104) + i * 10;
          sprite.fillRect(x - 1, base - 10, 3, 10, TFT_WHITE);
          sprite.fillEllipse(x, base - 11, 5 + prop % 2, 3, color);
        }
        break;
      }
      case 4:
        sprite.drawEllipse(94, y - 5, 19, 11, TFT_YELLOW);
        break;
      case 5:
        sprite.fillCircle(39, y - 4, 10, TFT_ORANGE);
        sprite.drawCircle(39, y - 4, 3 + prop * 2, TFT_WHITE);
        sprite.fillEllipse(20, 90, 6, 3, TFT_ORANGE);
        break;
      case 6:
        sprite.fillTriangle(106, y + 1, 128, y - 9, 119, y + 9, TFT_CYAN);
        sprite.fillTriangle(120, 94, 130, 73 + prop, 139, 94, TFT_CYAN);
        break;
      case 7:
        sprite.fillRect(107, y + 10, 28, 18, TFT_YELLOW);
        sprite.drawLine(110, y + 15, 127 + prop, y + 23, TFT_MAROON);
        sprite.fillCircle(127 + prop, y + 23, 2, TFT_RED);
        break;
      case 9:
        for (int i = 0; i < 3; ++i)
          sprite.fillRoundRect(23 + i * 12, y - 13, 11, 17, 3, TFT_DARKGREY);
        sprite.fillRect(125, 68 - prop * 2, 17, 18, TFT_LIGHTGREY);
        break;
      case 10:
        sprite.fillCircle(79, y - 39, 3, TFT_CYAN);
        sprite.fillCircle(109 + prop, y - 39, 3, TFT_CYAN);
        for (int i = 0; i < 3; ++i)
          sprite.fillEllipse(20 + i * 12, 95 - (i + prop) % 3, 5, 3, TFT_ORANGE);
        break;
    }
  } else {
    sprite.fillEllipse(80, 98, 61, 6, 0x632D);
    if (!hidden) {
      sprite.drawCircle(48, y + 2 - prop, 14, color);
      sprite.fillEllipse(70, y + 14, 29, 21, color);
      sprite.fillEllipse(96, y - 4, 22, 17, color);
      sprite.fillTriangle(78, y - 11, 79, y - 32, 92, y - 16, color);
      sprite.fillTriangle(102, y - 12, 114, y - 30, 115, y - 8, color);
      sprite.fillEllipse(89, y + 31, 11, 6, color);
      sprite.fillRect(89, y - 8, 3, blink ? 1 : 6, TFT_BLACK);
      sprite.fillRect(105, y - 8, 3, blink ? 1 : 6, TFT_BLACK);
      sprite.fillCircle(99, y, 2, TFT_PINK);
      sprite.drawLine(95, y + 3, 81, y + 4, rank == 8 ? TFT_CYAN : TFT_WHITE);
      sprite.drawLine(102, y + 3, 118 + prop, y + 4, rank == 8 ? TFT_CYAN : TFT_WHITE);
    }
    if (rank == 0 || revealing) {
      sprite.fillRect(43, 79, 72, 20, 0xCC08);
      sprite.drawFastHLine(43, 79 - (hidden ? prop : 0), 72, TFT_YELLOW);
    }
    if (hidden) return;
    switch (rank) {
      case 1:
        sprite.fillRoundRect(112 + prop, y + 10, 15, 7, 3, TFT_SKYBLUE);
        sprite.fillRoundRect(122 + prop, y + 6, 7, 11, 2, TFT_SKYBLUE);
        break;
      case 2:
        sprite.fillRoundRect(41, y + 5, 70, 31, 10, TFT_PURPLE);
        sprite.drawFastHLine(52, y + 20 - prop, 45, TFT_MAGENTA);
        break;
      case 3:
        sprite.fillRect(23 + prop, 26, 12, 62, TFT_RED);
        sprite.drawFastVLine(26 + prop, 27, 59, TFT_PINK);
        break;
      case 4:
        sprite.drawFastHLine(79, y + 11, 30, TFT_MAROON);
        sprite.fillCircle(97 + prop / 2, y + 17, 5, TFT_YELLOW);
        break;
      case 5:
        sprite.fillTriangle(46, y + 29, 80, y + 9, 75, y + 26, TFT_BLUE);
        sprite.drawCircle(118 + prop, y + 15, 6, TFT_WHITE);
        sprite.drawLine(122 + prop, y + 20, 129 + prop, y + 27, TFT_WHITE);
        break;
      case 6:
        sprite.fillTriangle(30, 100, 81, 76, 127, 100, TFT_DARKGREY);
        sprite.fillCircle(128 - prop, 31, 7, TFT_YELLOW);
        sprite.fillCircle(131 - prop, 29, 6, bg);
        break;
      case 7:
        sprite.fillRoundRect(34, 85, 94, 11, 5, TFT_PURPLE);
        sprite.fillRoundRect(43, 93, 78, 10, 5, TFT_MAGENTA);
        break;
      case 8:
        sprite.drawCircle(120 + prop, y + 4, 3 + prop, TFT_CYAN);
        break;
      case 9:
        sprite.fillCircle(130 + prop, y - 13, 4, TFT_YELLOW);
        sprite.drawLine(117, y - 8, 130 + prop, y - 13, TFT_ORANGE);
        break;
      case 10:
        sprite.fillEllipse(80, 92, 49, 10, TFT_DARKGREY);
        if (prop < 3)
          sprite.fillTriangle(91, 93, 84, 107, 104, 93, TFT_YELLOW);
        break;
    }
  }
}

#ifdef SHELF_PET_CAT
inline void drawToy(TFT_eSprite &sprite, unsigned rank, uint32_t elapsed, uint16_t bg) {
  sprite.fillSprite(bg);
  const int x = 99 + (elapsed / 80) % 10 - (sceneArt::clash(elapsed) ? 12 : 0);
  const int y = 61 - (elapsed / 75) % 14;
  if (rank < 2) {
    sprite.fillRoundRect(x - 6, y - 10, 12, 23, 3, TFT_SKYBLUE);
    sprite.fillRoundRect(x - 6, y + 5, 21, 9, 4, TFT_SKYBLUE);
    sprite.fillRect(x - 6, y - 8, 12, 3, TFT_WHITE);
    return;
  }
  switch (catStages[rank].opponent.shape) {
    case MonsterShape::Beast:
      sprite.fillEllipse(x, y + 8, 14, 9, TFT_LIGHTGREY);
      sprite.fillCircle(x - 8, y + 1, 5, TFT_PINK);
      sprite.fillCircle(x - 12, y + 6, 2, TFT_BLACK);
      sprite.drawLine(x + 11, y + 10, x + 23, y + 5, TFT_PINK);
      break;
    case MonsterShape::Crawler:
      sprite.fillCircle(x, y + 8, 13, TFT_MAGENTA);
      sprite.drawCircle(x, y + 8, 8, TFT_WHITE);
      break;
    case MonsterShape::Biped:
      sprite.drawLine(x - 11, y + 30, x + 12, y - 9, TFT_ORANGE);
      sprite.fillEllipse(x + 12, y - 9, 9, 5, TFT_PINK);
      break;
    case MonsterShape::Winged:
      sprite.fillTriangle(x - 15, y, x + 14, y, x, y + 16, TFT_YELLOW);
      sprite.fillTriangle(x - 15, y + 10, x + 14, y + 10, x, y - 8, TFT_YELLOW);
      break;
  }
}
#endif

}  // namespace virtualPet
