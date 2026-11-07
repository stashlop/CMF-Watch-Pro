// Framebuffer compositing: JPEG decode, additive glyph text, battery-meter patches, cross-fade.
// File formats are written by esp32/assets.py (which also has a PC model of this code: compose()).
#pragma once
#include <stddef.h>
#include <stdint.h>

#include "assets_manifest.h"
#include "board.h"

uint16_t *fbAlloc();  // LCD_W x LCD_H RGB565 in PSRAM
void fbCopy(uint16_t *dst, const uint16_t *src);
void fbBlend(uint16_t *dst, const uint16_t *a, const uint16_t *b, uint8_t t);  // t: 0 = a, 255 = b

bool jpegDecode(const uint8_t *data, size_t len, uint16_t *target);

struct Glyph {
  uint8_t ch;
  int16_t adv;  // 1/16 px
  int16_t xo, yo;
  uint16_t w, h;
  const uint16_t *px;
};

struct Font {
  uint8_t *raw = nullptr;
  int16_t mid = 0;  // baseline offset for 'm' anchor, 1/16 px
  uint16_t n = 0;
  Glyph g[48];
  const Glyph *find(char c) const;
};

bool fontLoad(Font &f, const char *path);
void fontFree(Font &f);
void textDraw(uint16_t *fb, const Font &f, const OmniSpot &s, const char *str);

struct Patch {
  uint16_t x, y, w, h;
  const uint16_t *px;
};

struct Meter {
  uint8_t *raw = nullptr;
  uint8_t nNormal = 0, nRed = 0;
  Patch p[OMNI_SEGS + 8];
};

bool meterLoad(Meter &m, const char *path);
void meterFree(Meter &m);
void meterApply(uint16_t *fb, const Meter &m, int battery);
