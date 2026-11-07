#include "inflate.h"

#include <stdlib.h>

#include "esp32s3/rom/miniz.h"

size_t zlibInflate(const uint8_t *in, size_t inLen, uint8_t *out, size_t outLen) {
  // The decompressor state is ~11 KB: keep it off the task stack.
  auto *d = (tinfl_decompressor *)malloc(sizeof(tinfl_decompressor));
  if (!d) return 0;
  tinfl_init(d);
  size_t inBytes = inLen, outBytes = outLen;
  tinfl_status st = tinfl_decompress(d, in, &inBytes, out, out, &outBytes,
                                     TINFL_FLAG_PARSE_ZLIB_HEADER | TINFL_FLAG_USING_NON_WRAPPING_OUTPUT_BUF);
  free(d);
  return st == TINFL_STATUS_DONE ? outBytes : 0;
}
