// Board hardware: AMOLED, touch, side buttons, RTC, PMU (battery) on the ESP32-S3-Touch-AMOLED-2.06.
// The PMU is only read (battery %, charging, PWR key interrupts); its voltages are left as the board sets them.
#pragma once
#include <stdint.h>
#include <time.h>

bool displayBegin();
void displayPush(const uint16_t *fb);  // full 410x502 frame
void displaySetOn(bool on);
void displayBrightness(uint8_t level);
void displayMessage(const char *title, const char *detail);  // plain-text error screen

bool touchBegin();
bool touchRead(int16_t &x, int16_t &y);  // true while a finger is down

bool pmuBegin();
int pmuBattery();     // 0..100, or -1 if no battery
bool pmuCharging();
bool pmuPwrShort();   // PWR key short press since the last call

bool rtcBegin();
bool rtcNow(struct tm &t);
void rtcSet(const struct tm &t);

void bootButtonBegin();
bool bootPressed();   // BOOT key press edge since the last call
