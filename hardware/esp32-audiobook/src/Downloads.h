#pragma once

#include <Arduino.h>
#include <atomic>
#include <vector>

struct CatalogEntry {
    String id;
    String title;
};

class Downloads {
public:
    bool configure();
    bool catalog(const String& library, unsigned page, std::vector<CatalogEntry>& rows, bool& more);
    bool start(const String& book);
    void cancel() { cancelled = true; }
    void disconnect();

    enum State { Idle, Preparing, Transferring, Complete, Failed, Cancelled };
    std::atomic<State> state{Idle};
    std::atomic<unsigned> completed{0};
    std::atomic<unsigned> total{0};
    const char* error() const { return message.load(); }

private:
    bool connect();
    int request(const String& path, String& body, size_t maxBytes, bool post = false);
    bool fetch(const String& path, const String& file, uint32_t expected);
    void transfer();
    bool fail(const char* reason);

    String ssid;
    String password;
    String host;
    String token;
    String selected;
    std::atomic<bool> cancelled{false};
    std::atomic<const char*> message{nullptr};
};
