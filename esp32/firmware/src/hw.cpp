#include "hw.h"

#include <Arduino.h>
#include <Arduino_GFX_Library.h>
#include <Wire.h>

#define XPOWERS_CHIP_AXP2101
#include <XPowersLib.h>

#include "SensorPCF85063.hpp"
#include "board.h"

// ---- display --------------------------------------------------------------------
static Arduino_DataBus *bus =
    new Arduino_ESP32QSPI(LCD_CS, LCD_SCLK, LCD_SDIO0, LCD_SDIO1, LCD_SDIO2, LCD_SDIO3);
static Arduino_CO5300 *panel = new Arduino_CO5300(bus, LCD_RESET, 0 /* rotation */, LCD_W, LCD_H,
                                                  LCD_COL_OFFSET, 0, 0, 0);

bool displayBegin() {
  if (!panel->begin()) return false;
  panel->fillScreen(0x0000);
  panel->setBrightness(200);
  return true;
}

void displayPush(const uint16_t *fb) { panel->draw16bitRGBBitmap(0, 0, (uint16_t *)fb, LCD_W, LCD_H); }

void displaySetOn(bool on) {
  if (on) {
    panel->displayOn();
  } else {
    panel->displayOff();
  }
}

void displayBrightness(uint8_t level) { panel->setBrightness(level); }

void displayMessage(const char *title, const char *detail) {
  panel->fillScreen(0x0000);
  panel->setTextColor(0x3FE2);
  panel->setTextSize(3);
  panel->setCursor(30, 180);
  panel->println(title);
  panel->setTextColor(0xFFFF);
  panel->setTextSize(2);
  panel->setCursor(30, 240);
  panel->println(detail);
}

// ---- touch (FT3168, FocalTech register map) ----------------------------------------
bool touchBegin() {
  pinMode(TP_INT, INPUT_PULLUP);
  pinMode(TP_RESET, OUTPUT);
  digitalWrite(TP_RESET, LOW);
  delay(10);
  digitalWrite(TP_RESET, HIGH);
  delay(200);
  Wire.beginTransmission(FT3168_ADDR);
  return Wire.endTransmission() == 0;
}

bool touchRead(int16_t &x, int16_t &y) {
  Wire.beginTransmission(FT3168_ADDR);
  Wire.write(0x02);  // TD_STATUS, then P1_XH, P1_XL, P1_YH, P1_YL
  if (Wire.endTransmission(false) != 0) return false;
  if (Wire.requestFrom((uint8_t)FT3168_ADDR, (uint8_t)5) != 5) return false;
  uint8_t n = Wire.read() & 0x0F;
  uint8_t xh = Wire.read(), xl = Wire.read(), yh = Wire.read(), yl = Wire.read();
  if (n == 0 || n > 2) return false;
  x = (int16_t)(((xh & 0x0F) << 8) | xl);
  y = (int16_t)(((yh & 0x0F) << 8) | yl);
  return x < LCD_W && y < LCD_H;
}

// ---- PMU (AXP2101): read-only use ---------------------------------------------------
static XPowersPMU pmu;
static bool pmuOk = false;

bool pmuBegin() {
  pmuOk = pmu.begin(Wire, AXP2101_SLAVE_ADDRESS, I2C_SDA, I2C_SCL);
  if (!pmuOk) return false;
  pmu.enableBattDetection();
  pmu.enableBattVoltageMeasure();
  pmu.disableIRQ(XPOWERS_AXP2101_ALL_IRQ);
  pmu.clearIrqStatus();
  pmu.enableIRQ(XPOWERS_AXP2101_PKEY_SHORT_IRQ);
  return true;
}

int pmuBattery() {
  if (!pmuOk || !pmu.isBatteryConnect()) return -1;
  int p = pmu.getBatteryPercent();
  return p < 0 ? -1 : (p > 100 ? 100 : p);
}

bool pmuCharging() { return pmuOk && pmu.isCharging(); }

bool pmuPwrShort() {
  if (!pmuOk) return false;
  pmu.getIrqStatus();
  bool pressed = pmu.isPekeyShortPressIrq();
  if (pressed) pmu.clearIrqStatus();
  return pressed;
}

// ---- RTC (PCF85063) ----------------------------------------------------------------
static SensorPCF85063 rtc;
static bool rtcOk = false;

bool rtcBegin() {
  rtcOk = rtc.begin(Wire, I2C_SDA, I2C_SCL);
  return rtcOk;
}

bool rtcNow(struct tm &t) {
  if (!rtcOk) return false;
  RTC_DateTime d = rtc.getDateTime();
  t = {};
  t.tm_year = d.getYear() - 1900;
  t.tm_mon = d.getMonth() - 1;
  t.tm_mday = d.getDay();
  t.tm_hour = d.getHour();
  t.tm_min = d.getMinute();
  t.tm_sec = d.getSecond();
  mktime(&t);  // fills tm_wday
  return d.getYear() >= 2024;
}

void rtcSet(const struct tm &t) {
  if (!rtcOk) return;
  rtc.setDateTime(t.tm_year + 1900, t.tm_mon + 1, t.tm_mday, t.tm_hour, t.tm_min, t.tm_sec);
}

// ---- BOOT button -------------------------------------------------------------------
static bool bootLast = false;
static uint32_t bootChanged = 0;

void bootButtonBegin() { pinMode(BTN_BOOT, INPUT_PULLUP); }

bool bootPressed() {
  bool down = digitalRead(BTN_BOOT) == LOW;
  uint32_t now = millis();
  if (down != bootLast && now - bootChanged > 30) {
    bootLast = down;
    bootChanged = now;
    return down;
  }
  return false;
}
