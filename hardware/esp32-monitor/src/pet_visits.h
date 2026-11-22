#pragma once

#include <Arduino.h>
#include <esp_now.h>
#include <esp_wifi.h>
#include <freertos/queue.h>
#include "virtual_pet.h"

namespace petVisits {

enum Species : uint8_t { Goblin, Ant, Cat, SpeciesCount };
#if defined(SHELF_PET_ANT)
constexpr Species local = Ant;
#elif defined(SHELF_PET_CAT)
constexpr Species local = Cat;
#else
constexpr Species local = Goblin;
#endif
constexpr const char *names[] = {"Goblin", "Ant", "Cat"};
constexpr uint8_t fallbackChannel = 6;
constexpr uint32_t presenceMs = 2200, requestMs = 12000, visitMs = 8000;
constexpr uint32_t walkMs = 1000, heartbeatMs = 180;
constexpr uint8_t broadcast[] = {255, 255, 255, 255, 255, 255};

enum Message : uint8_t { Hello, Busy, Invite, Accept, Live, End };
struct Packet {
  uint32_t token;
  uint16_t protocol;
  uint8_t species, form, message, channel;
  uint8_t target[6];
};
static_assert(sizeof(Packet) == 16, "Unexpected pet visit packet layout");
constexpr uint16_t protocol = 0x5001;
struct Received { Packet packet; uint8_t mac[6]; };

enum Status : uint8_t { Home, Calling, Waiting, Away, Hosting };
struct Friend {
  uint8_t mac[6]{};
  uint8_t channel = 0;
  uint32_t seenAt = 0;
  bool free = false;
};

static QueueHandle_t inbox;
static Friend friends[SpeciesCount];
static uint8_t address[6], partnerAddress[6];
static uint8_t channel = fallbackChannel, sweepChannel = 0;
static bool ready;
static uint32_t lastSent, radioAt, nextSweep;
static uint32_t token, started, heardAt;
static Status status = Home;
static Species partner = Goblin;
static uint8_t guestForm;

inline void receive(const uint8_t *mac, const uint8_t *bytes, int length) {
  if (!inbox || length != sizeof(Packet)) return;
  Received item{};
  memcpy(&item.packet, bytes, sizeof(Packet));
  const Packet &p = item.packet;
  if (p.protocol != protocol || p.species >= SpeciesCount || p.species == local ||
      p.message > End || p.channel < 1 || p.channel > 11 ||
      p.form >= (p.species == Goblin ? FORM_COUNT : virtualPet::formCount) ||
      (p.message >= Invite && (!p.token || memcmp(p.target, address, 6)))) return;
  memcpy(item.mac, mac, 6);
  xQueueSend(inbox, &item, 0);
}

inline void changeChannel(uint8_t next, uint32_t now) {
  if (channel == next || esp_wifi_set_channel(next, WIFI_SECOND_CHAN_NONE) == ESP_OK) {
    channel = next;
    radioAt = now;
    lastSent = now - heartbeatMs;
  }
}

inline void begin(bool ownReceiver, uint32_t now,
                  esp_now_recv_cb_t receiver = receive) {
  if (esp_wifi_get_mac(WIFI_IF_STA, address) != ESP_OK) return;
  inbox = xQueueCreate(16, sizeof(Received));
  if (!inbox) return;
  if (ownReceiver && (esp_now_init() != ESP_OK || esp_now_register_recv_cb(receiver) != ESP_OK)) return;
  esp_now_peer_info_t peer{};
  memcpy(peer.peer_addr, broadcast, 6);
  peer.ifidx = WIFI_IF_STA;
  ready = esp_now_add_peer(&peer) == ESP_OK;
  channel = 0;
  changeChannel(fallbackChannel, now);
  nextSweep = local == Goblin ? now : now + 8000 + esp_random() % 5000;
}

inline bool nearby(Species species, uint32_t now) {
  const Friend &peer = friends[species];
  return ready && species != local && peer.channel == channel && peer.free &&
      now - peer.seenAt < presenceMs;
}

inline void send(Message message, unsigned form, uint32_t now) {
  Packet packet{message >= Invite ? token : 0, protocol, local,
      static_cast<uint8_t>(form), message, channel, {}};
  if (message >= Invite) memcpy(packet.target, partnerAddress, 6);
  esp_now_send(broadcast, reinterpret_cast<const uint8_t *>(&packet), sizeof(packet));
  lastSent = now;
}

inline void start(Status next, Species species, const uint8_t *mac,
                  uint32_t session, uint32_t now) {
  status = next;
  partner = species;
  memcpy(partnerAddress, mac, 6);
  token = session;
  started = heardAt = now;
  lastSent = now - heartbeatMs;
}

inline void invite(Species species, uint32_t now) {
  if (status == Home && nearby(species, now))
    start(Calling, species, friends[species].mac, esp_random() | 1U, now);
}

inline void close(unsigned form, uint32_t now) {
  if (status == Home) return;
  send(End, form, now);
  status = Home;
}

inline void radio(uint32_t now, bool fixed) {
  if (fixed || status != Home || !ready) return;
  if (local != Goblin) {
    const Friend &goblin = friends[Goblin];
    if (goblin.channel == channel && now - goblin.seenAt < presenceMs) {
      sweepChannel = 0;
      nextSweep = now + 8000;
      return;
    }
  }
  if (sweepChannel == 0 && static_cast<int32_t>(now - nextSweep) < 0) return;
  if (sweepChannel && now - radioAt < 380) return;
  if (++sweepChannel <= 11) {
    changeChannel(sweepChannel, now);
  } else {
    changeChannel(fallbackChannel, now);
    sweepChannel = 0;
    nextSweep = now + 11000 + esp_random() % 5000;
  }
}

inline void tick(uint32_t now, unsigned form, bool free, bool fixed) {
  if (!ready) return;
  Received received;
  while (xQueueReceive(inbox, &received, 0) == pdTRUE) {
    const Packet &p = received.packet;
    if (p.channel != channel) continue;
    const Species species = static_cast<Species>(p.species);
    Friend &peer = friends[species];
    if (p.message <= Busy) {
      memcpy(peer.mac, received.mac, 6);
      peer.seenAt = now;
      peer.channel = channel;
      peer.free = p.message == Hello;
      continue;
    }
    if (status == Home && p.message == Invite && free) {
      start(Waiting, species, received.mac, p.token, now);
      continue;
    }
    if (status == Calling && p.message == Invite && species == partner && local > partner &&
        memcmp(received.mac, partnerAddress, 6) == 0) {
      start(Waiting, species, received.mac, p.token, now);
      continue;
    }
    if (species != partner || p.token != token || memcmp(received.mac, partnerAddress, 6) ||
        status == Home) continue;
    if (p.message == End) {
      status = Home;
    } else if (status == Calling && p.message == Accept) {
      status = Away;
      started = heardAt = now;
      lastSent = now - heartbeatMs;
    } else if (p.message == Live && (status == Waiting || status == Hosting || status == Away)) {
      if (status == Waiting) {
        status = Hosting;
        started = now;
        guestForm = p.form;
        lastSent = now - heartbeatMs;
      }
      heardAt = now;
    }
  }
  if (status != Home && ((status >= Away && (now - started >= visitMs ||
      now - heardAt >= presenceMs)) || (status < Away && now - started >= requestMs)))
    close(form, now);
  radio(now, fixed);
  if (now - lastSent < heartbeatMs) return;
  switch (status) {
    case Home: send(free ? Hello : Busy, form, now); break;
    case Calling: send(Invite, form, now); break;
    case Waiting: send(Accept, form, now); break;
    case Away:
    case Hosting: send(Live, form, now); break;
  }
}

}  // namespace petVisits
