#pragma once

#include "display_link.h"
#include "virtual_pet.h"

namespace cydCamp {

constexpr uint8_t broadcast[] = {255, 255, 255, 255, 255, 255};
constexpr uint32_t leaseMs = 6500, beaconMs = 150, updateMs = 850;
constexpr uint16_t protocol = 0x4301;
enum Message : uint8_t { Beacon, Join, Stay, Leave, Ack };
enum State : uint8_t { Home, Joining, AtCamp };
struct Packet {
  uint32_t session;
  uint16_t version;
  uint8_t message, species, form, channel;
  uint8_t target[6];
};
static_assert(sizeof(Packet) == 16, "Camp packet must differ from rack scene packets");
struct Received { Packet packet; uint8_t mac[6]; };
struct Guest {
  uint32_t session = 0, updated = 0;
  uint8_t mac[6]{}, form = 0;
  bool active = false;
};
static QueueHandle_t inbox;
static uint8_t address[6], beaconChannel;
static uint32_t lastBeacon, lastSend, lastAck, session;
static State state = Home;
static Guest guests[3];

inline void begin() {
  if (esp_wifi_get_mac(WIFI_IF_STA, address) != ESP_OK) return;
  inbox = xQueueCreate(16, sizeof(Received));
  if (!inbox || esp_now_is_peer_exist(broadcast)) return;
  esp_now_peer_info_t peer{};
  memcpy(peer.peer_addr, broadcast, 6);
  peer.ifidx = WIFI_IF_STA;
  esp_now_add_peer(&peer);
}

inline void receive(const uint8_t *mac, const uint8_t *bytes, int length) {
  if (!inbox || length != sizeof(Packet)) return;
  Received item{};
  memcpy(&item.packet, bytes, sizeof(Packet));
  const Packet &p = item.packet;
  if (p.version != protocol || p.message > Ack || p.species >= 3 ||
      p.form >= (p.species == 0 ? FORM_COUNT : virtualPet::formCount) ||
      p.channel == 0 || p.channel > 14 ||
      (p.message != Beacon && (!p.session || memcmp(p.target, address, 6)))) return;
  memcpy(item.mac, mac, 6);
  xQueueSend(inbox, &item, 0);
}

inline void send(Message message, uint32_t id, unsigned species, unsigned form,
                 const uint8_t *target) {
  uint8_t channel = 0;
  wifi_second_chan_t secondary;
  if (!inbox || esp_wifi_get_channel(&channel, &secondary) != ESP_OK) return;
  Packet packet{id, protocol, message, static_cast<uint8_t>(species),
                static_cast<uint8_t>(form), channel, {}};
  if (target) memcpy(packet.target, target, 6);
  esp_now_send(broadcast, reinterpret_cast<const uint8_t *>(&packet), sizeof(packet));
}

inline bool available(uint32_t now, uint8_t channel) {
  return lastBeacon && channel == beaconChannel && now - lastBeacon < 1800;
}

inline void join(uint32_t now) {
  session = esp_random() | 1U;
  state = Joining;
  lastAck = now;
  lastSend = now - updateMs;
}

inline void leave(unsigned species, unsigned form) {
  if (state == Home) return;
  send(Leave, session, species, form, displayLink::cydMac);
  state = Home;
}

inline void clientTick(uint32_t now, unsigned species, unsigned form, uint8_t channel) {
  Received item;
  while (inbox && xQueueReceive(inbox, &item, 0) == pdTRUE) {
    const Packet &p = item.packet;
    if (memcmp(item.mac, displayLink::cydMac, 6) || p.channel != channel) continue;
    if (p.message == Beacon) {
      lastBeacon = now;
      beaconChannel = p.channel;
    } else if (p.message == Ack && state != Home && p.session == session && p.species == species) {
      state = AtCamp;
      lastAck = now;
    }
  }
  if (state == Home) return;
  if (now - lastAck >= leaseMs) {
    leave(species, form);
  } else if (now - lastSend >= updateMs) {
    send(state == Joining ? Join : Stay, session, species, form, displayLink::cydMac);
    lastSend = now;
  }
}

inline bool hostTick(uint32_t now, bool open) {
  bool changed = false;
  for (auto &guest : guests) {
    if (guest.active && (!open || now - guest.updated >= leaseMs)) {
      guest.active = false;
      changed = true;
    }
  }
  if (open && now - lastBeacon >= beaconMs) {
    send(Beacon, 0, 0, 0, nullptr);
    lastBeacon = now;
  }
  Received item;
  while (inbox && xQueueReceive(inbox, &item, 0) == pdTRUE) {
    const Packet &p = item.packet;
    if (!open || p.message < Join || p.message > Leave) continue;
    Guest &guest = guests[p.species];
    const bool same = guest.session == p.session && !memcmp(item.mac, guest.mac, 6);
    if (p.message == Leave) {
      if (same && guest.active) {
        guest.active = false;
        changed = true;
      }
      continue;
    }
    if ((!same && guest.active) || (!guest.active && (p.message != Join || same))) continue;
    changed = changed || !guest.active || guest.form != p.form;
    guest.active = true;
    guest.form = p.form;
    guest.updated = now;
    guest.session = p.session;
    memcpy(guest.mac, item.mac, 6);
    send(Ack, p.session, p.species, p.form, item.mac);
  }
  return changed;
}

inline const char *formName(unsigned species, unsigned rank) {
  if (species == 0) return milestone(static_cast<Form>(rank)).name;
  return (species == 1 ? virtualPet::antStages : virtualPet::catStages)[rank].name;
}

}  // namespace cydCamp
