// Asset pack on LittleFS (built by `python -m esp32.assets`, uploaded with `pio run -t uploadfs`).
// A PSRAM cache with a background prefetch task on core 0 keeps animations from waiting on flash reads.
#pragma once
#include <stddef.h>
#include <stdint.h>

struct Blob {
  const uint8_t *data;
  size_t len;
};

bool assetsBegin(char *buildIdOut, size_t n);  // mounts LittleFS, reads build.txt
Blob assetGet(const char *path);               // cached; valid until the next assetGet on this task
void assetPrefetch(const char *path);          // queue a background load (no-op if cached)
uint8_t *assetLoadInflated(const char *path, size_t *len);  // malloc'd copy, 'OZ1' files inflated; caller frees
