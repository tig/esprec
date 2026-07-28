/* Host-buildable synthetic emitter: prove C component CRC matches Python. */
#include <stdio.h>
#include <stdint.h>
#include <string.h>

/* Compile esprec.c without ESP_PLATFORM for host CRC stub. */
#include "../../component/esprec/esprec.c"

int main(void) {
  const int w = 4, h = 2;
  uint16_t px[8];
  memset(px, 0, sizeof px);
  /* solid-ish pattern */
  for (int i = 0; i < 8; i++) {
    px[i] = (uint16_t)(0x00F8 + i); /* arbitrary spi_be words */
  }
  return esprec_emit_rgb565_spi_be(px, w, h) == 0 ? 0 : 1;
}
