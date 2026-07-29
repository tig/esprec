#pragma once

#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

/** esprec on-device component version string. */
#define ESPREC_COMPONENT_VERSION "0.2.0"

/**
 * Emit one full-frame capture on stdout (console-safe base64).
 *
 * Wire (shot):
 *   ESPREC1 w=… h=… fmt=rgb565be pack=spi_be enc=b64 nbytes=N crc=0x…
 *   base64 lines
 *   ESPREC1_END crc=0x…
 *
 * Optional seq/ts_ms after crc for spool frames:
 *   … crc=0x… seq=I ts_ms=T
 *
 * CRC32 covers canonical meta prefix + raster (w|h|fmt|pack|nbytes only).
 * Caller should hush ESP_LOG during emit if logs share the console.
 */
int esprec_emit_rgb565_spi_be(const uint16_t *pixels, int w, int h);

int esprec_emit_rgb565_spi_be_bytes(const uint8_t *pixels, int w, int h,
                                    size_t nbytes);

/** Emit with sequence index and timestamp (ms) for multi-frame spool. */
int esprec_emit_rgb565_spi_be_ex(const uint16_t *pixels, int w, int h, int seq,
                                 int64_t ts_ms);

/* ---- Multi-frame record (sample now, spool later) ---- */

/**
 * Begin a recording session.
 *
 * @param w,h          frame size (must match every push)
 * @param interval_ms  target sample period (product samples when due)
 * @param max_frames   hard cap (RAM or flash)
 * @param flash_dir    SPIFFS/dir prefix for flash frames, e.g. "/spiffs";
 *                     NULL = RAM-only (fail if not enough heap)
 * @return 0 on success
 *
 * Policy: if heap can hold all max_frames with ~80 KiB free reserve → RAM;
 * otherwise if flash_dir is set → flash files; else fail.
 * Prints: ok rec begin storage=ram|flash max=N interval_ms=I frame_bytes=B
 */
int esprec_rec_begin(int w, int h, int interval_ms, int max_frames,
                     const char *flash_dir);

/** True while accepting samples. */
int esprec_rec_active(void);

/** True if active and enough time has elapsed since last sample. */
int esprec_rec_due(int64_t now_ms);

/**
 * Store one frame (memcpy to RAM slot or write flash file) + timestamp.
 * No base64. Safe to call from UI tick when due.
 * @return 0 ok, 1 full (auto-stopped), <0 error
 *
 * pixels must be exactly w*h as given to esprec_rec_begin (already sized).
 */
int esprec_rec_push(const uint16_t *pixels, int64_t now_ms);

/**
 * Store from a larger source with nearest-neighbor downsample to rec size.
 * Typical: full-panel shadow → half-res rec for realtime sample rates on SPIFFS.
 * src_w/src_h must be integer multiples of rec w/h.
 */
int esprec_rec_push_scaled(const uint16_t *src, int src_w, int src_h,
                           int64_t now_ms);

/** Stop accepting samples (keep stored frames for spool). */
int esprec_rec_stop(void);

/** Frames stored so far. */
int esprec_rec_count(void);

/** "ram" or "flash" or "" if idle. */
const char *esprec_rec_storage(void);

/**
 * Emit all stored frames then free session.
 *
 *   ESPREC1_REC frames=N storage=… interval_ms=I
 *   ESPREC1 … seq=0 ts_ms=…
 *   …
 *   ESPREC1_REC_END frames=N
 */
int esprec_rec_spool(void);

/** Abort and free without spool. */
void esprec_rec_abort(void);

#ifdef __cplusplus
}
#endif
