#include "esprec.h"

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#if defined(ESP_PLATFORM)
#include "esp_heap_caps.h"
#include "esp_rom_crc.h"
#else
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
static void *heap_caps_malloc(size_t n, int caps) {
  (void)caps;
  return malloc(n);
}
#define MALLOC_CAP_8BIT 0
#endif

#define ESPREC_HEAP_RESERVE (40 * 1024)

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

static int emit_frame(const uint8_t *pixels, int w, int h, size_t nbytes,
                      int seq, int64_t ts_ms) {
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
  if (seq >= 0) {
    printf("ESPREC1 w=%d h=%d fmt=%s pack=%s enc=b64 nbytes=%u crc=0x%08lx "
           "seq=%d ts_ms=%lld\n",
           w, h, fmt, pack, (unsigned)nbytes, (unsigned long)crc, seq,
           (long long)ts_ms);
  } else {
    printf("ESPREC1 w=%d h=%d fmt=%s pack=%s enc=b64 nbytes=%u crc=0x%08lx\n", w,
           h, fmt, pack, (unsigned)nbytes, (unsigned long)crc);
  }
  fflush(stdout);
  emit_b64(pixels, nbytes);
  printf("ESPREC1_END crc=0x%08lx\n", (unsigned long)crc);
  fflush(stdout);
  return 0;
}

int esprec_emit_rgb565_spi_be_bytes(const uint8_t *pixels, int w, int h,
                                    size_t nbytes) {
  return emit_frame(pixels, w, h, nbytes, -1, 0);
}

int esprec_emit_rgb565_spi_be(const uint16_t *pixels, int w, int h) {
  if (!pixels) {
    printf("ESPREC1_ERR bad_args\n");
    fflush(stdout);
    return -1;
  }
  size_t nbytes = (size_t)w * (size_t)h * sizeof(uint16_t);
  return emit_frame((const uint8_t *)pixels, w, h, nbytes, -1, 0);
}

int esprec_emit_rgb565_spi_be_ex(const uint16_t *pixels, int w, int h, int seq,
                                 int64_t ts_ms) {
  if (!pixels) {
    printf("ESPREC1_ERR bad_args\n");
    fflush(stdout);
    return -1;
  }
  size_t nbytes = (size_t)w * (size_t)h * sizeof(uint16_t);
  return emit_frame((const uint8_t *)pixels, w, h, nbytes, seq, ts_ms);
}

/* ---- recorder ---- */

typedef struct {
  int active;
  int stopped;
  int w, h;
  size_t frame_bytes;
  int interval_ms;
  int max_frames;
  int count;
  int use_flash;
  char flash_prefix[48];
  uint8_t *ram; /* count slots * frame_bytes */
  int64_t *ts;
  uint32_t *crc; /* per-frame CRC so flash spool need not re-load whole frame for CRC */
  int64_t last_sample_ms;
  FILE *flash_fp; /* kept open for append during session (faster than reopen) */
} esprec_rec_t;

static esprec_rec_t s_rec;

static size_t free_heap_approx(void) {
#if defined(ESP_PLATFORM)
  return (size_t)heap_caps_get_free_size(MALLOC_CAP_8BIT);
#else
  return 8u * 1024u * 1024u;
#endif
}

static void rec_clear(void) {
  if (s_rec.flash_fp) {
    fclose(s_rec.flash_fp);
    s_rec.flash_fp = NULL;
  }
  free(s_rec.ram);
  free(s_rec.ts);
  free(s_rec.crc);
  memset(&s_rec, 0, sizeof s_rec);
}

static void flash_blob_path(char *out, size_t out_len) {
  snprintf(out, out_len, "%s/erec_blob.bin", s_rec.flash_prefix);
}

int esprec_rec_begin(int w, int h, int interval_ms, int max_frames,
                     const char *flash_dir) {
  esprec_rec_abort();
  if (w <= 0 || h <= 0 || max_frames <= 0 || interval_ms <= 0) {
    printf("ESPREC1_ERR rec_bad_args\n");
    fflush(stdout);
    return -1;
  }
  s_rec.w = w;
  s_rec.h = h;
  s_rec.frame_bytes = (size_t)w * (size_t)h * 2u;
  s_rec.interval_ms = interval_ms;
  s_rec.max_frames = max_frames;
  s_rec.count = 0;
  s_rec.last_sample_ms = -1;
  s_rec.ts = (int64_t *)calloc((size_t)max_frames, sizeof(int64_t));
  s_rec.crc = (uint32_t *)calloc((size_t)max_frames, sizeof(uint32_t));
  if (!s_rec.ts || !s_rec.crc) {
    printf("ESPREC1_ERR rec_oom_ts\n");
    fflush(stdout);
    rec_clear();
    return -2;
  }

  size_t free_h = free_heap_approx();
  int ram_cap = 0;
  if (free_h > (size_t)ESPREC_HEAP_RESERVE + s_rec.frame_bytes) {
    ram_cap = (int)((free_h - (size_t)ESPREC_HEAP_RESERVE) / s_rec.frame_bytes);
  }
  if (ram_cap > max_frames) {
    ram_cap = max_frames;
  }

  /* Prefer RAM only when it holds the full requested session (fast + simple).
   * Otherwise use flash so multi-second / multi-Hz captures are not capped at
   * 1–2 frames on heap-starved ESP32. */
  int use_ram = (ram_cap >= max_frames && ram_cap >= 2);
  if (use_ram) {
    size_t need = s_rec.frame_bytes * (size_t)max_frames;
    s_rec.ram = (uint8_t *)heap_caps_malloc(need, MALLOC_CAP_8BIT);
    if (!s_rec.ram) {
      s_rec.ram = (uint8_t *)malloc(need);
    }
    if (s_rec.ram) {
      s_rec.use_flash = 0;
      s_rec.active = 1;
      printf("ok rec begin storage=ram max=%d interval_ms=%d frame_bytes=%u "
             "free_heap=%u\n",
             max_frames, interval_ms, (unsigned)s_rec.frame_bytes,
             (unsigned)free_h);
      fflush(stdout);
      return 0;
    }
  }

  if (!flash_dir || !flash_dir[0]) {
    /* Last resort: partial RAM session if flash unavailable. */
    if (ram_cap >= 2) {
      size_t need = s_rec.frame_bytes * (size_t)ram_cap;
      s_rec.ram = (uint8_t *)malloc(need);
      if (s_rec.ram) {
        s_rec.max_frames = ram_cap;
        s_rec.use_flash = 0;
        s_rec.active = 1;
        printf("ok rec begin storage=ram max=%d interval_ms=%d frame_bytes=%u "
               "free_heap=%u (partial)\n",
               s_rec.max_frames, interval_ms, (unsigned)s_rec.frame_bytes,
               (unsigned)free_h);
        fflush(stdout);
        return 0;
      }
    }
    printf("ESPREC1_ERR rec_oom free=%u frame_bytes=%u (no flash_dir)\n",
           (unsigned)free_h, (unsigned)s_rec.frame_bytes);
    fflush(stdout);
    rec_clear();
    return -3;
  }

  snprintf(s_rec.flash_prefix, sizeof s_rec.flash_prefix, "%s", flash_dir);
  {
    char path[80];
    flash_blob_path(path, sizeof path);
    remove(path);
    s_rec.flash_fp = fopen(path, "wb");
    if (!s_rec.flash_fp) {
      printf("ESPREC1_ERR rec_flash_create %s\n", path);
      fflush(stdout);
      rec_clear();
      return -4;
    }
  }
  s_rec.use_flash = 1;
  s_rec.active = 1;
  printf("ok rec begin storage=flash max=%d interval_ms=%d frame_bytes=%u "
         "free_heap=%u dir=%s\n",
         max_frames, interval_ms, (unsigned)s_rec.frame_bytes, (unsigned)free_h,
         s_rec.flash_prefix);
  fflush(stdout);
  return 0;
}

int esprec_rec_active(void) { return s_rec.active && !s_rec.stopped; }

int esprec_rec_due(int64_t now_ms) {
  if (!esprec_rec_active()) {
    return 0;
  }
  if (s_rec.last_sample_ms < 0) {
    return 1;
  }
  return (now_ms - s_rec.last_sample_ms) >= (int64_t)s_rec.interval_ms;
}

int esprec_rec_push(const uint16_t *pixels, int64_t now_ms) {
  if (!esprec_rec_active() || !pixels) {
    return -1;
  }
  if (s_rec.count >= s_rec.max_frames) {
    s_rec.stopped = 1;
    return 1;
  }
  int i = s_rec.count;
  const uint8_t *raw = (const uint8_t *)pixels;
  uint32_t crc = crc_meta_raster(s_rec.w, s_rec.h, "rgb565be", "spi_be",
                                 s_rec.frame_bytes, raw);
  if (s_rec.use_flash) {
    if (!s_rec.flash_fp) {
      printf("ESPREC1_ERR rec_flash_closed\n");
      fflush(stdout);
      return -2;
    }
    size_t nw = fwrite(raw, 1, s_rec.frame_bytes, s_rec.flash_fp);
    fflush(s_rec.flash_fp);
    if (nw != s_rec.frame_bytes) {
      printf("ESPREC1_ERR rec_flash_write\n");
      fflush(stdout);
      return -3;
    }
  } else {
    memcpy(s_rec.ram + (size_t)i * s_rec.frame_bytes, raw, s_rec.frame_bytes);
  }
  s_rec.ts[i] = now_ms;
  s_rec.crc[i] = crc;
  s_rec.last_sample_ms = now_ms;
  s_rec.count++;
  if (s_rec.count >= s_rec.max_frames) {
    s_rec.stopped = 1;
    return 1;
  }
  return 0;
}

int esprec_rec_push_scaled(const uint16_t *src, int src_w, int src_h,
                           int64_t now_ms) {
  if (!esprec_rec_active() || !src) {
    return -1;
  }
  if (src_w == s_rec.w && src_h == s_rec.h) {
    return esprec_rec_push(src, now_ms);
  }
  if (src_w % s_rec.w != 0 || src_h % s_rec.h != 0) {
    return -4;
  }
  int sx = src_w / s_rec.w;
  int sy = src_h / s_rec.h;
  /* Static buffer avoids heap churn at sample rate (up to 80×60 = 9.6 KiB). */
  enum { SCALE_MAX_PIX = 80 * 60 };
  static uint16_t tmp[SCALE_MAX_PIX];
  if ((size_t)s_rec.w * (size_t)s_rec.h > SCALE_MAX_PIX) {
    printf("ESPREC1_ERR rec_scale_too_big\n");
    fflush(stdout);
    return -5;
  }
  for (int y = 0; y < s_rec.h; y++) {
    for (int x = 0; x < s_rec.w; x++) {
      tmp[y * s_rec.w + x] = src[(y * sy) * src_w + (x * sx)];
    }
  }
  return esprec_rec_push(tmp, now_ms);
}

int esprec_rec_stop(void) {
  if (!s_rec.active) {
    printf("ok rec stop frames=0\n");
    fflush(stdout);
    return 0;
  }
  s_rec.stopped = 1;
  printf("ok rec stop frames=%d storage=%s\n", s_rec.count,
         s_rec.use_flash ? "flash" : "ram");
  fflush(stdout);
  return 0;
}

int esprec_rec_count(void) { return s_rec.count; }

const char *esprec_rec_storage(void) {
  if (!s_rec.active && s_rec.count == 0) {
    return "";
  }
  return s_rec.use_flash ? "flash" : "ram";
}

static int emit_frame_known_crc(const uint8_t *pixels, int w, int h,
                                size_t nbytes, int seq, int64_t ts_ms,
                                uint32_t crc) {
  printf("ESPREC1 w=%d h=%d fmt=rgb565be pack=spi_be enc=b64 nbytes=%u "
         "crc=0x%08lx seq=%d ts_ms=%lld\n",
         w, h, (unsigned)nbytes, (unsigned long)crc, seq, (long long)ts_ms);
  fflush(stdout);
  emit_b64(pixels, nbytes);
  printf("ESPREC1_END crc=0x%08lx\n", (unsigned long)crc);
  fflush(stdout);
  return 0;
}

/** Stream base64 from a file (avoids a second full-frame heap buffer). */
static int emit_b64_file(FILE *f, size_t n) {
  static const char T[] =
      "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/";
  int col = 0;
  size_t i = 0;
  while (i < n) {
    uint8_t trip[3];
    size_t rem = n - i;
    size_t take = rem >= 3 ? 3 : rem;
    if (fread(trip, 1, take, f) != take) {
      return -1;
    }
    uint32_t a = trip[0];
    uint32_t b = take > 1 ? trip[1] : 0;
    uint32_t c = take > 2 ? trip[2] : 0;
    uint32_t triple = (a << 16) | (b << 8) | c;
    char out[5];
    out[0] = T[(triple >> 18) & 63];
    out[1] = T[(triple >> 12) & 63];
    out[2] = (take > 1) ? T[(triple >> 6) & 63] : '=';
    out[3] = (take > 2) ? T[triple & 63] : '=';
    out[4] = '\0';
    fputs(out, stdout);
    col += 4;
    if (col >= 76) {
      fputc('\n', stdout);
      col = 0;
    }
    i += take;
  }
  if (col) {
    fputc('\n', stdout);
  }
  fflush(stdout);
  return 0;
}

int esprec_rec_spool(void) {
  if (!s_rec.active && s_rec.count == 0) {
    printf("ESPREC1_ERR rec_empty\n");
    fflush(stdout);
    return -1;
  }
  s_rec.stopped = 1;
  if (s_rec.flash_fp) {
    fclose(s_rec.flash_fp);
    s_rec.flash_fp = NULL;
  }
  int n = s_rec.count;
  printf("ESPREC1_REC frames=%d storage=%s interval_ms=%d w=%d h=%d\n", n,
         s_rec.use_flash ? "flash" : "ram", s_rec.interval_ms, s_rec.w,
         s_rec.h);
  fflush(stdout);

  FILE *blob = NULL;
  if (s_rec.use_flash) {
    char path[80];
    flash_blob_path(path, sizeof path);
    blob = fopen(path, "rb");
    if (!blob) {
      printf("ESPREC1_ERR rec_spool_read %s\n", path);
      fflush(stdout);
      return -3;
    }
  }

  for (int i = 0; i < n; i++) {
    if (s_rec.use_flash) {
      if (fseek(blob, (long)((size_t)i * s_rec.frame_bytes), SEEK_SET) != 0) {
        fclose(blob);
        printf("ESPREC1_ERR rec_spool_seek\n");
        fflush(stdout);
        return -4;
      }
      printf("ESPREC1 w=%d h=%d fmt=rgb565be pack=spi_be enc=b64 nbytes=%u "
             "crc=0x%08lx seq=%d ts_ms=%lld\n",
             s_rec.w, s_rec.h, (unsigned)s_rec.frame_bytes,
             (unsigned long)s_rec.crc[i], i, (long long)s_rec.ts[i]);
      fflush(stdout);
      if (emit_b64_file(blob, s_rec.frame_bytes) != 0) {
        fclose(blob);
        printf("ESPREC1_ERR rec_spool_short\n");
        fflush(stdout);
        return -4;
      }
      printf("ESPREC1_END crc=0x%08lx\n", (unsigned long)s_rec.crc[i]);
      fflush(stdout);
    } else {
      const uint8_t *px = s_rec.ram + (size_t)i * s_rec.frame_bytes;
      (void)emit_frame_known_crc(px, s_rec.w, s_rec.h, s_rec.frame_bytes, i,
                                 s_rec.ts[i], s_rec.crc[i]);
    }
  }
  if (blob) {
    fclose(blob);
  }
  printf("ESPREC1_REC_END frames=%d\n", n);
  fflush(stdout);

  if (s_rec.use_flash) {
    char path[80];
    flash_blob_path(path, sizeof path);
    remove(path);
  }
  rec_clear();
  return 0;
}

void esprec_rec_abort(void) {
  if (s_rec.use_flash) {
    char path[80];
    flash_blob_path(path, sizeof path);
    remove(path);
  }
  rec_clear();
}
