#pragma once
#include <TFT_eSPI.h>
#include "combat.h"

namespace sceneArt {
inline void goblin(TFT_eSprite &pet, Form form, uint16_t bg, int bob,
                   bool defeated = false, bool concerned = false, bool uncertain = false, int stride = 0) {
  pet.fillSprite(bg);
  const bool small = form < Form::Adult;
  const bool hob = form >= Form::Hobgoblin;
  int y = (small ? 32 : hob ? 17 : 22) + bob;
  uint16_t skin = hob ? TFT_RED : TFT_GREEN;
  uint16_t cloth = hob ? 0x3186 : small ? 0xE6FA : 0x92A8;
  int width = small ? 64 : hob ? 64 : 56;
  int left = 80 - width / 2;
  int headHeight = small ? 42 : 38;
  pet.fillEllipse(80, 99, 46, 5, 0x18C3);
  pet.fillTriangle(24, y + 5, left + 9, y + 14, left, y + 31, skin);
  pet.fillTriangle(136, y + 5, 151 - left, y + 14, 160 - left, y + 31, skin);
  pet.fillRect(left, y, width, headHeight, skin);
  pet.fillRect(left - 6, y + 10, width + 12, 23, skin);
  pet.fillRect(56, y + headHeight, 48, small ? 15 : 33, cloth);
  pet.fillRect(49, y + (small ? 57 : 71) + stride, 22, 7, skin);
  pet.fillRect(89, y + (small ? 57 : 71) - stride, 22, 7, skin);
  if (!small) {
    pet.fillRect(45, y + 42, 11, 23, skin);
    pet.fillRect(104, y + 42, 11, 23, skin);
    pet.fillRect(54, y + 37, 52, 6, hob ? 0xBDF7 : TFT_ORANGE);
    pet.fillRect(56, y + 61, 48, 5, 0x6204);
    pet.fillRect(76, y + 60, 8, 7, TFT_YELLOW);
  }
  if (hob) {
    const uint16_t armor = form >= Form::GoblinLord ? 0x3ACB : 0xBDF7;
    if (form == Form::GoblinKing) {
      pet.fillRect(left - 1, y - 6, width + 2, 10, TFT_GOLD);
      for (int x = 58; x <= 102; x += 22) {
        pet.fillTriangle(x - 9, y - 5, x + 9, y - 5, x, y - 16, TFT_GOLD);
      }
      pet.fillRect(77, y - 5, 7, 6, TFT_RED);
    } else {
      pet.fillRect(left - 1, y - 5, width + 2, 10, armor);
      pet.fillRect(75, y - 12, 10, 9, TFT_RED);
    }
    pet.fillRect(43, y + 39, 18, 9, armor);
    pet.fillRect(99, y + 39, 18, 9, armor);
  } else if (small) {
    pet.fillRect(71, y - 4, 6, 7, 0x4C63);
  }
  if (form == Form::Scavenger || form == Form::Adult) {
    // Patchwork satchel and the first scavenged tool.
    pet.drawLine(62, y + 39, 101, y + 54, 0x6204);
    pet.fillRoundRect(97, y + 42, 21, 16, 3, 0xA344);
    pet.fillRect(103, y + 45, 8, 5, TFT_ORANGE);
    pet.drawLine(114, y + 48, 124, y + 36, 0xBDF7);
    pet.fillCircle(124, y + 35, 3, 0xBDF7);
  } else if (form == Form::Tactician || form == Form::Hobgoblin) {
    // A folded map and a crossbow carry over when the Tactician grows into a Hob.
    pet.fillRect(24, y + 47, 23, 18, 0xE6D0);
    pet.drawLine(31, y + 49, 31, y + 62, 0xA344);
    pet.drawLine(39, y + 49, 39, y + 62, 0xA344);
    pet.fillRect(123, y + 42, 5, 28, 0xA344);
    pet.drawLine(108, y + 52, 125, y + 43, TFT_YELLOW);
    pet.drawLine(125, y + 43, 143, y + 52, TFT_YELLOW);
    pet.drawFastHLine(108, y + 52, 36, 0xDEFB);
  } else if (form >= Form::Chieftain) {
    pet.fillRect(124, 6, 4, 84, 0xA344);
    pet.fillTriangle(128, 8, 156, 8, 128, 27, TFT_RED);
    if (form >= Form::GreatChieftain) {
      pet.fillTriangle(128, 24, 152, 24, 128, 41, TFT_GOLD);
      pet.fillTriangle(128, 39, 148, 39, 128, 54, TFT_CYAN);
      pet.fillTriangle(43, y + 48, 60, y + 43, 41, y + 73, 0x3ACB);
      pet.fillTriangle(117, y + 48, 100, y + 43, 119, y + 73, 0x3ACB);
    }
    if (form >= Form::GoblinLord) {
      const int flame = 4 + (millis() / 500) % 2;
      pet.fillTriangle(72, y + 58, 88, y + 58, 80, y + 43 - flame, TFT_GREEN);
      pet.fillCircle(80, y + 54, 3, TFT_YELLOW);
    }
  }
  bool blink = (millis() / 500) % 9 == 0;
  for (int eye = 56; eye <= 90; eye += 34) {
    if (defeated) {
      for (int stroke = 0; stroke < 3; ++stroke) {
        pet.drawLine(eye, y + 14 + stroke, eye + 13, y + 24 + stroke, TFT_BLACK);
        pet.drawLine(eye, y + 24 + stroke, eye + 13, y + 14 + stroke, TFT_BLACK);
      }
    } else {
      pet.fillRect(eye, y + 15, 14, blink ? 3 : 10, TFT_BLACK);
    }
  }
  if (defeated) {
    pet.fillRect(72, y + 32, 16, 3, TFT_BLACK);
  } else if (concerned) {
    pet.drawLine(55, y + 8, 70, y + 12, TFT_BLACK);
    pet.drawLine(90, y + 12, 105, y + 8, TFT_BLACK);
    pet.drawLine(70, y + 34, 80, y + 29, TFT_BLACK);
    pet.drawLine(80, y + 29, 90, y + 34, TFT_BLACK);
  } else if (uncertain) {
    pet.fillRect(72, y + 32, 16, 3, TFT_BLACK);
  } else {
    pet.fillRect(68, y + 30, 24, 4, TFT_BLACK);
    pet.fillRect(72, y + 34, 16, 4, TFT_BLACK);
    pet.fillRect(70, y + 30, 4, 5, TFT_WHITE);
  }
  if (hob) {
    pet.fillTriangle(66, y + 35, 71, y + 35, 68, y + 28, TFT_WHITE);
    pet.fillTriangle(89, y + 35, 94, y + 35, 92, y + 28, TFT_WHITE);
  }
}

inline void patrol(TFT_eSprite &pet, Form form, uint16_t bg, uint32_t elapsed, bool walking) {
  const bool step = (elapsed / (walking ? 120 : 500)) % 2;
  goblin(pet, form, bg, step ? 2 : 0, false, false, false, walking ? (step ? 4 : -4) : 0);
}

inline bool clash(uint32_t elapsed) { return elapsed >= 800 && elapsed < 3000; }
inline unsigned beat(uint32_t elapsed) { return (elapsed / 120) % 6; }
inline void monster(TFT_eSprite &pet, const Opponent &opponent, unsigned rank,
                    uint32_t elapsed, uint16_t bg, bool defeated = false) {
  const bool clash = sceneArt::clash(elapsed);
  const unsigned beat = sceneArt::beat(elapsed);
  pet.fillSprite(bg);
  const int x = clash && beat >= 3 ? 60 : 74;
  const int y = (defeated ? 70 : 54) + ((elapsed / 180) % 2 ? 3 : 0);
  const int size = 12 + 2 * rank;
  const uint16_t color = defeated ? TFT_DARKGREY : rank >= 6 ? TFT_PURPLE : TFT_ORANGE;
  pet.fillEllipse(77, 98, 47, 5, 0x18C3);
  switch (opponent.shape) {
    case MonsterShape::Beast:
      pet.fillEllipse(x + 10, y + 14, size + 11, size / 2, color);
      pet.fillTriangle(x + 28, y + 12, x + 46, y - 4, x + 34, y + 19, color);
      pet.fillTriangle(x - 15, y - 5, x - 10, y - 21, x, y, color);
      pet.fillRect(x + 3, y + 17, 6, 19, color);
      pet.fillRect(x + 20, y + 17, 6, 19, color);
      break;
    case MonsterShape::Crawler:
      pet.fillEllipse(x + 10, y + 10, size + 9, size / 2 + 4, color);
      for (int leg = 0; leg < 4; ++leg) {
        const int root = x - 6 + 10 * leg;
        const int foot = root - 18 + 12 * leg;
        pet.drawLine(root, y + 12, foot, y + 22, color);
        pet.drawLine(foot, y + 22, foot, y + 34, color);
      }
      pet.fillTriangle(x - 11, y + 4, x - 24, y + 1, x - 11, y + 11, TFT_WHITE);
      break;
    case MonsterShape::Winged: {
      const int wing = (elapsed / 120) % 2 ? 9 : 26;
      pet.fillTriangle(x, y + 5, x + 30, y - wing - 8, x + 48, y + 5, color);
      pet.fillTriangle(x + 3, y + 8, x - 8, y - wing, x + 20, y + 3, TFT_MAGENTA);
      pet.fillEllipse(x + 13, y + 10, size + 4, 10, color);
      pet.fillTriangle(x + 21, y + 12, x + 47, y + 19, x + 35, y + 7, color);
      break;
    }
    case MonsterShape::Biped:
      pet.fillRoundRect(x - 4, y + 2, size + 10, 28, 5, color);
      pet.fillRect(x, y + 27, 8, 14, color);
      pet.fillRect(x + size - 2, y + 27, 8, 14, color);
      pet.fillRect(x - 21, y + 7, 23, 7, color);
      pet.fillRect(x - 21, y - 9, 4, 36, TFT_LIGHTGREY);
      break;
  }
  pet.fillEllipse(x - 6, y, size / 2 + 4, 9, color);
  pet.fillCircle(x - 12, y - 2, 2, TFT_WHITE);
  if (clash && (beat == 2 || beat == 5)) {
    pet.drawLine(3, 45, 24, 68, TFT_YELLOW);
    pet.drawLine(3, 68, 24, 45, TFT_YELLOW);
    pet.drawFastHLine(0, 56, 27, TFT_WHITE);
  }
}
}
