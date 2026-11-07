// Omnitrix state machine, mirroring omnitrix/studio.py:
//   home -> select (alien dial) -> confirm (burst) -> info -> transform -> face (alien watch face)
// Inputs: PWR = side button, BOOT = back, touch = tap / swipe (turn dial) / hold 0.6 s (transform).
#pragma once
#include <stdint.h>
#include <time.h>

bool uiBegin();
void uiLoop(uint32_t nowMs);  // poll inputs, advance animations, redraw when needed
void uiSetTime(const struct tm &t);
void uiPrintStatus();
