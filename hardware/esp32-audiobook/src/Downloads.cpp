#include "Downloads.h"
#include <dirent.h>

#include <HTTPClient.h>
#include <SD.h>
#include <WiFi.h>

namespace {
constexpr uint32_t maxPart = 48 * 1024 * 1024;

bool validId(const String& id) {
    if (id.isEmpty() || id.length() > 64) return false;
    for (char c : id) {
        if (!((c >= 'a' && c <= 'z') || (c >= 'A' && c <= 'Z') ||
              (c >= '0' && c <= '9') || c == '-' || c == '_')) return false;
    }
    return true;
}

// The host's authenticated HTTP API is used on the local network.
bool beginRequest(HTTPClient& http, WiFiClient& client, const String& url, const String& token) {
    http.useHTTP10(true);
    http.setConnectTimeout(4000);
    http.setTimeout(6000);
    if (!http.begin(client, url)) return false;
    http.addHeader("Authorization", "Bearer " + token);
    return true;
}
}

bool Downloads::configure() {
    if (!SD.exists("/network.txt")) return false;
    File file = SD.open("/network.txt");
    if (!file || file.size() > 512) return false;
    ssid = file.readStringUntil('\n');
    password = file.readStringUntil('\n');
    auto stripCR = [](String& value) {
        if (value.endsWith("\r")) value.remove(value.length() - 1);
    };
    stripCR(ssid);
    stripCR(password);
    host = file.readStringUntil('\n');
    token = file.readStringUntil('\n');
    host.trim();
    token.trim();
    while (host.endsWith("/")) host.remove(host.length() - 1);
    int colon = host.lastIndexOf(':');
    IPAddress address;
    if (ssid.isEmpty() || ssid.length() > 32 || password.length() > 63 || token.length() != 43 ||
        !host.startsWith("http://") || colon <= 7 ||
        !address.fromString(host.substring(7, colon)) ||
        host.substring(colon + 1).toInt() <= 0 || host.substring(colon + 1).toInt() > 65535) return false;
    return address[0] == 10 || (address[0] == 172 && address[1] >= 16 && address[1] <= 31) ||
           (address[0] == 192 && address[1] == 168);
}

bool Downloads::fail(const char* reason) {
    message = reason;
    return false;
}

bool Downloads::connect() {
    if (WiFi.status() == WL_CONNECTED) return true;
    static std::atomic<uint8_t> disconnectReason{0};
    static const auto eventId = WiFi.onEvent([](WiFiEvent_t, WiFiEventInfo_t info) {
        disconnectReason = info.wifi_sta_disconnected.reason;
        Serial.printf("CYD Wi-Fi disconnected: reason %u\n", unsigned(disconnectReason.load()));
    }, ARDUINO_EVENT_WIFI_STA_DISCONNECTED);
    (void)eventId;
    disconnectReason = 0;
    WiFi.persistent(false);
    if (!WiFi.mode(WIFI_STA)) {
        Serial.printf("CYD Wi-Fi radio init failed; heap %u\n", unsigned(ESP.getFreeHeap()));
        return fail("Could not start Wi-Fi radio");
    }
    WiFi.setAutoReconnect(true);
    const auto initial = WiFi.begin(ssid.c_str(), password.c_str());
    Serial.printf("CYD Wi-Fi joining; initial status %d, heap %u\n", int(initial), unsigned(ESP.getFreeHeap()));
    const uint32_t deadline = millis() + 18000;
    while (WiFi.status() != WL_CONNECTED && int32_t(deadline - millis()) > 0 && !cancelled) delay(100);
    if (WiFi.status() == WL_CONNECTED) {
        Serial.println("CYD Wi-Fi received an IP address");
        return true;
    }
    const auto reason = disconnectReason.load();
    Serial.printf("CYD Wi-Fi join failed: status %d, reason %u\n", int(WiFi.status()), unsigned(reason));
    WiFi.mode(WIFI_OFF);
    switch (reason) {
        case WIFI_REASON_NO_AP_FOUND: return fail("2.4 GHz network not found");
        case WIFI_REASON_AUTH_FAIL:
        case WIFI_REASON_4WAY_HANDSHAKE_TIMEOUT:
        case WIFI_REASON_HANDSHAKE_TIMEOUT: return fail("Wi-Fi password or security rejected");
        default: return fail("Wi-Fi connection timed out");
    }
}
void Downloads::disconnect() {
    WiFi.mode(WIFI_OFF);
}

int Downloads::request(const String& path, String& body, size_t maxBytes, bool post,
                       const String& payload) {
    WiFiClient client;
    HTTPClient http;
    if (!beginRequest(http, client, host + path, token)) return -1;
    int code = post ? http.POST(payload) : http.GET();
    int bytes = http.getSize();
    if (code > 0 && bytes >= 0 && size_t(bytes) <= maxBytes) {
        body = http.getString();
        if (body.length() != size_t(bytes)) code = -1;
    } else {
        code = -1;
    }
    http.end();
    return code;
}

void Downloads::syncProgress() {
    DIR* directory = opendir("/sd/Downloads");
    if (!directory) return;
    while (dirent* entry = readdir(directory)) {
        String id = entry->d_name;
        if (entry->d_type != DT_DIR || !validId(id)) continue;
        String path = "/Downloads/" + id + "/progress.log";
        if (!SD.exists(path)) continue;
        File log = SD.open(path);
        if (!log) {
            pendingProgress = true;
            continue;
        }
        uint64_t position = 0;
        String latest;
        while (log.available()) {
            String line = log.readStringUntil('\n');
            unsigned long long current = 0, duration = 0;
            unsigned finished = 0;
            char trailing;
            if (sscanf(line.c_str(), "%llu,%llu,%u%c", &current, &duration, &finished, &trailing) == 3 &&
                current > 0 && current <= duration && finished <= 1 &&
                (!finished || current == duration) && current >= position) {
                position = current;
                latest = line;
            }
        }
        log.close();
        if (latest.isEmpty()) continue;
        String response;
        if (request("/progress/" + id, response, 128, true, latest) == 200 && SD.remove(path)) {
            ++uploaded;
        } else {
            pendingProgress = true;
        }
    }
    closedir(directory);
}

bool Downloads::recent(RecentListen& result) {
    result = {};
    uploaded = 0;
    pendingProgress = false;
    message = nullptr;
    cancelled = false;
    if (!configure()) return fail("Check network.txt on microSD");
    if (!connect()) return false;
    String body;
    syncProgress();
    const int code = request("/recent", body, 512);
    if (code != 200) return fail(code == 401 ? "Check the host access token" : "Listening history unavailable");
    if (body.isEmpty()) return true;

    String fields[5];
    int start = 0;
    for (unsigned i = 0; i < 4; ++i) {
        int end = body.indexOf('\t', start);
        if (end < 0) return fail("Invalid listening history");
        fields[i] = body.substring(start, end);
        start = end + 1;
    }
    fields[4] = body.substring(start);
    if (!validId(fields[0]) || fields[1].isEmpty() ||
        (!fields[3].isEmpty() && (!validId(fields[2]) || !validId(fields[3])))) {
        return fail("Invalid listening history");
    }
    result = {{fields[0], fields[1]}, fields[2], fields[3], fields[4]};
    return true;
}

bool Downloads::catalog(const String& library, unsigned page, std::vector<CatalogEntry>& rows,
                        bool& more, const String& series) {
    message = nullptr;
    cancelled = false;
    if (!configure()) return fail("Check network.txt on microSD");
    if (!connect()) return false;
    String body;
    String path = !series.isEmpty() ? "/series/" + library + "/" + series + "/" :
        library.isEmpty() ? "/libraries/" : "/books/" + library + "/";
    const int code = request(path + String(page), body, 768);
    if (code != 200) return fail(code == 401 ? "Check the host access token" : "Audiobook host unavailable");

    std::vector<CatalogEntry> parsed;
    int start = body.indexOf('\n');
    if (start != 1 || (body[0] != '0' && body[0] != '1')) return fail("Invalid catalog response");
    while (++start < int(body.length())) {
        int end = body.indexOf('\n', start);
        if (end < 0) end = body.length();
        int tab = body.indexOf('\t', start);
        if (tab < 0 || tab >= end || parsed.size() >= 4) return fail("Invalid catalog row");
        String id = body.substring(start, tab);
        if (!validId(id)) return fail("Invalid catalog item");
        parsed.push_back({id, body.substring(tab + 1, end)});
        start = end;
    }
    more = body[0] == '1';
    rows = std::move(parsed);
    return true;
}

bool Downloads::start(const String& book) {
    if (!validId(book)) return fail("Invalid book selection");
    selected = book;
    cancelled = false;
    completed = total = 0;
    message = nullptr;
    state = Preparing;
    if (xTaskCreate([](void* context) {
        auto& downloads = *static_cast<Downloads*>(context);
        downloads.transfer();
        vTaskDelete(nullptr);
    }, "book-download", 8192, this, 1, nullptr) == pdPASS) return true;
    state = Failed;
    return fail("Not enough memory to download");
}

bool Downloads::fetch(const String& path, const String& file, uint32_t expected) {
    const String partial = file + ".part";
    SD.remove(partial);
    WiFiClient client;
    HTTPClient http;
    if (!beginRequest(http, client, host + path, token) || http.GET() != 200 ||
        http.getSize() != int(expected)) return false;
    File output = SD.open(partial, FILE_WRITE);
    if (!output) return false;
    uint8_t buffer[2048];
    uint32_t remaining = expected;
    uint32_t lastRead = millis();
    auto* stream = http.getStreamPtr();
    while (stream && remaining && !cancelled && millis() - lastRead < 10000) {
        int available = stream->available();
        if (available <= 0) {
            if (!stream->connected()) break;
            delay(2);
            continue;
        }
        const size_t amount = std::min<size_t>(available, std::min<size_t>(remaining, sizeof(buffer)));
        int count = stream->read(buffer, amount);
        if (count <= 0 || output.write(buffer, count) != size_t(count)) break;
        remaining -= count;
        lastRead = millis();
        delay(1);
    }
    output.close();
    http.end();
    if (!remaining && !cancelled && SD.rename(partial, file)) return true;
    SD.remove(partial);
    return false;
}

void Downloads::transfer() {
    const bool success = [&] {
        if (!connect()) return false;
        const String path = "/book/" + selected;
        const String directory = "/Downloads/" + selected;
        if (SD.exists(directory + "/title.txt")) return true;
        String body;
        int code = request(path, body, 32768, true);
        if (code != 202) return fail("Host rejected the download");
        const uint32_t start = millis();
        do {
            if (cancelled) return false;
            code = request(path, body, 32768);
            if (code == 200) break;
            if (code != 202) return fail("Host could not prepare the book");
            delay(2000);
        } while (millis() - start < 30UL * 60 * 1000);
        int separator = body.indexOf('\n');
        if (code != 200) return fail("Book preparation timed out");
        if (separator <= 0 || separator > 90) return fail("Invalid book manifest");

        std::vector<uint32_t> parts;
        for (int offset = separator + 1; offset < int(body.length());) {
            char* end = nullptr;
            const char* number = body.c_str() + offset;
            unsigned long bytes = strtoul(number, &end, 10);
            if (end == number || (*end && *end != ',') || bytes < 2 ||
                bytes > maxPart || bytes % 2 || parts.size() >= 2048) return fail("Invalid audio part");
            parts.push_back(bytes);
            offset = end - body.c_str() + 1;
        }
        if (parts.empty()) return fail("Book has no audio");
        String title = body.substring(0, separator);
        body = "";
        if ((!SD.exists("/Downloads") && !SD.mkdir("/Downloads")) ||
            (!SD.exists(directory) && !SD.mkdir(directory))) return fail("Cannot create book folder");

        uint64_t required = 0;
        for (unsigned i = 0; i < parts.size(); ++i) {
            char name[16];
            snprintf(name, sizeof(name), "%05u.pcm", i + 1);
            File part = SD.open(directory + "/" + name);
            if (part && part.size() != parts[i]) return fail("Existing audio part size differs");
            if (!part) required += parts[i];
        }
        if (SD.totalBytes() - SD.usedBytes() < required + 65536) return fail("Not enough room on microSD");

        total = parts.size();
        state = Transferring;
        for (unsigned i = 0; i < parts.size() && !cancelled; ++i) {
            char name[16];
            snprintf(name, sizeof(name), "%05u.pcm", i + 1);
            String target = directory + "/" + name;
            if (!SD.exists(target) && !fetch(path + "/" + name, target, parts[i])) {
                return fail("Download interrupted; retry to resume");
            }
            completed = i + 1;
        }
        if (cancelled) return false;
        const String marker = directory + "/title.txt";
        const String temporary = marker + ".part";
        SD.remove(temporary);
        File file = SD.open(temporary, FILE_WRITE);
        if (!file) return fail("Could not save book title");
        const size_t written = file.print(title);
        file.close();
        return (written == title.length() && SD.rename(temporary, marker)) ||
               fail("Could not finish the book");
    }();
    disconnect();
    state = success ? Complete : cancelled ? Cancelled : Failed;
}
