#pragma once
#include <Arduino.h>
#include <WiFi.h>
#include <esp_now.h>
#include <esp_wifi.h>
#include <freertos/queue.h>
#include "combat.h"

namespace displayLink {
constexpr uint8_t waveshareMac[] = {0x28, 0x84, 0x85, 0x55, 0x4c, 0x1c};
constexpr uint8_t cydMac[] = {0x48, 0x9d, 0x31, 0xc0, 0x27, 0x5c};
constexpr uint32_t fightMs = 3600, walkMs = 1200, inspectionMs = 7000;
constexpr uint32_t patrolMs = walkMs * 2 + inspectionMs;
constexpr uint32_t timeoutMs = 2200;
enum Scene : uint8_t { Idle, Fight, Patrol };
struct Frame {
  uint16_t version = 0x4701, elapsed = 0;
  int16_t patrolX = 0;
  Scene scene = Idle;
  uint8_t form = 0, rank = 0, opponent = 0, defeated = 0, reserved = 0;
};
static_assert(sizeof(Frame) == 12, "Unexpected ESP-NOW frame layout");
struct Received { Frame frame; uint32_t at; };
static QueueHandle_t inbox;
static const uint8_t *peer;
static bool ready;
static uint32_t lastSent;

inline void receive(const uint8_t *mac, const uint8_t *bytes, int length) {
  if (length != sizeof(Frame) || memcmp(mac, peer, 6) != 0) return;
  Received packet;
  memcpy(&packet.frame, bytes, sizeof(Frame));
  const auto &f = packet.frame;
  if (f.version != Frame{}.version || f.scene > Patrol || f.form >= FORM_COUNT ||
      f.rank >= FORM_COUNT || f.opponent >= 2 || f.defeated > 1 || f.reserved ||
      (f.scene == Fight && f.elapsed >= fightMs) ||
      (f.scene == Patrol && (f.elapsed >= patrolMs || f.patrolX > 0 || f.patrolX < -240))) return;
  packet.at = millis();
  xQueueOverwrite(inbox, &packet);
}

inline void begin(const uint8_t *mac) {
  peer = mac;
  inbox = xQueueCreate(1, sizeof(Received));
  if (!inbox || esp_now_init() != ESP_OK) return;
  esp_now_peer_info_t info{};
  memcpy(info.peer_addr, peer, 6);
  info.ifidx = WIFI_IF_STA;
  ready = esp_now_add_peer(&info) == ESP_OK && esp_now_register_recv_cb(receive) == ESP_OK;
}

inline void send(const Frame &frame, uint32_t now, uint32_t interval) {
  if (!ready || now - lastSent < interval) return;
  lastSent = now;
  esp_now_send(peer, reinterpret_cast<const uint8_t *>(&frame), sizeof(frame));
}

inline bool read(Received &packet) {
  return ready && xQueueReceive(inbox, &packet, 0) == pdTRUE;
}

inline int walkDistance(uint32_t elapsed, int distance) {
  const uint32_t leg = elapsed < walkMs ? elapsed : elapsed > patrolMs - walkMs ?
      patrolMs - elapsed : walkMs;
  return distance * leg / walkMs;
}
}
