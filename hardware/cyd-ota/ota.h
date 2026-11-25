#pragma once

#include <ArduinoOTA.h>
#include <Preferences.h>
#include <WiFi.h>
#include <esp_wifi.h>

namespace cydOta {
static bool otaProvisioned = false;
static bool otaActive = false;

inline bool validOtaKey(const String &key) {
  return key.length() == 64 && strspn(key.c_str(), "0123456789abcdef") == 64;
}

inline size_t decodeCredential(const String &hex, uint8_t *buffer, size_t capacity) {
  if (!hex.length() || hex.length() % 2 || hex.length() / 2 > capacity ||
      strspn(hex.c_str(), "0123456789abcdef") != hex.length()) return 0;
  for (size_t i = 0; i < hex.length() / 2; ++i) {
    char pair[] = {hex[2 * i], hex[2 * i + 1], '\0'};
    buffer[i] = strtoul(pair, nullptr, 16);
    if (!buffer[i]) return 0;
  }
  return hex.length() / 2;
}

inline bool saveWiFi(const String &command) {
  const int separator = command.indexOf(' ', 9);
  if (separator < 0) return false;
  wifi_config_t config{};
  const auto ssidLength = decodeCredential(command.substring(9, separator),
                                           config.sta.ssid, sizeof(config.sta.ssid));
  const auto passwordLength = decodeCredential(command.substring(separator + 1),
                                               config.sta.password, sizeof(config.sta.password));
  if (!ssidLength || passwordLength < 8) return false;
  if (passwordLength == 64) {
    for (uint8_t byte : config.sta.password) {
      if (!isxdigit(byte)) return false;
    }
  }
  return WiFi.mode(WIFI_STA) && esp_wifi_set_storage(WIFI_STORAGE_FLASH) == ESP_OK &&
         esp_wifi_set_config(WIFI_IF_STA, &config) == ESP_OK;
}

inline void configureOta(bool allowWiFiProvisioning = false) {
  Preferences settings;
  if (!settings.begin("cyd-ota")) return;
  String key = settings.getString("key");
  String command;
  bool overflow = false;
  Serial.println("CYD OTA provisioning ready");
  uint32_t started = millis();
  while (millis() - started < 1500) {
    const int byte = Serial.read();
    if (byte < 0) {
      delay(5);
    } else if (byte == '\n') {
      if (!overflow && allowWiFiProvisioning && command.startsWith("CYD-WIFI ")) {
        started = millis();
        if (saveWiFi(command)) Serial.println("CYD Wi-Fi credentials saved");
      } else if (!overflow && command.startsWith("CYD-OTA ")) {
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
    } else if (command.length() < (allowWiFiProvisioning ? 202 : 72)) {
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
