#pragma once
#include <stddef.h>
#include <stdint.h>

// Inflate a zlib stream (Python zlib.compress) with the ESP32-S3 ROM's miniz. Returns bytes written, 0 on error.
size_t zlibInflate(const uint8_t *in, size_t inLen, uint8_t *out, size_t outLen);
