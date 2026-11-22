#pragma once

#include <Preferences.h>
#include <WiFi.h>
#include <WiFiUdp.h>
#include "pet_visits.h"

namespace campLink {

enum State { Home, Joining, AtCamp };
constexpr uint16_t port = 18841;
constexpr uint32_t sendInterval = 1000, lease = 6500;
constexpr char configKey[] = "camp-config";
constexpr const char *names[] = {"goblin", "ant", "cat"};
static State state = Home;
static Preferences *storage;
static WiFiUDP udp;
static IPAddress server;
static String ssid, password, key, serialLine;
static bool discarding, connecting, socketReady, configChanged;
static uint32_t connectAt, nextConnect, lastSent, lastAck, lastPoll, sequence, session, startedAt;

inline bool configure(const String &line) {
  const int ipEnd = line.indexOf('\t');
  const int keyEnd = line.indexOf('\t', ipEnd + 1);
  const int ssidEnd = line.indexOf('\t', keyEnd + 1);
  if (ipEnd < 1 || keyEnd < 0 || ssidEnd < 0) return false;
  IPAddress ip;
  if (!ip.fromString(line.substring(0, ipEnd)) || ip == IPAddress(0, 0, 0, 0)) return false;
  const String candidate = line.substring(ipEnd + 1, keyEnd);
  const String network = line.substring(keyEnd + 1, ssidEnd);
  const String pass = line.substring(ssidEnd + 1);
  if (candidate.length() != 32 || !network.length() || network.length() > 32 ||
      (pass.length() && (pass.length() < 8 || pass.length() > 63))) return false;
  for (unsigned i = 0; i < candidate.length(); ++i) {
    const char c = candidate[i];
    if (!((c >= '0' && c <= '9') || (c >= 'a' && c <= 'f'))) return false;
  }
  server = ip;
  ssid = network;
  password = pass;
  key = candidate;
  return true;
}

inline void begin(Preferences *store) {
  storage = store;
  WiFi.persistent(false);
  WiFi.setAutoReconnect(false);
  if (storage && storage->isKey(configKey)) configure(storage->getString(configKey));
}

inline void provision() {
  for (unsigned remaining = 64; remaining && Serial.available(); --remaining) {
    const char c = Serial.read();
    if (c == '\r') continue;
    if (c != '\n') {
      if (serialLine.length() < 160 && !discarding) serialLine += c;
      else discarding = true;
      continue;
    }
    if (!discarding && serialLine == "CAMP CLEAR") {
      if (storage) storage->remove(configKey);
      ssid = "";
      configChanged = true;
      Serial.println("Camp configuration cleared");
    } else if (!discarding && serialLine.startsWith("CAMP ")) {
      const String value = serialLine.substring(5);
      if (configure(value)) {
        if (storage) storage->putString(configKey, value);
        configChanged = true;
        Serial.println("Camp configured");
      } else {
        Serial.println("Invalid camp configuration");
      }
    }
    serialLine = "";
    discarding = false;
  }
}

inline bool ready() { return socketReady && WiFi.status() == WL_CONNECTED; }

inline void send(const char *mode, unsigned form) {
  char packet[128];
  const int len = snprintf(packet, sizeof(packet), "CAMP1 %s %s %08lx %lu %s %u",
      key.c_str(), names[petVisits::local], static_cast<unsigned long>(session),
      static_cast<unsigned long>(++sequence), mode, form);
  if (len > 0 && static_cast<size_t>(len) < sizeof(packet) && udp.beginPacket(server, port)) {
    udp.write(reinterpret_cast<const uint8_t *>(packet), len);
    udp.endPacket();
  }
}

inline void join(uint32_t now) {
  if (state != Home || !ready()) return;
  state = Joining;
  session = esp_random();
  sequence = 0;
  startedAt = lastAck = now;
  lastSent = now - sendInterval;
}

inline void leave(unsigned form) {
  if (state != Home && ready())
    for (unsigned i = 0; i < 3; ++i) send("leave", form);
  state = Home;
}

inline void tick(uint32_t now, unsigned form, bool mayConnect) {
  provision();
  if (configChanged) {
    state = Home;
    udp.stop();
    socketReady = connecting = configChanged = false;
    WiFi.disconnect();
    nextConnect = now + 250;
  }
  if (WiFi.status() != WL_CONNECTED) {
    if (socketReady) udp.stop();
    socketReady = false;
    state = Home;
    if (connecting && now - connectAt >= 9500) {
      WiFi.disconnect();
      connecting = false;
      nextConnect = now + 45000;
    } else if (!connecting && ssid.length() && mayConnect &&
               static_cast<int32_t>(now - nextConnect) >= 0) {
      WiFi.begin(ssid.c_str(), password.c_str());
      connecting = true;
      connectAt = now;
    }
    return;
  }
  connecting = false;
  if (!socketReady) socketReady = udp.begin(0);
  if (state == Home || !socketReady) return;

  if (now - lastPoll < 75) return;
  lastPoll = now;
  for (unsigned i = 0; i < 4; ++i) {
    const int size = udp.parsePacket();
    if (size <= 0) break;
    char packet[64]{};
    if (size >= static_cast<int>(sizeof(packet))) {
      udp.flush();
      continue;
    }
    const int length = udp.read(packet, sizeof(packet) - 1);
    unsigned long receivedSession = 0, receivedSequence = 0;
    char extra = 0;
    if (length > 0 && udp.remoteIP() == server && udp.remotePort() == port &&
        sscanf(packet, "CAMP1 %lx %lu %c", &receivedSession, &receivedSequence, &extra) == 2 &&
        receivedSession == session && receivedSequence == sequence) {
      state = AtCamp;
      lastAck = now;
    }
  }
  if ((state == Joining && now - startedAt >= lease) || now - lastAck >= lease) {
    leave(form);
  } else if (now - lastSent >= sendInterval) {
    send(state == Joining ? "arrive" : "stay", form);
    lastSent = now;
  }
}

}  // namespace campLink
