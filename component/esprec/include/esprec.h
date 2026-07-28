#pragma once

#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

/** esprec on-device component version string. */
#define ESPREC_COMPONENT_VERSION "0.1.0"

/**
 * Emit one full-frame capture on stdout (console-safe base64).
 *
 * @param pixels  RGB565 shadow buffer (same packing as panel SPI words on LE).
 * @param w       width in pixels
 * @param h       height in pixels
 * @return 0 on success, non-zero on error (also prints ESPREC1_ERR …)
 *
 * Wire:
 *   ESPREC1 w=… h=… fmt=rgb565be pack=spi_be enc=b64 nbytes=N crc=0x…
 *   base64 lines
 *   ESPREC1_END crc=0x…
 *
 * CRC32 covers canonical meta prefix + raster (see host esprec.protocol).
 * Caller should hush ESP_LOG during emit if logs share the console.
 */
int esprec_emit_rgb565_spi_be(const uint16_t *pixels, int w, int h);

/**
 * Same as esprec_emit_rgb565_spi_be but accepts byte pointer + byte length.
 * nbytes must equal w*h*2.
 */
int esprec_emit_rgb565_spi_be_bytes(const uint8_t *pixels, int w, int h,
                                    size_t nbytes);

#ifdef __cplusplus
}
#endif
