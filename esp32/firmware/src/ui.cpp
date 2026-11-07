#include "ui.h"

#include <Arduino.h>
#include <math.h>

#include "assets.h"
#include "assets_manifest.h"
#include "gfx.h"
#include "hw.h"

namespace {

enum Mode { HOME, SELECT, CONFIRM, INFO, TRANSFORM, FADE, FACE };
const char *const MODE_NAMES[] = {"home", "select", "confirm", "info", "transform", "fade", "face"};

const uint32_t HOLD_MS = 600;           // studio.HOLD_SECONDS
const uint32_t HOLD_FEEDBACK_MS = 150;  // show the hold ring after this
const uint32_t SCREEN_TIMEOUT_MS = 15000;
const uint32_t MENU_TIMEOUT_MS = 30000;
const uint32_t TURN_FRAME_MS = 45;
const int TAP_SLOP = 12;
const int SWIPE_STEP = 40;
const uint16_t OMNI_GREEN = 0x3FE2;  // #39FF14 in RGB565

uint16_t *bg, *work, *clean, *faceBuf;  // PSRAM framebuffers
Font fonts[4];                          // clock, sec, date, label for the loaded theme
Meter meter;
int loadedTheme = -1;
int bgBattery = -999;

Mode mode = HOME;
uint32_t modeStart = 0;
int sel = 0;
int active = -1;  // alien whose face is worn, -1 = Omnitrix home
int turnQueue = 0, turnSub = 1;
uint32_t turnNext = 0;
int shownFrame = -1;

struct tm now = {};
int lastSecDrawn = -1;
int battery = 100;
bool hasBattery = false;
uint32_t lastBatteryRead = 0, lastRtcRead = 0;

bool screenOn = true;
uint32_t lastInput = 0;

struct TouchState {
  bool down = false, moved = false, held = false, ring = false;
  int16_t x0 = 0, y0 = 0, x = 0, y = 0, anchorX = 0;
  uint32_t t0 = 0;
  int misses = 0;
} touch;

// ---- helpers ------------------------------------------------------------------------
int wrap(int i) { return ((i % OMNI_N_ALIENS) + OMNI_N_ALIENS) % OMNI_N_ALIENS; }

void showJpeg(const char *path) {
  Blob b = assetGet(path);
  if (!jpegDecode(b.data, b.len, work)) {
    Serial.printf("[ui] cannot show %s\n", path);
    return;
  }
  displayPush(work);
}

void showFrame(char kind, int a, int k) {
  char p[24];
  if (kind == 'x' && a < 0) snprintf(p, sizeof p, "/x/s_%d.jpg", k);
  else if (kind == 'i') snprintf(p, sizeof p, "/i/%d.jpg", a);
  else snprintf(p, sizeof p, "/%c/%d_%d.jpg", kind, a, k);
  showJpeg(p);
}

void prefetchFrame(char kind, int a, int k) {
  char p[24];
  if (kind == 'x' && a < 0) snprintf(p, sizeof p, "/x/s_%d.jpg", k);
  else if (kind == 'i') snprintf(p, sizeof p, "/i/%d.jpg", a);
  else snprintf(p, sizeof p, "/%c/%d_%d.jpg", kind, a, k);
  assetPrefetch(p);
}

void prefetchAround(int s) {
  for (int k = 0; k < OMNI_SEL_SUB; k++) {
    prefetchFrame('s', wrap(s + 1), k);
    prefetchFrame('s', wrap(s - 1), k);
  }
  for (int k = 0; k < OMNI_CONFIRM_FRAMES; k++) prefetchFrame('c', s, k);
  prefetchFrame('i', s, 0);
}

void prefetchTransform(int s) {
  for (int k = 0; k < OMNI_XF_SHARED; k++) prefetchFrame('x', -1, k);
  for (int k = 0; k < OMNI_XF_ALIEN; k++) prefetchFrame('x', s, k);
}

// ---- faces (home = theme 0, alien i = theme i+1) ----------------------------------------
int displayedBattery() { return hasBattery ? battery : 100; }

void ensureTheme(int theme) {
  if (theme == loadedTheme && bgBattery == displayedBattery()) return;
  char p[24];
  if (theme != loadedTheme) {
    static const char *const keys[4] = {"clock", "sec", "date", "label"};
    for (int k = 0; k < 4; k++) {
      snprintf(p, sizeof p, "/t/%d_%s.fnt", theme, keys[k]);
      if (!fontLoad(fonts[k], p)) Serial.printf("[ui] font %s failed\n", p);
    }
    snprintf(p, sizeof p, "/m/%d.mtr", theme);
    if (!meterLoad(meter, p)) Serial.printf("[ui] meter %s failed\n", p);
  }
  snprintf(p, sizeof p, "/f/%d.jpg", theme);
  Blob b = assetGet(p);
  if (!jpegDecode(b.data, b.len, bg)) Serial.printf("[ui] face %s failed\n", p);
  meterApply(bg, meter, displayedBattery());
  loadedTheme = theme;
  bgBattery = displayedBattery();
}

void composeFace(uint16_t *dst) {
  fbCopy(dst, bg);
  char s[48];
  strftime(s, sizeof s, "%a  %d %b", &now);
  for (char *c = s; *c; c++) *c = (char)toupper(*c);
  textDraw(dst, fonts[2], OMNI_SPOT_DATE, s);
  strftime(s, sizeof s, "%H:%M", &now);
  textDraw(dst, fonts[0], OMNI_SPOT_CLOCK, s);
  strftime(s, sizeof s, "%S", &now);
  textDraw(dst, fonts[1], OMNI_SPOT_SEC, s);
  char energy[16];
  if (hasBattery) snprintf(energy, sizeof energy, "ENERGY %d%%", battery);
  else snprintf(energy, sizeof energy, "USB POWER");
  if (loadedTheme == 0) snprintf(s, sizeof s, "%s", energy);
  else snprintf(s, sizeof s, "%s  /  %s", OMNI_THEME_NAMES[loadedTheme], energy);
  textDraw(dst, fonts[3], OMNI_SPOT_LABEL, s);
}

void drawFaceNow() {
  ensureTheme(active < 0 ? 0 : active + 1);
  composeFace(work);
  displayPush(work);
  lastSecDrawn = now.tm_sec;
}

// ---- mode changes -----------------------------------------------------------------
void setMode(Mode m, uint32_t t) {
  mode = m;
  modeStart = t;
  shownFrame = -1;
  Serial.printf("[ui] %s (alien %s)\n", MODE_NAMES[m], OMNI_THEME_NAMES[sel + 1]);
  switch (m) {
    case HOME:
    case FACE:
      drawFaceNow();
      break;
    case SELECT:
      turnQueue = 0;
      turnSub = 1;
      showFrame('s', sel, 0);
      prefetchAround(sel);
      break;
    case INFO:
      showFrame('i', sel, 0);
      prefetchTransform(sel);
      break;
    case CONFIRM:
      prefetchTransform(sel);
      break;
    default:
      break;
  }
}

void wearOrHome(uint32_t t) { setMode(active >= 0 ? FACE : HOME, t); }

void turn(int step) {
  if (mode != SELECT) return;
  turnQueue += step;
  if (turnQueue > OMNI_N_ALIENS) turnQueue = OMNI_N_ALIENS;
  if (turnQueue < -OMNI_N_ALIENS) turnQueue = -OMNI_N_ALIENS;
}

void startTransform(uint32_t t) {
  if (mode == TRANSFORM || mode == FADE) return;
  turnQueue = 0;
  setMode(TRANSFORM, t);
}

// ---- events (studio.py side_button / back / on_release / _check_hold) -----------------
void onSide(uint32_t t) {
  if (mode == HOME || mode == FACE || mode == INFO) setMode(SELECT, t);
  else if (mode == SELECT) wearOrHome(t);
}

void onBack(uint32_t t) {
  if (mode == SELECT) wearOrHome(t);
  else if (mode == INFO) setMode(SELECT, t);
  else if (mode == FACE) {
    active = -1;
    setMode(HOME, t);
  }
}

void onTap(int x, int y, uint32_t t) {
  float dx = x - OMNI_CX, dy = y - OMNI_CY;
  float r = sqrtf(dx * dx + dy * dy);
  if ((mode == HOME || mode == FACE) && r < OMNI_R_RING) {
    setMode(SELECT, t);
  } else if (mode == SELECT && turnQueue == 0) {
    if (r < OMNI_R_CORE) {
      setMode(CONFIRM, t);
    } else if (fabsf(r - OMNI_R_ORBIT) < 22) {
      float ang = atan2f(dy, dx) * 180.0f / (float)M_PI + 90.0f;
      float a = fmodf(ang + 180.0f, 360.0f);
      if (a < 0) a += 360.0f;
      turn((int)lroundf((a - 180.0f) / (360.0f / OMNI_N_ALIENS)));
    }
  }
}

void holdRing(float p) {
  fbCopy(work, clean);
  int n = (int)(p * 24);
  for (int i = 0; i < n; i++) {
    float a = (-90.0f + i * 15.0f) * (float)M_PI / 180.0f;
    int cx = touch.x0 + (int)(34 * cosf(a)), cy = touch.y0 + (int)(34 * sinf(a));
    for (int yy = -3; yy <= 3; yy++)
      for (int xx = -3; xx <= 3; xx++) {
        int px = cx + xx, py = cy + yy;
        if (xx * xx + yy * yy <= 9 && px >= 0 && px < LCD_W && py >= 0 && py < LCD_H) work[py * LCD_W + px] = OMNI_GREEN;
      }
  }
  displayPush(work);
}

void wake(uint32_t t) {
  screenOn = true;
  displaySetOn(true);
  displayBrightness(200);
  wearOrHome(t);
}

void sleepScreen() {
  screenOn = false;
  displayBrightness(0);
  displaySetOn(false);
  Serial.println("[ui] screen off");
}

// ---- input polling ----------------------------------------------------------------
void pollInput(uint32_t t) {
  bool side = pmuPwrShort();
  bool back = bootPressed();
  int16_t x, y;
  bool down = touchRead(x, y);

  if (!screenOn) {
    if (side || back || down) {
      lastInput = t;
      wake(t);
      touch = TouchState{};
      touch.down = down;  // swallow the waking touch
      touch.held = true;
    }
    return;
  }
  if (side || back || down) lastInput = t;
  if (side) onSide(t);
  if (back) onBack(t);

  bool holdable = (mode == SELECT || mode == INFO);
  if (down) {
    touch.misses = 0;
    if (!touch.down) {
      touch = TouchState{};
      touch.down = true;
      touch.x0 = touch.x = touch.anchorX = x;
      touch.y0 = touch.y = y;
      touch.t0 = t;
      return;
    }
    touch.x = x;
    touch.y = y;
    if (abs(x - touch.x0) > TAP_SLOP || abs(y - touch.y0) > TAP_SLOP) touch.moved = true;
    if (mode == SELECT && abs(x - touch.anchorX) > SWIPE_STEP) {
      turn(x > touch.anchorX ? -1 : 1);
      touch.anchorX = x;
    }
    uint32_t held = t - touch.t0;
    if (holdable && !touch.moved && !touch.held && held >= HOLD_FEEDBACK_MS) {
      if (!touch.ring) {
        fbCopy(clean, work);
        touch.ring = true;
      }
      if (held >= HOLD_MS) {
        touch.held = true;
        touch.ring = false;
        startTransform(t);
      } else {
        holdRing((float)(held - HOLD_FEEDBACK_MS) / (HOLD_MS - HOLD_FEEDBACK_MS));
      }
    }
    return;
  }
  if (touch.down && ++touch.misses >= 2) {  // two empty polls = finger lifted
    touch.down = false;
    if (touch.ring) {
      fbCopy(work, clean);
      displayPush(work);
      touch.ring = false;
    }
    if (!touch.moved && !touch.held && t - touch.t0 < HOLD_MS) onTap(touch.x0, touch.y0, t);
  }
}

// ---- per-mode animation -------------------------------------------------------------
void tickSelect(uint32_t t) {
  if (turnQueue == 0 || t < turnNext) return;
  int dir = turnQueue > 0 ? 1 : -1;
  if (dir > 0) {
    if (turnSub < OMNI_SEL_SUB) {
      showFrame('s', sel, turnSub++);
    } else {
      sel = wrap(sel + 1);
      showFrame('s', sel, 0);
      turnSub = 1;
      turnQueue--;
      prefetchAround(sel);
    }
  } else {
    int j = wrap(sel - 1);
    if (turnSub < OMNI_SEL_SUB) {
      showFrame('s', j, OMNI_SEL_SUB - turnSub++);
    } else {
      sel = j;
      showFrame('s', sel, 0);
      turnSub = 1;
      turnQueue++;
      prefetchAround(sel);
    }
  }
  turnNext = t + TURN_FRAME_MS;
}

void tickConfirm(uint32_t t) {
  uint32_t el = t - modeStart;
  int k = (int)((uint64_t)el * OMNI_CONFIRM_FRAMES / OMNI_CONFIRM_MS);
  if (k >= OMNI_CONFIRM_FRAMES) {
    if (shownFrame == OMNI_CONFIRM_FRAMES - 1) {
      ensureTheme(sel + 1);  // load the alien face now, while the info card is up next
      setMode(INFO, t);
      return;
    }
    k = OMNI_CONFIRM_FRAMES - 1;
  }
  if (k != shownFrame) {
    showFrame('c', sel, k);
    shownFrame = k;
  }
}

void tickTransform(uint32_t t) {
  uint32_t el = t - modeStart;
  int k = (int)((uint64_t)el * OMNI_XF_FPS / 1000);
  const int total = OMNI_XF_SHARED + OMNI_XF_ALIEN;
  if (k >= total) {
    if (shownFrame < total - 1) k = total - 1;  // always show the last frame before fading
    else {
      fbCopy(clean, work);  // last transform frame
      active = sel;
      ensureTheme(active + 1);
      composeFace(faceBuf);
      setMode(FADE, t);
      return;
    }
  }
  if (k != shownFrame) {
    if (k < OMNI_XF_SHARED) showFrame('x', -1, k);
    else showFrame('x', sel, k - OMNI_XF_SHARED);
    shownFrame = k;
  }
}

void tickFade(uint32_t t) {
  uint32_t el = t - modeStart;
  if (el >= OMNI_FADE_MS) {
    setMode(FACE, t);
    return;
  }
  float x = (float)el / OMNI_FADE_MS;
  float e = x < 0.5f ? 4 * x * x * x : 1 - powf(-2 * x + 2, 3) / 2;  // gfx.ease_in_out
  fbBlend(work, clean, faceBuf, (uint8_t)(e * 255));
  displayPush(work);
}

}  // namespace

// ---- public -----------------------------------------------------------------------
bool uiBegin() {
  bg = fbAlloc();
  work = fbAlloc();
  clean = fbAlloc();
  faceBuf = fbAlloc();
  if (!bg || !work || !clean || !faceBuf) return false;
  rtcNow(now);
  battery = pmuBattery();
  hasBattery = battery >= 0;
  if (!hasBattery) battery = 100;
  uint32_t t = millis();
  lastInput = t;
  setMode(HOME, t);
  return true;
}

void uiLoop(uint32_t t) {
  pollInput(t);

  if (t - lastRtcRead >= 200) {
    lastRtcRead = t;
    rtcNow(now);
  }
  if (t - lastBatteryRead >= 30000) {
    lastBatteryRead = t;
    int b = pmuBattery();
    hasBattery = b >= 0;
    battery = hasBattery ? b : 100;
  }
  if (!screenOn) return;

  switch (mode) {
    case HOME:
    case FACE:
      if (now.tm_sec != lastSecDrawn) drawFaceNow();
      if (t - lastInput > SCREEN_TIMEOUT_MS) sleepScreen();
      break;
    case SELECT:
      tickSelect(t);
      if (t - lastInput > MENU_TIMEOUT_MS) wearOrHome(t);
      break;
    case INFO:
      if (t - lastInput > MENU_TIMEOUT_MS) wearOrHome(t);
      break;
    case CONFIRM:
      tickConfirm(t);
      break;
    case TRANSFORM:
      tickTransform(t);
      lastInput = t;
      break;
    case FADE:
      tickFade(t);
      lastInput = t;
      break;
  }
}

void uiSetTime(const struct tm &t) {
  rtcSet(t);
  rtcNow(now);
  lastSecDrawn = -1;
}

void uiPrintStatus() {
  char s[32];
  strftime(s, sizeof s, "%Y-%m-%d %H:%M:%S", &now);
  Serial.printf("time %s  battery %s%d%%  charging %d  mode %s  alien %s  worn %s  screen %s\n", s,
                hasBattery ? "" : "(none) ", battery, pmuCharging(), MODE_NAMES[mode], OMNI_THEME_NAMES[sel + 1],
                active >= 0 ? OMNI_THEME_NAMES[active + 1] : "-", screenOn ? "on" : "off");
}
