#include "gfx.h"

#include <Arduino.h>
#include <JPEGDEC.h>
#include <string.h>

#include "assets.h"

static const size_t FB_PIXELS = (size_t)LCD_W * LCD_H;

uint16_t *fbAlloc() {
  auto *p = (uint16_t *)heap_caps_malloc(FB_PIXELS * 2, MALLOC_CAP_SPIRAM | MALLOC_CAP_8BIT);
  if (p) memset(p, 0, FB_PIXELS * 2);
  return p;
}

void fbCopy(uint16_t *dst, const uint16_t *src) { memcpy(dst, src, FB_PIXELS * 2); }

void fbBlend(uint16_t *dst, const uint16_t *a, const uint16_t *b, uint8_t t) {
  const uint32_t tb = t, ta = 255 - t;
  for (size_t i = 0; i < FB_PIXELS; i++) {
    uint32_t pa = a[i], pb = b[i];
    uint32_t r = (((pa >> 11) * ta + (pb >> 11) * tb) / 255);
    uint32_t g = ((((pa >> 5) & 63) * ta + ((pb >> 5) & 63) * tb) / 255);
    uint32_t bl = (((pa & 31) * ta + (pb & 31) * tb) / 255);
    dst[i] = (uint16_t)((r << 11) | (g << 5) | bl);
  }
}

static inline uint16_t add565(uint16_t a, uint16_t b) {
  uint32_t r = (a >> 11) + (b >> 11);
  uint32_t g = ((a >> 5) & 63) + ((b >> 5) & 63);
  uint32_t bl = (a & 31) + (b & 31);
  if (r > 31) r = 31;
  if (g > 63) g = 63;
  if (bl > 31) bl = 31;
  return (uint16_t)((r << 11) | (g << 5) | bl);
}

// ---- JPEG -------------------------------------------------------------------------
static JPEGDEC jpeg;
static uint16_t *jpegTarget;

static int jpegDraw(JPEGDRAW *d) {
  int w = d->iWidth;
  if (d->x + w > LCD_W) w = LCD_W - d->x;
  for (int row = 0; row < d->iHeight; row++) {
    int y = d->y + row;
    if (y >= LCD_H) break;
    memcpy(jpegTarget + (size_t)y * LCD_W + d->x, d->pPixels + (size_t)row * d->iWidth, (size_t)w * 2);
  }
  return 1;
}

bool jpegDecode(const uint8_t *data, size_t len, uint16_t *target) {
  if (!data || !len) return false;
  jpegTarget = target;
  if (!jpeg.openRAM((uint8_t *)data, (int)len, jpegDraw)) return false;
  jpeg.setPixelType(RGB565_LITTLE_ENDIAN);
  int ok = jpeg.decode(0, 0, 0);
  jpeg.close();
  return ok == 1;
}

// ---- fonts ('OFN1') -----------------------------------------------------------------
static uint16_t rd16(const uint8_t *p) { return (uint16_t)(p[0] | (p[1] << 8)); }
static uint32_t rd32(const uint8_t *p) { return p[0] | (p[1] << 8) | (p[2] << 16) | ((uint32_t)p[3] << 24); }

const Glyph *Font::find(char c) const {
  for (uint16_t i = 0; i < n; i++)
    if (g[i].ch == (uint8_t)c) return &g[i];
  return nullptr;
}

bool fontLoad(Font &f, const char *path) {
  fontFree(f);
  size_t len = 0;
  uint8_t *raw = assetLoadInflated(path, &len);
  if (!raw || len < 12 || memcmp(raw, "OFN1", 4) != 0) {
    free(raw);
    return false;
  }
  uint16_t n = rd16(raw + 4);
  if (n > sizeof(f.g) / sizeof(f.g[0])) n = sizeof(f.g) / sizeof(f.g[0]);
  f.raw = raw;
  f.mid = (int16_t)rd16(raw + 6);
  f.n = n;
  for (uint16_t i = 0; i < n; i++) {
    const uint8_t *r = raw + 12 + 16 * i;
    Glyph &g = f.g[i];
    g.ch = r[0];
    g.adv = (int16_t)rd16(r + 2);
    g.xo = (int16_t)rd16(r + 4);
    g.yo = (int16_t)rd16(r + 6);
    g.w = rd16(r + 8);
    g.h = rd16(r + 10);
    uint32_t off = rd32(r + 12);
    g.px = (g.w && g.h && off + (size_t)g.w * g.h * 2 <= len) ? (const uint16_t *)(raw + off) : nullptr;
  }
  return true;
}

void fontFree(Font &f) {
  free(f.raw);
  f.raw = nullptr;
  f.n = 0;
}

static void addBlit(uint16_t *fb, int x, int y, const Glyph &g) {
  for (int row = 0; row < g.h; row++) {
    int yy = y + row;
    if (yy < 0 || yy >= LCD_H) continue;
    const uint16_t *src = g.px + (size_t)row * g.w;
    uint16_t *dst = fb + (size_t)yy * LCD_W;
    for (int col = 0; col < g.w; col++) {
      int xx = x + col;
      if (xx < 0 || xx >= LCD_W || !src[col]) continue;
      dst[xx] = add565(dst[xx], src[col]);
    }
  }
}

// Same integer layout as esp32/assets.py text_layout()
void textDraw(uint16_t *fb, const Font &f, const OmniSpot &s, const char *str) {
  if (!f.raw) return;
  const int32_t sp = s.spacing * 16;
  int32_t total = 0;
  size_t count = 0;
  for (const char *c = str; *c; c++) {
    const Glyph *g = f.find(*c);
    if (!g) continue;
    total += g->adv + sp;
    count++;
  }
  if (count) total -= sp;
  int32_t x = s.x * 16 - (s.h == 'm' ? total / 2 : total);
  int32_t by = (s.v == 'm') ? ((s.y * 16 + f.mid + 8) >> 4) : s.y;
  for (const char *c = str; *c; c++) {
    const Glyph *g = f.find(*c);
    if (!g) continue;
    if (g->px) addBlit(fb, (x >> 4) + g->xo, by + g->yo, *g);
    x += g->adv + sp;
  }
}

// ---- battery meter ('OMT2') ---------------------------------------------------------
bool meterLoad(Meter &m, const char *path) {
  meterFree(m);
  size_t len = 0;
  uint8_t *raw = assetLoadInflated(path, &len);
  if (!raw || len < 8 || memcmp(raw, "OMT2", 4) != 0) {
    free(raw);
    return false;
  }
  m.nNormal = raw[4];
  m.nRed = raw[5];
  size_t total = (size_t)m.nNormal + m.nRed;
  if (total > sizeof(m.p) / sizeof(m.p[0])) {
    free(raw);
    return false;
  }
  size_t off = 8;
  for (size_t i = 0; i < total; i++) {
    if (off + 8 > len) {
      free(raw);
      return false;
    }
    Patch &p = m.p[i];
    p.x = rd16(raw + off);
    p.y = rd16(raw + off + 2);
    p.w = rd16(raw + off + 4);
    p.h = rd16(raw + off + 6);
    p.px = (const uint16_t *)(raw + off + 8);
    off += 8 + (size_t)p.w * p.h * 2;
    if (off > len) {
      free(raw);
      return false;
    }
  }
  m.raw = raw;
  return true;
}

void meterFree(Meter &m) {
  free(m.raw);
  m.raw = nullptr;
  m.nNormal = m.nRed = 0;
}

static void pastePatch(uint16_t *fb, const Patch &p) {
  for (int row = 0; row < p.h; row++) {
    int y = p.y + row;
    if (y >= LCD_H) break;
    int w = (p.x + p.w > LCD_W) ? LCD_W - p.x : p.w;
    memcpy(fb + (size_t)y * LCD_W + p.x, p.px + (size_t)row * p.w, (size_t)w * 2);
  }
}

// Patches 1..lit over the unlit base give exactly the face with `lit` segments (see assets.meter_pack)
void meterApply(uint16_t *fb, const Meter &m, int battery) {
  if (!m.raw) return;
  if (battery < 0) battery = 0;
  if (battery > 100) battery = 100;
  int lit = (battery * OMNI_SEGS + 50) / 100;
  if (battery <= OMNI_LOW_BATTERY) {
    for (int i = 0; i <= lit && i < m.nRed; i++) pastePatch(fb, m.p[m.nNormal + i]);
  } else {
    for (int i = 0; i < lit && i < m.nNormal; i++) pastePatch(fb, m.p[i]);
  }
}
