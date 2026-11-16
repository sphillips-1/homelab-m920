#include <Arduino.h>
#include <Preferences.h>
#include <SD.h>
#include <TFT_eSPI.h>
#include <BluetoothA2DPSource.h>
#include <atomic>
#include <dirent.h>
#include <algorithm>
#include <vector>
#include "touch_controls.h"
#include "Downloads.h"

namespace {
constexpr int sampleRate = 22050;
constexpr int sdSelect = 5;
constexpr int touchSelect = 33;
constexpr int touchClock = 25;
constexpr int touchOut = 32;
constexpr int touchIn = 39;
constexpr int touchIrq = 36;
constexpr size_t audioCapacity = 4096;
constexpr uint16_t background = 0x10A3;
constexpr uint16_t panel = 0x21CA;
constexpr uint16_t accent = 0x5EF3;
constexpr uint16_t muted = 0xAD77;
constexpr char folder[] = "/Audiobooks";

TFT_eSPI screen;
Preferences prefs;
std::vector<String> chapters;
String playbackFolder = folder;
Downloads downloads;
enum class LibraryView { Player, Offline, Server, Libraries, Catalog, Series, Download };
LibraryView libraryView = LibraryView::Player;
std::vector<CatalogEntry> libraryRows;
String libraryId;
String downloadTitle;
int libraryPage = 0;
RecentListen recentListen;
const char* recentError = nullptr;
String selectedBookId;
LibraryView downloadFrom = LibraryView::Catalog;
bool moreRows = false;
constexpr uint32_t wifiBootMagic = 0x43594457;
RTC_NOINIT_ATTR uint32_t wifiBootRequest;
bool wifiOnlyBoot = false;
const char* libraryError = nullptr;
File track;
TouchCalibration calibration{};
TouchPoint targets[] = {{24,24}, {296,24}, {24,216}, {296,216}};
TouchPoint samples[3];
int target = -1;
int chapter = 0;
std::atomic<int> volume{3};
uint32_t position = 0;
uint32_t savedAt = 0;
bool playing = false;
A2DPNoVolumeControl passthroughVolume;
class HeadphoneSource : public BluetoothA2DPSource {
public:
    void setHeadphoneLevel(int level) {
        // The library uses labels 0 and 1 for capability and notification requests.
        if (!remoteControlConnected.load()) return;
        const auto requested = static_cast<uint8_t>((level * 127 + 5) / 10);
        const auto result = esp_avrc_ct_send_set_absolute_volume_cmd(15, requested);
        if (result != ESP_OK) Serial.printf("Headset volume command: %s\n", esp_err_to_name(result));
    }

protected:
    void bt_av_hdl_avrc_ct_evt(uint16_t event, void* data) override {
        const auto* response = static_cast<const esp_avrc_ct_cb_param_t*>(data);
        if (event == ESP_AVRC_CT_CONNECTION_STATE_EVT) {
            remoteControlConnected = response->conn_stat.connected;
        } else if (event == ESP_AVRC_CT_SET_ABSOLUTE_VOLUME_RSP_EVT) {
            Serial.printf("Headset accepted volume %u / 127\n", unsigned(response->set_volume_rsp.volume));
        }
        BluetoothA2DPSource::bt_av_hdl_avrc_ct_evt(event, data);
    }

private:
    std::atomic<bool> remoteControlConnected{false};
};
HeadphoneSource bluetooth;
std::atomic<bool> headphonesConnected{false};
std::atomic<bool> disconnectPending{false};
String headphoneName = "WH-1000XM5";
portMUX_TYPE audioLock = portMUX_INITIALIZER_UNLOCKED;
int16_t audioBuffer[audioCapacity];
size_t readHead = 0;
size_t queued = 0;
uint32_t consumedBytes = 0;
uint32_t loadedPosition = 0;
bool deliverAudio = false;
bool repeatSample = false;
bool prefsReady = false;
bool browser = false;
int page = 0;
const char* error = nullptr;


// The display uses HSPI and the SD card uses VSPI. Touch has its own pins.
uint16_t touchTransfer(uint16_t out, int bits) {
    uint16_t in = 0;
    for (int bit = bits - 1; bit >= 0; --bit) {
        digitalWrite(touchOut, (out >> bit) & 1);
        digitalWrite(touchClock, HIGH);
        in = (in << 1) | digitalRead(touchIn);
        digitalWrite(touchClock, LOW);
    }
    return in;
}

bool readTouch(TouchPoint& point) {
    if (digitalRead(touchIrq) == HIGH) return false;
    digitalWrite(touchSelect, LOW);
    touchTransfer(0xB1, 8);
    int z1 = touchTransfer(0xC1, 16) >> 3;
    int z2 = touchTransfer(0x91, 16) >> 3;
    touchTransfer(0x91, 16);
    int x = touchTransfer(0xD1, 16) >> 3;
    int y = touchTransfer(0x90, 16) >> 3;
    touchTransfer(0, 16);
    digitalWrite(touchSelect, HIGH);
    point = {x, y};
    return z1 > 30 && z1 + 4095 - z2 >= 400;
}

void onConnection(esp_a2d_connection_state_t state, void*) {
    const bool connected = state == ESP_A2D_CONNECTION_STATE_CONNECTED;
    const bool wasConnected = headphonesConnected.exchange(connected);
    if (wasConnected && !connected) disconnectPending = true;
}

int32_t sendAudio(Frame* frames, int32_t count) {
    const int gain = volume.load();
    portENTER_CRITICAL(&audioLock);
    for (int32_t i = 0; i < count; ++i) {
        int16_t sample = 0;
        if (deliverAudio && headphonesConnected.load() && queued) {
            // Two 44.1 kHz stereo frames per 22.05 kHz mono sample.
            sample = int32_t(audioBuffer[readHead]) * gain / 10;
            if (repeatSample) {
                readHead = (readHead + 1) % audioCapacity;
                --queued;
                consumedBytes += sizeof(sample);
            }
            repeatSample = !repeatSample;
        }
        frames[i] = Frame(sample, sample);
    }
    portEXIT_CRITICAL(&audioLock);
    return count;
}

void initAudio() {
    File config = SD.open("/headphones.txt");
    if (config && config.size() <= 248) {
        String name = config.readStringUntil('\n');
        name.trim();
        if (name.length()) headphoneName = name;
    }
    if (prefsReady && prefs.getString("headset") != headphoneName) {
        // Clear the A2DP library's cached address when the configured name changes.
        Preferences pairing;
        if (pairing.begin("connected_bda")) {
            if (pairing.isKey("src_bda")) pairing.remove("src_bda");
            pairing.end();
        }
        prefs.putString("headset", headphoneName);
    }
    bluetooth.set_local_name("CYD Audiobook");
    // AVRCP volume events can also enable the library's PCM attenuation.
    // Keep the player's gain as the only PCM adjustment.
    bluetooth.set_volume_control(&passthroughVolume);
    bluetooth.set_ssp_enabled(true);
    bluetooth.set_ssid_callback([](const char* name, esp_bd_addr_t, int) {
        return headphoneName.equals(name);
    });
    bluetooth.set_auto_reconnect(true);
    bluetooth.set_on_connection_state_changed(onConnection);
    bluetooth.set_data_callback_in_frames(sendAudio);
    bluetooth.start(headphoneName.c_str());
}

void updatePosition() {
    portENTER_CRITICAL(&audioLock);
    position += consumedBytes;
    consumedBytes = 0;
    portEXIT_CRITICAL(&audioLock);
}

void save() {
    if (!prefsReady || !track) return;
    String name = playbackFolder == folder ? chapters[chapter] : playbackFolder + "/" + chapters[chapter];
    String record = name + "\n" + String(position - position % 2);
    if (prefs.getString("bookmark") != record) prefs.putString("bookmark", record);
    savedAt = millis();
}

void halt() {
    playing = false;
    portENTER_CRITICAL(&audioLock);
    deliverAudio = false;
    position += consumedBytes;
    consumedBytes = 0;
    readHead = queued = 0;
    repeatSample = false;
    portEXIT_CRITICAL(&audioLock);
}

bool openChapter(int index, uint32_t offset = 0) {
    halt();
    track.close();
    chapter = index;
    track = SD.open(playbackFolder + "/" + chapters[chapter]);
    if (!track || track.size() < 2 || track.size() % 2) {
        track.close();
        error = "Could not open chapter";
        return false;
    }
    position = offset <= track.size() ? offset - offset % 2 : 0;
    return true;
}

void play() {
    if (!headphonesConnected.load()) {
        return;
    } else if (!track || !track.seek(position)) {
        error = "Could not start chapter";
    } else {
        loadedPosition = position;
        playing = true;
        error = nullptr;
    }
}

void button(int x, int y, int w, const char* text, bool primary = false) {
    screen.fillRoundRect(x, y, w, 40, 7, primary ? accent : panel);
    screen.setTextColor(primary ? background : TFT_WHITE);
    screen.drawCentreString(text, x + w / 2, y + 12, 2);
}

String titleFor(int index, unsigned limit) {
    String title = chapters[index];
    title.remove(title.length() - 4);
    if (title.length() > limit) title = title.substring(0, limit - 3) + "...";
    return title;
}

void showTime() {
    if (!track || browser || target >= 0) return;
    uint32_t elapsed = position / (sampleRate * 2);
    uint32_t duration = track.size() / (sampleRate * 2);
    char time[48];
    snprintf(time, sizeof(time), "%lu:%02lu / %lu:%02lu",
             (unsigned long)(elapsed / 60), (unsigned long)(elapsed % 60),
             (unsigned long)(duration / 60), (unsigned long)(duration % 60));
    screen.fillRect(12, 94, 296, 31, background);
    screen.setTextColor(muted);
    screen.drawString(time, 12, 94, 2);
    screen.fillRoundRect(12, 117, 296, 4, 2, panel);
    int width = uint64_t(position) * 296 / track.size();
    if (width) screen.fillRect(12, 117, width, 4, accent);
}

String fittedTitle(String text, int width) {
    if (screen.textWidth(text, 2) <= width) return text;
    const auto border = width - screen.textWidth("...", 2);
    while (!text.isEmpty() && screen.textWidth(text, 2) > border) text.remove(text.length() - 1);
    return text + "...";
}

void drawLibrary() {
    screen.setTextColor(accent);
    if (libraryView == LibraryView::Server) {
        screen.drawString("Audiobookshelf", 12, 12, 2);
        screen.setTextColor(muted);
        screen.drawString("Most recent listen", 12, 42, 2);
        if (!recentListen.book.id.isEmpty()) {
            bool hasSeries = !recentListen.series.isEmpty();
            int bookWidth = hasSeries ? 208 : 296;
            screen.fillRoundRect(12, 63, bookWidth, 40, 7, panel);
            screen.setTextColor(TFT_WHITE);
            screen.drawString(fittedTitle(recentListen.book.title, bookWidth - 16), 20, 75, 2);
            if (hasSeries) button(228, 63, 80, "Series");
        } else {
            screen.setTextColor(TFT_WHITE);
            screen.drawString(recentError ? fittedTitle(recentError, 296) : "No listening history yet", 12, 75, 2);
        }
        button(12, 190, 72, "Back");
        button(94, 190, 214, "Browse libraries", true);
        return;
    }
    const char* heading = libraryView == LibraryView::Offline ? "On microSD" :
        libraryView == LibraryView::Libraries ? "Audiobookshelf libraries" :
        libraryView == LibraryView::Catalog ? "Audiobookshelf books" : "Download to microSD";
    screen.drawString(libraryView == LibraryView::Series
        ? fittedTitle(recentListen.seriesTitle.isEmpty() ? "Series" : recentListen.seriesTitle, 296)
        : String(heading), 12, 12, 2);
    if (libraryView == LibraryView::Download) {
        auto state = downloads.state.load();
        screen.setTextColor(TFT_WHITE);
        String title = downloadTitle;
        if (title.length() > 40) title = title.substring(0, 37) + "...";
        screen.drawString(title, 12, 58, 2);
        String status;
        switch (state) {
            case Downloads::Preparing: status = "Preparing audio on host..."; break;
            case Downloads::Transferring:
                status = "Parts copied: " + String(downloads.completed.load()) +
                         " / " + String(downloads.total.load());
                break;
            case Downloads::Complete: status = "Ready to play offline"; break;
            case Downloads::Failed: status = downloads.error() ? downloads.error() : "Download failed"; break;
            case Downloads::Cancelled: status = "Cancelled. Select again to resume."; break;
            default: status = "Store this book on the card?"; break;
        }
        screen.drawString(status, 12, 93, 2);
        if (state == Downloads::Preparing || state == Downloads::Transferring) {
            button(12, 190, 92, "Cancel");
        } else {
            button(12, 190, 92, "Back");
            if (state == Downloads::Idle || state == Downloads::Failed || state == Downloads::Cancelled) {
                button(114, 190, 194, "Download book", true);
            } else {
                button(114, 190, 194, "On microSD", true);
            }
        }
        return;
    }
    if (libraryError) {
        screen.setTextColor(TFT_WHITE);
        screen.drawString(libraryError, 12, 76, 2);
    } else {
        for (unsigned row = 0; row < libraryRows.size(); ++row) {
            String title = libraryRows[row].title;
            if (title.length() > 41) title = title.substring(0, 38) + "...";
            screen.fillRoundRect(12, 40 + row * 35, 296, 30, 5, panel);
            screen.setTextColor(TFT_WHITE);
            screen.drawString(title, 19, 47 + row * 35, 2);
        }
        if (libraryRows.empty()) {
            screen.setTextColor(muted);
            screen.drawString("No books here yet", 12, 76, 2);
        }
    }
    button(12, 190, 72, "Back");
    if (libraryView == LibraryView::Offline) {
        if (libraryPage) button(90, 190, 55, "Prev");
        if (moreRows) button(151, 190, 55, "Next");
        button(212, 190, 96, "Server");
    } else {
        if (libraryPage) button(90, 190, 104, "Previous");
        if (moreRows) button(204, 190, 104, "Next");
    }
}

void draw() {
    screen.fillScreen(background);
    screen.setTextColor(accent);
    if (target >= 0) {
        screen.drawCentreString("Tap the crosshair", 160, 110, 2);
        TouchPoint p = targets[target];
        screen.drawFastHLine(p.x - 14, p.y, 29, TFT_WHITE);
        screen.drawFastVLine(p.x, p.y - 14, 29, TFT_WHITE);
        return;
    }
    if (libraryView != LibraryView::Player) {
        drawLibrary();
        return;
    }
    screen.drawString(browser ? "Chapters" : "Audiobook player", 12, 12, 2);
    if (chapters.empty()) {
        screen.setTextColor(TFT_WHITE);
        screen.drawString(error, 12, 72, 2);
        screen.drawString("Insert a card and press RST if needed.", 12, 102, 2);
        button(12, 190, 92, "Books");
        return;
    }
    if (browser) {
        for (int row = 0; row < 4 && page + row < int(chapters.size()); ++row) {
            int index = page + row;
            screen.fillRoundRect(12, 40 + row * 35, 296, 30, 5, panel);
            screen.setTextColor(index == chapter ? accent : TFT_WHITE);
            screen.drawString(titleFor(index, 41), 19, 47 + row * 35, 2);
        }
        button(12, 190, 65, "Back");
        button(83, 190, 65, "Prev");
        button(154, 190, 65, "Next");
        button(225, 190, 83, "Books");
        return;
    }
    screen.setTextColor(TFT_WHITE);
    screen.drawString(titleFor(chapter, 39), 12, 45, 2);
    screen.setTextColor(muted);
    String status = "Chapter " + String(chapter + 1) + " / " + String(chapters.size());
    if (!headphonesConnected.load()) {
        status = "Pairing: " + headphoneName;
        if (status.length() > 39) status = status.substring(0, 36) + "...";
    }
    screen.drawString(error ? String(error) : status, 12, 68, 2);
    showTime();
    button(12, 135, 92, "-15 sec");
    button(114, 135, 92, playing ? "Pause" : "Play", true);
    button(216, 135, 92, "+30 sec");
    button(12, 190, 92, "Chapters");
    button(114, 190, 92, "- Volume");
    button(216, 190, 92, "+ Volume");
    screen.setTextColor(muted);
    screen.drawRightString("Vol " + String(volume.load()) + "/10", 308, 12, 2);
}

void seekBy(int seconds) {
    if (!track) return;
    bool resume = playing;
    halt();
    int64_t destination = int64_t(position) + int64_t(seconds) * sampleRate * 2;
    position = std::max<int64_t>(0, std::min<int64_t>(track.size(), destination));
    save();
    if (resume) play();
}

bool selectFolder(const String& path);

void offlinePage() {
    libraryView = LibraryView::Offline;
    libraryRows.clear();
    moreRows = false;
    libraryError = nullptr;
    unsigned seen = 0;
    if (SD.exists(folder)) {
        if (libraryPage == 0) libraryRows.push_back({"", "Books copied to card"});
        ++seen;
    }
    if (DIR* directory = opendir("/sd/Downloads")) {
        while (dirent* entry = readdir(directory)) {
            if (entry->d_type == DT_DIR && entry->d_name[0] != '.') {
                String id = entry->d_name;
                String marker = "/Downloads/" + id + "/title.txt";
                if (!SD.exists(marker)) continue;
                File title = SD.open(marker);
                if (!title || title.size() > 90) continue;
                if (seen++ < unsigned(libraryPage * 4)) continue;
                if (libraryRows.size() == 4) {
                    moreRows = true;
                    break;
                }
                libraryRows.push_back({id, title.readString()});
            }
        }
        closedir(directory);
    }
    draw();
}

void onlinePage() {
    screen.fillScreen(background);
    screen.setTextColor(TFT_WHITE);
    screen.drawCentreString("Connecting to Audiobookshelf...", 160, 110, 2);
    libraryRows.clear();
    moreRows = false;
    const bool series = libraryView == LibraryView::Series;
    if (downloads.catalog(series ? recentListen.library : libraryId, libraryPage, libraryRows, moreRows,
                          series ? recentListen.series : String())) libraryError = nullptr;
    else libraryError = downloads.error();
    draw();
}

void switchRadioMode(bool wifi) {
    halt();
    save();
    screen.fillScreen(background);
    screen.setTextColor(TFT_WHITE);
    screen.drawCentreString(wifi ? "Starting Wi-Fi..." : "Starting Bluetooth...", 160, 110, 2);
    wifiBootRequest = wifi ? wifiBootMagic : 0;
    ESP.restart();
}

void openServer() {
    if (!wifiOnlyBoot) {
        switchRadioMode(true);
        return;
    }
    libraryView = LibraryView::Server;
    screen.fillScreen(background);
    screen.setTextColor(TFT_WHITE);
    screen.drawCentreString("Loading Audiobookshelf...", 160, 110, 2);
    recentError = downloads.recent(recentListen) ? nullptr : downloads.error();
    draw();
}

void openBooks() {
    halt();
    save();
    libraryPage = 0;
    offlinePage();
}

void chooseDownload(const CatalogEntry& entry) {
    downloadTitle = entry.title;
    selectedBookId = entry.id;
    downloadFrom = libraryView;
    downloads.state = Downloads::Idle;
    libraryView = LibraryView::Download;
    draw();
}

void libraryTap(TouchPoint point) {
    if (libraryView == LibraryView::Server) {
        if (point.y >= 63 && point.y < 103 && !recentListen.book.id.isEmpty()) {
            if (!recentListen.series.isEmpty() && point.x >= 228 && point.x < 308) {
                libraryView = LibraryView::Series;
                libraryPage = 0;
                onlinePage();
            } else if (point.x >= 12 && point.x < (recentListen.series.isEmpty() ? 308 : 220)) {
                chooseDownload(recentListen.book);
            }
        } else if (point.y >= 190 && point.y < 230) {
            if (point.x >= 12 && point.x < 84) {
                downloads.disconnect();
                libraryPage = 0;
                offlinePage();
            } else if (point.x >= 94 && point.x < 308) {
                libraryView = LibraryView::Libraries;
                libraryId = "";
                libraryPage = 0;
                onlinePage();
            }
        }
        return;
    }
    if (libraryView == LibraryView::Download) {
        if (point.y < 190 || point.y >= 230) return;
        const auto state = downloads.state.load();
        if (state == Downloads::Preparing || state == Downloads::Transferring) {
            if (point.x >= 12 && point.x < 104) downloads.cancel();
        } else if (point.x >= 12 && point.x < 104) {
            libraryView = downloadFrom;
            draw();
        } else if (point.x >= 114 && point.x < 308) {
            if (state == Downloads::Complete) {
                libraryPage = 0;
                offlinePage();
            } else {
                downloads.start(selectedBookId);
                draw();
            }
        }
        return;
    }
    if (point.y >= 40 && point.y < 180 && (point.y - 40) % 35 < 30 &&
        point.x >= 12 && point.x < 308 && !libraryError) {
        const unsigned row = (point.y - 40) / 35;
        if (row >= libraryRows.size()) return;
        const auto& entry = libraryRows[row];
        if (libraryView == LibraryView::Offline) {
            const String path = entry.id.isEmpty() ? String(folder) : "/Downloads/" + entry.id;
            if (selectFolder(path) && wifiOnlyBoot) {
                switchRadioMode(false);
                return;
            }
            browser = false;
            libraryView = LibraryView::Player;
            draw();
        } else if (libraryView == LibraryView::Libraries) {
            libraryId = entry.id;
            libraryView = LibraryView::Catalog;
            libraryPage = 0;
            onlinePage();
        } else {
            chooseDownload(entry);
        }
        return;
    }
    if (point.y < 190 || point.y >= 230) return;
    if (point.x >= 12 && point.x < 84) {
        if (libraryView == LibraryView::Offline) {
            if (wifiOnlyBoot) {
                switchRadioMode(false);
                return;
            }
            libraryView = LibraryView::Player;
            draw();
        } else if (libraryView == LibraryView::Catalog) {
            libraryView = LibraryView::Libraries;
            libraryId = "";
            libraryPage = 0;
            onlinePage();
        } else {
            libraryView = LibraryView::Server;
            draw();
        }
    } else if (libraryView == LibraryView::Offline && point.x >= 212) {
        openServer();
    } else {
        bool offline = libraryView == LibraryView::Offline;
        if (point.x >= 90 && point.x < (offline ? 145 : 194) && libraryPage) --libraryPage;
        else if (point.x >= (offline ? 151 : 204) && point.x < (offline ? 206 : 308) && moreRows) ++libraryPage;
        else return;
        if (offline) offlinePage();
        else onlinePage();
    }
}

void tap(TouchPoint raw) {
    if (target >= 0) {
        if (target < 3) samples[target++] = raw;
        if (target == 3 && !calibrateTouch(samples, calibration)) target = 0;
        if (target == 4) target = 0;
        draw();
        return;
    }
    TouchPoint p = mapTouch(calibration, raw);
    if (libraryView != LibraryView::Player) {
        libraryTap(p);
        return;
    }
    if (chapters.empty()) {
        if (p.x >= 12 && p.x < 104 && p.y >= 190 && p.y < 230) openBooks();
        return;
    }
    if (p.x < 12 || p.x >= 308) return;
    int column = p.x < 109 ? 0 : p.x < 211 ? 1 : 2;
    if (browser) {
        if (p.y >= 40 && p.y < 180 && (p.y - 40) % 35 < 30) {
            int index = page + (p.y - 40) / 35;
            if (index >= int(chapters.size())) return;
            if (index != chapter) {
                error = nullptr;
                if (openChapter(index)) save();
            }
            browser = false;
        } else if (p.y >= 190 && p.y < 230) {
            if (p.x < 77) browser = false;
            else if (p.x >= 83 && p.x < 148 && page >= 4) page -= 4;
            else if (p.x >= 154 && p.x < 219 && page + 4 < int(chapters.size())) page += 4;
            else if (p.x >= 225) {
                openBooks();
                return;
            }
        }
    } else if (p.y >= 135 && p.y < 175) {
        if (column == 0) seekBy(-15);
        if (column == 1) {
            if (playing) {
                halt();
                save();
            } else {
                if (track && position == track.size()) position = 0;
                play();
            }
        }
        if (column == 2) seekBy(30);
    } else if (p.y >= 190 && p.y < 230) {
        if (column == 0) {
            browser = true;
            page = chapter / 4 * 4;
        } else {
            const int level = constrain(volume.load() + (column == 1 ? -1 : 1), 0, 10);
            volume.store(level);
            if (headphonesConnected.load()) bluetooth.setHeadphoneLevel(level);
            if (prefsReady && prefs.getUChar("volume", 3) != level) prefs.putUChar("volume", level);
        }
    }
    draw();
}

void pollTouch() {
    static uint32_t lastPoll = 0;
    static uint32_t heldSince = 0;
    static unsigned count = 0;
    static unsigned misses = 0;
    static TouchPoint total{};
    uint32_t now = millis();
    if (now - lastPoll < 12) return;
    lastPoll = now;
    TouchPoint raw;
    if (readTouch(raw)) {
        if (!count) heldSince = now;
        misses = 0;
        if (count < 8) {
            total.x += raw.x;
            total.y += raw.y;
            ++count;
        }
        return;
    }
    if (!count || ++misses < 2) return;
    raw = {total.x / int(count), total.y / int(count)};
    unsigned captured = count;
    count = 0;
    total = {};
    if (now - heldSince >= 2000 && libraryView == LibraryView::Player) {
        halt();
        save();
        target = 0;
        draw();
    } else if (captured >= 2) {
        if (target == 3) {
            if (confirmsCalibration(calibration, raw)) {
                if (prefsReady) prefs.putBytes("touch", &calibration, sizeof(calibration));
                target = -1;
            } else {
                target = 0;
            }
            draw();
        } else {
            tap(raw);
        }
    }
}

void pumpAudio() {
    if (!playing) return;
    updatePosition();

    portENTER_CRITICAL(&audioLock);
    const size_t space = audioCapacity - queued;
    portEXIT_CRITICAL(&audioLock);
    if (loadedPosition == track.size() && position == track.size()) {
        if (chapter + 1 < int(chapters.size()) && openChapter(chapter + 1)) play();
        else halt();
        save();
        draw();
        return;
    }

    int16_t pcm[512];
    const size_t bytes = std::min<size_t>({sizeof(pcm), space * sizeof(int16_t),
                                  track.size() - loadedPosition});
    if (!bytes) return;
    if (track.read(reinterpret_cast<uint8_t*>(pcm), bytes) != bytes) {
        halt();
        save();
        error = "SD read failed";
        draw();
        return;
    }
    loadedPosition += bytes;

    portENTER_CRITICAL(&audioLock);
    size_t writeHead = (readHead + queued) % audioCapacity;
    const size_t samplesRead = bytes / sizeof(int16_t);
    for (size_t i = 0; i < samplesRead; ++i) {
        audioBuffer[writeHead] = pcm[i];
        writeHead = (writeHead + 1) % audioCapacity;
    }
    queued += samplesRead;
    if (queued >= audioCapacity / 2 || loadedPosition == track.size()) deliverAudio = true;
    portEXIT_CRITICAL(&audioLock);
}

bool selectFolder(const String& path) {
    halt();
    track.close();
    chapters.clear();
    error = nullptr;
    playbackFolder = path;
    Serial.println("MicroSD mounted; scanning chapters");
    // Read the FAT directory directly so boot does not open every audio file.
    const String directoryPath = String("/sd") + path;
    if (DIR* directory = opendir(directoryPath.c_str())) {
        while (dirent* entry = readdir(directory)) {
            String name = entry->d_name;
            if (entry->d_type != DT_DIR && !name.startsWith(".") && name.endsWith(".pcm")) {
                chapters.push_back(name);
            }
        }
        closedir(directory);
    }
    Serial.printf("Chapter scan complete: %u files\n", unsigned(chapters.size()));
    if (chapters.empty()) {
        error = "No chapters in this folder";
        return false;
    }
    std::sort(chapters.begin(), chapters.end());
    String record = prefsReady && prefs.isKey("bookmark") ? prefs.getString("bookmark") : String();
    int split = record.indexOf('\n');
    if (split >= 0) {
        String name = record.substring(0, split);
        String prefix = path + "/";
        if (name.startsWith(prefix)) name.remove(0, prefix.length());
        auto match = std::find(chapters.begin(), chapters.end(), name);
        if (match != chapters.end()) {
            return openChapter(match - chapters.begin(), strtoul(record.c_str() + split + 1, nullptr, 10));
        }
    }
    return openChapter(0);
}

bool cardReady = false;

void loadCard() {
    SPI.begin(18, 19, 23, sdSelect);
    if (!SD.begin(sdSelect, SPI, 10000000)) {
        error = "MicroSD unavailable";
        return;
    }
    cardReady = true;
    String record = prefsReady && prefs.isKey("bookmark") ? prefs.getString("bookmark") : String();
    if (record.startsWith("/Downloads/")) {
        const int end = record.indexOf('/', sizeof("/Downloads/") - 1);
        if (end > 0) {
            String path = record.substring(0, end);
            if (SD.exists(path + "/title.txt") && selectFolder(path)) return;
        }
    }
    selectFolder(folder);
}
}  // namespace

void setup() {
    Serial.begin(115200);
    wifiOnlyBoot = wifiBootRequest == wifiBootMagic;
    wifiBootRequest = 0;
    screen.init();
    screen.setRotation(1);
    screen.fillScreen(background);
    screen.setTextColor(TFT_WHITE);
    screen.drawCentreString("Reading microSD...", 160, 110, 2);
    Serial.println("CYD display initialized; checking microSD");
    pinMode(touchSelect, OUTPUT);
    digitalWrite(touchSelect, HIGH);
    pinMode(touchClock, OUTPUT);
    pinMode(touchOut, OUTPUT);
    pinMode(touchIn, INPUT);
    pinMode(touchIrq, INPUT);
    prefsReady = prefs.begin("cyd-audiobook");
    if (prefsReady) volume = constrain(prefs.getUChar("volume", 3), 0, 10);
    if (!prefsReady || prefs.getBytesLength("touch") != sizeof(calibration) ||
        prefs.getBytes("touch", &calibration, sizeof(calibration)) != sizeof(calibration) ||
        !validCalibration(calibration)) target = 0;
    loadCard();
    draw();
    if (wifiOnlyBoot) {
        Serial.println("CYD Wi-Fi mode; Bluetooth is off");
        openServer();
        if (recentError) Serial.printf("CYD catalog: %s\n", recentError);
        else Serial.printf("CYD catalog: recent listen %s\n", recentListen.book.id.isEmpty() ? "empty" : "loaded");
    } else if (cardReady) {
        Serial.println("Starting Bluetooth");
        initAudio();
    } else {
        Serial.println(error);
    }
    Serial.printf("CYD audiobook: %u chapters, Bluetooth target %s\n",
                  unsigned(chapters.size()), headphoneName.c_str());
    draw();
}

void loop() {
    static bool wasConnected = false;
    const bool connected = headphonesConnected.load();
    if (disconnectPending.exchange(false) && playing) {
        halt();
        save();
        draw();
    }
    if (connected != wasConnected) {
        wasConnected = connected;
        draw();
    }
    // A direct USB check uses the same catalog entry point as the Server button.
    if (Serial.available() && Serial.read() == '?' && libraryView != LibraryView::Download && target < 0) {
        openServer();
        if (wifiOnlyBoot) {
            if (recentError) Serial.printf("CYD catalog: %s\n", recentError);
            else Serial.printf("CYD catalog: recent listen %s\n", recentListen.book.id.isEmpty() ? "empty" : "loaded");
        }
    }
    pumpAudio();
    pollTouch();
    if (libraryView == LibraryView::Download) {
        static auto previousState = Downloads::Idle;
        static unsigned previousParts = 0;
        auto current = downloads.state.load();
        auto parts = downloads.completed.load();
        if (current != previousState || parts != previousParts) {
            previousState = current;
            previousParts = parts;
            draw();
        }
    }
    if (playing && millis() - savedAt >= 15000) save();
    static uint32_t displayAt = 0;
    if (playing && millis() - displayAt >= 1000) {
        showTime();
        displayAt = millis();
    }
    delay(1);
}
