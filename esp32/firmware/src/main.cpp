// Omnitrix firmware for the Waveshare ESP32-S3-Touch-AMOLED-2.06.
//
// Serial commands (115200 baud, newline-terminated):
//   time YYYY-MM-DD HH:MM:SS   set the RTC (python -m esp32.settime does this from the PC clock)
//   status                     print time, battery, mode
#include <Arduino.h>
#include <Wire.h>

#include "assets.h"
#include "assets_manifest.h"
#include "board.h"
#include "hw.h"
#include "ui.h"

SET_LOOP_TASK_STACK_SIZE(16 * 1024);

static bool ready = false;

static void setCompileTimeIfUnset() {
  struct tm t = {};
  if (rtcNow(t)) return;
  // __DATE__ "Nov  7 2026", __TIME__ "13:45:00"
  static const char months[] = "JanFebMarAprMayJunJulAugSepOctNovDec";
  char mon[4] = {0};
  int day, year, hh, mm, ss;
  sscanf(__DATE__, "%3s %d %d", mon, &day, &year);
  sscanf(__TIME__, "%d:%d:%d", &hh, &mm, &ss);
  t.tm_year = year - 1900;
  t.tm_mon = (int)((strstr(months, mon) - months) / 3);
  t.tm_mday = day;
  t.tm_hour = hh;
  t.tm_min = mm;
  t.tm_sec = ss;
  rtcSet(t);
  Serial.println("[rtc] was unset; set to build time. Run `python -m esp32.settime` for the exact time.");
}

static void handleLine(char *line) {
  int Y, M, D, h, m, s;
  if (sscanf(line, "time %d-%d-%d %d:%d:%d", &Y, &M, &D, &h, &m, &s) == 6) {
    struct tm t = {};
    t.tm_year = Y - 1900;
    t.tm_mon = M - 1;
    t.tm_mday = D;
    t.tm_hour = h;
    t.tm_min = m;
    t.tm_sec = s;
    uiSetTime(t);
    Serial.println("ok time");
  } else if (strncmp(line, "status", 6) == 0) {
    Serial.printf("omnitrix build %s  ready %d\n", OMNI_BUILD_ID, ready);
    if (ready) uiPrintStatus();
  } else if (line[0]) {
    Serial.println("commands: time YYYY-MM-DD HH:MM:SS | status");
  }
}

static void pollSerial() {
  static char buf[64];
  static size_t n = 0;
  while (Serial.available()) {
    char c = (char)Serial.read();
    if (c == '\r') continue;
    if (c == '\n') {
      buf[n] = 0;
      handleLine(buf);
      n = 0;
    } else if (n < sizeof buf - 1) {
      buf[n++] = c;
    }
  }
}

void setup() {
  Serial.begin(115200);
  delay(300);
  Serial.println("\n[omnitrix] booting");
  Wire.begin(I2C_SDA, I2C_SCL);
  Wire.setClock(400000);

  if (!displayBegin()) Serial.println("[display] init failed");
  if (!psramFound()) {
    displayMessage("NO PSRAM", "Build with qio_opi memory type");
    return;
  }
  char build[16] = {0};
  if (!assetsBegin(build, sizeof build)) {
    displayMessage("NO ASSETS", "Run: pio run -t uploadfs");
    Serial.println("[assets] LittleFS mount or build.txt failed - upload the asset pack");
    return;
  }
  if (strcmp(build, OMNI_BUILD_ID) != 0) {
    displayMessage("ASSET MISMATCH", "Re-upload firmware + uploadfs");
    Serial.printf("[assets] pack %s, firmware expects %s\n", build, OMNI_BUILD_ID);
    return;
  }
  if (!touchBegin()) Serial.println("[touch] FT3168 not responding");
  if (!pmuBegin()) Serial.println("[pmu] AXP2101 not responding");
  if (!rtcBegin()) Serial.println("[rtc] PCF85063 not responding");
  setCompileTimeIfUnset();
  bootButtonBegin();
  ready = uiBegin();
  if (!ready) displayMessage("OUT OF MEMORY", "Framebuffers did not fit");
  Serial.printf("[omnitrix] build %s ready=%d\n", OMNI_BUILD_ID, ready);
}

void loop() {
  pollSerial();
  if (ready) uiLoop(millis());
  delay(5);
}
