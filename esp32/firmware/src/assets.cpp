#include "assets.h"

#include <Arduino.h>
#include <LittleFS.h>
#include <string.h>

#include "inflate.h"

static const size_t CACHE_BUDGET = 4u * 1024 * 1024;
static const int MAX_ENTRIES = 160;
static const int PATH_LEN = 24;

struct Entry {
  char path[PATH_LEN];
  uint8_t *data;
  uint32_t len;
  uint32_t stamp;
  bool loading;
  bool used;
};

static Entry entries[MAX_ENTRIES];
static SemaphoreHandle_t mtx;
static QueueHandle_t queue;
static size_t cacheUsed;
static uint32_t clockTick;
static int pinned = -1;  // entry the main task is decoding; never evicted

static int findLocked(const char *path) {
  for (int i = 0; i < MAX_ENTRIES; i++)
    if (entries[i].used && strncmp(entries[i].path, path, PATH_LEN) == 0) return i;
  return -1;
}

static void evictLocked(size_t need) {
  while (cacheUsed + need > CACHE_BUDGET) {
    int victim = -1;
    for (int i = 0; i < MAX_ENTRIES; i++) {
      Entry &e = entries[i];
      if (!e.used || e.loading || i == pinned || !e.data) continue;
      if (victim < 0 || e.stamp < entries[victim].stamp) victim = i;
    }
    if (victim < 0) return;
    free(entries[victim].data);
    cacheUsed -= entries[victim].len;
    entries[victim] = Entry{};
  }
}

static uint8_t *readFile(const char *path, uint32_t *len) {
  File f = LittleFS.open(path, "r");
  if (!f) return nullptr;
  size_t n = f.size();
  auto *buf = (uint8_t *)heap_caps_malloc(n ? n : 1, MALLOC_CAP_SPIRAM | MALLOC_CAP_8BIT);
  if (buf && f.read(buf, n) != n) {
    free(buf);
    buf = nullptr;
  }
  f.close();
  *len = buf ? (uint32_t)n : 0;
  return buf;
}

// Returns the entry index with data loaded (or -1). Pins it if `pin`.
static int load(const char *path, bool pin) {
  for (;;) {
    xSemaphoreTake(mtx, portMAX_DELAY);
    int i = findLocked(path);
    if (i >= 0 && !entries[i].loading) {
      entries[i].stamp = ++clockTick;
      if (pin) pinned = i;
      xSemaphoreGive(mtx);
      return entries[i].data ? i : -1;
    }
    if (i >= 0) {  // another task is loading it
      xSemaphoreGive(mtx);
      vTaskDelay(1);
      continue;
    }
    int slot = -1;
    for (int k = 0; k < MAX_ENTRIES && slot < 0; k++)
      if (!entries[k].used) slot = k;
    if (slot < 0) {
      evictLocked(CACHE_BUDGET);  // table full: drop everything evictable
      for (int k = 0; k < MAX_ENTRIES && slot < 0; k++)
        if (!entries[k].used) slot = k;
    }
    if (slot < 0) {
      xSemaphoreGive(mtx);
      return -1;
    }
    Entry &e = entries[slot];
    e = Entry{};
    strncpy(e.path, path, PATH_LEN - 1);
    e.used = e.loading = true;
    xSemaphoreGive(mtx);

    uint32_t len = 0;
    uint8_t *data = readFile(path, &len);

    xSemaphoreTake(mtx, portMAX_DELAY);
    evictLocked(len);
    e.data = data;
    e.len = len;
    e.loading = false;
    e.stamp = ++clockTick;
    cacheUsed += len;
    if (pin) pinned = slot;
    xSemaphoreGive(mtx);
    return data ? slot : -1;
  }
}

static void prefetchTask(void *) {
  char path[PATH_LEN];
  for (;;) {
    if (xQueueReceive(queue, path, portMAX_DELAY) == pdTRUE) load(path, false);
  }
}

bool assetsBegin(char *buildIdOut, size_t n) {
  if (!LittleFS.begin(false, "/littlefs", 10, "spiffs")) return false;
  mtx = xSemaphoreCreateMutex();
  queue = xQueueCreate(64, PATH_LEN);
  xTaskCreatePinnedToCore(prefetchTask, "prefetch", 4096, nullptr, 1, nullptr, 0);
  File f = LittleFS.open("/build.txt", "r");
  if (!f) return false;
  size_t got = f.readBytes(buildIdOut, n - 1);
  buildIdOut[got] = 0;
  f.close();
  return true;
}

Blob assetGet(const char *path) {
  int i = load(path, true);
  if (i < 0) return {nullptr, 0};
  return {entries[i].data, entries[i].len};
}

void assetPrefetch(const char *path) {
  xSemaphoreTake(mtx, portMAX_DELAY);
  bool have = findLocked(path) >= 0;
  xSemaphoreGive(mtx);
  if (have) return;
  char p[PATH_LEN] = {0};
  strncpy(p, path, PATH_LEN - 1);
  xQueueSend(queue, p, 0);
}

uint8_t *assetLoadInflated(const char *path, size_t *len) {
  uint32_t n = 0;
  uint8_t *raw = readFile(path, &n);
  *len = 0;
  if (!raw) return nullptr;
  if (n < 8 || memcmp(raw, "OZ1\0", 4) != 0) {
    *len = n;
    return raw;
  }
  uint32_t outLen = raw[4] | (raw[5] << 8) | (raw[6] << 16) | ((uint32_t)raw[7] << 24);
  auto *out = (uint8_t *)heap_caps_malloc(outLen ? outLen : 1, MALLOC_CAP_SPIRAM | MALLOC_CAP_8BIT);
  bool ok = out && zlibInflate(raw + 8, n - 8, out, outLen) == outLen;
  free(raw);
  if (!ok) {
    free(out);
    return nullptr;
  }
  *len = outLen;
  return out;
}
