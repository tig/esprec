#include "esprec.h"

#include <stdio.h>
#include <string.h>

#if defined(ESP_PLATFORM)
#include "esp_rom_crc.h"
#else
/* Host unit-build stub: CRC32 IEEE polynomial (matches binascii.crc32). */
static uint32_t esprec_crc32(uint32_t crc, const uint8_t *buf, size_t len) {
  crc = ~crc;
  for (size_t i = 0; i < len; i++) {
    crc ^= buf[i];
    for (int k = 0; k < 8; k++) {
      uint32_t mask = -(crc & 1u);
      crc = (crc >> 1) ^ (0xEDB88320u & mask);
    }
  }
  return ~crc;
}
#define esp_rom_crc32_le(crc, buf, len) esprec_crc32((crc), (buf), (len))
#endif

static void emit_b64(const uint8_t *src, size_t n) {
  static const char T[] =
      "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/";
  int col = 0;
  for (size_t i = 0; i < n; i += 3) {
    size_t rem = n - i;
    uint32_t a = src[i];
    uint32_t b = rem > 1 ? src[i + 1] : 0;
    uint32_t c = rem > 2 ? src[i + 2] : 0;
    uint32_t triple = (a << 16) | (b << 8) | c;
    char out[5];
    out[0] = T[(triple >> 18) & 63];
    out[1] = T[(triple >> 12) & 63];
    out[2] = (rem > 1) ? T[(triple >> 6) & 63] : '=';
    out[3] = (rem > 2) ? T[triple & 63] : '=';
    out[4] = '\0';
    fputs(out, stdout);
    col += 4;
    if (col >= 76) {
      fputc('\n', stdout);
      col = 0;
    }
  }
  if (col) {
    fputc('\n', stdout);
  }
  fflush(stdout);
}

static uint32_t crc_meta_raster(int w, int h, const char *fmt, const char *pack,
                                size_t nbytes, const uint8_t *pixels) {
  char prefix[96];
  int n = snprintf(prefix, sizeof prefix, "w=%d|h=%d|fmt=%s|pack=%s|nbytes=%u|",
                   w, h, fmt, pack, (unsigned)nbytes);
  if (n <= 0 || n >= (int)sizeof prefix) {
    return 0;
  }
  uint32_t crc = esp_rom_crc32_le(0, (const uint8_t *)prefix, (uint32_t)n);
  crc = esp_rom_crc32_le(crc, pixels, (uint32_t)nbytes);
  return crc;
}

int esprec_emit_rgb565_spi_be_bytes(const uint8_t *pixels, int w, int h,
                                    size_t nbytes) {
  if (!pixels || w <= 0 || h <= 0) {
    printf("ESPREC1_ERR bad_args\n");
    fflush(stdout);
    return -1;
  }
  size_t expect = (size_t)w * (size_t)h * 2u;
  if (nbytes != expect) {
    printf("ESPREC1_ERR nbytes\n");
    fflush(stdout);
    return -2;
  }
  const char *fmt = "rgb565be";
  const char *pack = "spi_be";
  uint32_t crc = crc_meta_raster(w, h, fmt, pack, nbytes, pixels);
  printf("ESPREC1 w=%d h=%d fmt=%s pack=%s enc=b64 nbytes=%u crc=0x%08lx\n", w,
         h, fmt, pack, (unsigned)nbytes, (unsigned long)crc);
  fflush(stdout);
  emit_b64(pixels, nbytes);
  printf("ESPREC1_END crc=0x%08lx\n", (unsigned long)crc);
  fflush(stdout);
  return 0;
}

int esprec_emit_rgb565_spi_be(const uint16_t *pixels, int w, int h) {
  if (!pixels) {
    printf("ESPREC1_ERR bad_args\n");
    fflush(stdout);
    return -1;
  }
  size_t nbytes = (size_t)w * (size_t)h * sizeof(uint16_t);
  return esprec_emit_rgb565_spi_be_bytes((const uint8_t *)pixels, w, h, nbytes);
}
