// Waveshare ESP32-S3-Touch-AMOLED-2.06 pin map
// Source: waveshareteam/ESP32-S3-Touch-AMOLED-2.06, examples/arduino/libraries/board_config/pin_config.h
#pragma once

// CO5300 AMOLED, QSPI
#define LCD_SDIO0 4
#define LCD_SDIO1 5
#define LCD_SDIO2 6
#define LCD_SDIO3 7
#define LCD_SCLK 11
#define LCD_CS 12
#define LCD_RESET 8
#define LCD_W 410
#define LCD_H 502
#define LCD_COL_OFFSET 22  // from Waveshare's Arduino_CO5300 setup for this panel

// Shared I2C bus: FT3168 touch (0x38), PCF85063 RTC, AXP2101 PMU, QMI8658 IMU
#define I2C_SDA 15
#define I2C_SCL 14
#define TP_INT 38
#define TP_RESET 9
#define FT3168_ADDR 0x38

// Side buttons: BOOT is GPIO0 (active low, readable after boot); PWR goes through the AXP2101 (PKEY IRQ)
#define BTN_BOOT 0
