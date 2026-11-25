#pragma once

#include <ArduinoOTA.h>
#include <Preferences.h>

namespace cydOta {
static bool otaProvisioned = false;
static bool otaActive = false;

inline bool validOtaKey(const String &key) {
  return key.length() == 64 && strspn(key.c_str(), "0123456789abcdef") == 64;
}

inline void configureOta() {
  Preferences settings;
  if (!settings.begin("cyd-ota")) return;
  String key = settings.getString("key");
  String command;
  bool overflow = false;
  Serial.println("CYD OTA provisioning ready");
  const uint32_t started = millis();
  while (millis() - started < 1500) {
    const int byte = Serial.read();
    if (byte < 0) {
      delay(5);
    } else if (byte == '\n') {
      if (!overflow && command.startsWith("CYD-OTA ")) {
        const String requested = command.substring(8);
        if (validOtaKey(requested) &&
            (key == requested || settings.putString("key", requested) == requested.length())) {
          key = requested;
          Serial.println("CYD OTA credential saved");
          break;
        }
      }
      command = "";
      overflow = false;
    } else if (command.length() < 72) {
      command += static_cast<char>(byte);
    } else {
      overflow = true;
    }
  }
  settings.end();
  otaProvisioned = validOtaKey(key);
  if (otaProvisioned) {
    ArduinoOTA.setPassword(key.c_str());
    ArduinoOTA.setMdnsEnabled(false);
  }
}

inline void serviceOta(bool connected, bool portalActive) {
  const bool enabled = otaProvisioned && connected && !portalActive;
  if (enabled != otaActive) {
    if (enabled) ArduinoOTA.begin();
    else ArduinoOTA.end();
    otaActive = enabled;
  }
  if (otaActive) ArduinoOTA.handle();
}

}  // namespace cydOta
